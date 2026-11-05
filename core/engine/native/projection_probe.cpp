// Intervento causale in memoria: y -> U(U^T y), senza scrivere il checkpoint.
#include "probe_common.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <fstream>
#include <iostream>
#include <limits>

using Clock = std::chrono::steady_clock;

struct Projection {
    decltype(&ggml_backend_tensor_get) get;
    decltype(&ggml_backend_tensor_set) set;
    std::string target, mode, error;
    uint32_t width=0, rank=0, calls=0;
    std::vector<float> basis;
    std::vector<float> decoder;
    std::vector<std::vector<uint32_t>> channel_masks;
    std::vector<std::vector<uint32_t>> anchor_indices;
    std::vector<std::vector<float>> reconstruction_weights;
    std::vector<uint32_t> layer_calls;
    Clock::time_point deadline;
};

bool project(ggml_tensor * t, bool ask, void * opaque) noexcept {
    auto & s=*static_cast<Projection *>(opaque);
    int layer=-1;
    const bool masked=s.mode=="channel-mask";
    const bool recovered=s.mode=="channel-reconstruction";
    if (recovered) {
        if (std::sscanf(t->name,"ffn_swiglu-%d",&layer)!=1 || layer<0 ||
            size_t(layer)>=s.channel_masks.size() || std::string(t->name)!="ffn_swiglu-"+std::to_string(layer))
            return ask ? false : true;
    } else if (t->op!=GGML_OP_MUL_MAT || !t->src[0]) return ask ? false : true;
    else if (masked) {
        if (std::sscanf(t->src[0]->name,"blk.%d.",&layer)!=1 || layer<0 ||
            size_t(layer)>=s.channel_masks.size() ||
            std::string(t->src[0]->name)!="blk."+std::to_string(layer)+".ffn_up.weight")
            return ask ? false : true;
    } else if (s.target!=t->src[0]->name) return ask ? false : true;
    if (ask) return true;
    try {
        if (Clock::now()>s.deadline) throw std::runtime_error("Tempo dell'intervento esaurito");
        if (t->type!=GGML_TYPE_F32 || t->ne[0]<1 || t->ne[0]>((masked || recovered) ? 65536 : 8192) || t->ne[1]<1 ||
            t->ne[1]>512 || t->ne[2]!=1 || t->ne[3]!=1 || t->nb[0]!=4 ||
            t->nb[1]!=size_t(t->ne[0])*4 || (s.width && s.width!=t->ne[0]))
            throw std::runtime_error("Uscita FFN incompatibile con la proiezione");
        ++s.calls;
        if (masked || recovered) {
            ++s.layer_calls[layer];
            if (s.channel_masks[layer].empty()) return true;
        }
        if (s.mode=="none") return true;
        const auto width=static_cast<size_t>(t->ne[0]), tokens=static_cast<size_t>(t->ne[1]);
        std::vector<float> values(width*tokens);
        s.get(t,values.data(),0,values.size()*sizeof(float));
        for (float v:values) if (!std::isfinite(v)) throw std::runtime_error("Attivazione non finita");
        if (recovered) {
            const auto & indices=s.anchor_indices[layer];
            const auto & weights=s.reconstruction_weights[layer];
            for (size_t token=0;token<tokens;++token)
                for (size_t r=0;r<s.channel_masks[layer].size();++r) {
                    double predicted=0;
                    for (size_t a=0;a<indices.size();++a)
                        predicted+=double(weights[r*indices.size()+a])*values[token*width+indices[a]];
                    const float value=static_cast<float>(predicted);
                    if (!std::isfinite(value)) throw std::runtime_error("Ricostruzione non finita");
                    values[token*width+s.channel_masks[layer][r]]=value;
                }
        }
        else if (masked) {
            // Annullare up prima di SwiGLU elimina il canale senza cambiare gate o residuo.
            for (size_t token=0;token<tokens;++token)
                for (auto index:s.channel_masks[layer]) values[token*width+index]=0.0f;
        }
        else if (s.mode=="zero") std::fill(values.begin(),values.end(),0.0f);
        else if (s.mode=="basis") {
            std::vector<double> coordinates(s.rank);
            for (size_t token=0; token<tokens; ++token) {
                auto * y=values.data()+token*width;
                for (uint32_t r=0; r<s.rank; ++r) {
                    double value=0;
                    const auto * u=s.basis.data()+r*width;
                    for (size_t j=0; j<width; ++j) value+=double(u[j])*y[j];
                    coordinates[r]=value;
                }
                for (size_t j=0; j<width; ++j) {
                    double value=0;
                    const auto & decoded=s.decoder.empty() ? s.basis : s.decoder;
                    for (uint32_t r=0; r<s.rank; ++r) value+=decoded[r*width+j]*coordinates[r];
                    y[j]=static_cast<float>(value);
                }
            }
        }
        // La callback arresta lo scheduler su questo nodo prima dei consumatori.
        s.set(t,values.data(),0,values.size()*sizeof(float));
        return true;
    } catch (const std::exception & e) {
        s.error=e.what(); return false;
    } catch (...) {
        s.error="Errore inatteso nella proiezione"; return false;
    }
}

int main(int argc,char ** argv) {
    llama_model * model=nullptr;
    llama_context * ctx=nullptr;
    llama_context * baseline_ctx=nullptr;
    decltype(&llama_model_free) free_model=nullptr;
    decltype(&llama_free) free_ctx=nullptr;
    try {
        if (argc!=7 && argc!=8) throw std::runtime_error("Uso: sonda runtime modello jobs.bin risposte.bin gpu none|identity|zero|base.bin [score]");
        const bool scoring=argc==8 && std::string(argv[7])=="score";
        if (argc==8 && !scoring) throw std::runtime_error("Modalita' di misura non valida");
        Projection s{};
        s.mode=argv[6];
        if (s.mode!="none" && s.mode!="identity" && s.mode!="zero") {
            std::ifstream basis(argv[6],std::ios::binary);
            char magic[8];
            if (!basis.read(magic,8)) throw std::runtime_error("Base non valida");
            if (std::memcmp(magic,"SGCR0001",8)==0) {
                const auto count=read<uint32_t>(basis);s.width=read<uint32_t>(basis);
                const auto removed=read<uint32_t>(basis),anchors=read<uint32_t>(basis);
                if (!count || count>64 || s.width<128 || s.width>65536 || removed>512 || anchors>1024 ||
                    removed+anchors>s.width || ((!removed)!=(!anchors)) || uint64_t(count)*removed*anchors>16777216)
                    throw std::runtime_error("Ricostruzione fuori budget");
                s.channel_masks.resize(count);s.anchor_indices.resize(count);
                s.reconstruction_weights.resize(count);s.layer_calls.resize(count);
                for (uint32_t layer=0;layer<count;++layer) {
                    for (auto * indices:{&s.channel_masks[layer],&s.anchor_indices[layer]}) {
                        indices->resize(indices==&s.channel_masks[layer] ? removed : anchors);
                        for (size_t j=0;j<indices->size();++j) {
                            (*indices)[j]=read<uint32_t>(basis);
                            if ((*indices)[j]>=s.width || (j && (*indices)[j]<=(*indices)[j-1]))
                                throw std::runtime_error("Indici della ricostruzione non validi");
                        }
                    }
                    for (auto index:s.channel_masks[layer])
                        if (std::binary_search(s.anchor_indices[layer].begin(),s.anchor_indices[layer].end(),index))
                            throw std::runtime_error("Canali rimossi e conservati sovrapposti");
                    auto & weights=s.reconstruction_weights[layer];weights.resize(size_t(removed)*anchors);
                    if (!basis.read(reinterpret_cast<char *>(weights.data()),weights.size()*4)) throw std::runtime_error("Coefficienti troncati");
                    for (auto value:weights) if (!std::isfinite(value) || std::abs(value)>10000)
                        throw std::runtime_error("Coefficienti di ricostruzione non validi");
                }
                if (basis.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Dati in eccesso nella ricostruzione");
                s.mode="channel-reconstruction";
            }
            else if (std::memcmp(magic,"SGCM0001",8)==0) {
                const auto count=read<uint32_t>(basis);
                s.width=read<uint32_t>(basis);
                const auto removed=read<uint32_t>(basis);
                if (!count || count>256 || s.width<128 || s.width>65536 ||
                    removed>=s.width || removed>4096 || uint64_t(count)*removed>1048576)
                    throw std::runtime_error("Maschera di canali fuori budget");
                s.channel_masks.resize(count);s.layer_calls.resize(count);
                for (auto & mask:s.channel_masks) {
                    mask.resize(removed);
                    for (size_t i=0;i<removed;++i) {
                        mask[i]=read<uint32_t>(basis);
                        if (mask[i]>=s.width || (i && mask[i]<=mask[i-1]))
                            throw std::runtime_error("Canali non ordinati, duplicati o fuori intervallo");
                    }
                }
                if (basis.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Dati in eccesso nella maschera");
                s.mode="channel-mask";
            } else {
            if (std::memcmp(magic,"SGAB0001",8) && std::memcmp(magic,"SGAF0001",8)) throw std::runtime_error("Base non valida");
            const bool factored=std::memcmp(magic,"SGAF0001",8)==0;
            s.width=read<uint32_t>(basis);s.rank=read<uint32_t>(basis);
            if (!s.width || s.width>8192 || !s.rank || s.rank>512 || s.rank>s.width)
                throw std::runtime_error("Forma della base fuori budget");
            s.basis.resize(size_t(s.width)*s.rank);
            if (!basis.read(reinterpret_cast<char *>(s.basis.data()),s.basis.size()*4)) throw std::runtime_error("Encoder troncato");
            if (factored) {
                s.decoder.resize(s.basis.size());
                if (!basis.read(reinterpret_cast<char *>(s.decoder.data()),s.decoder.size()*4)) throw std::runtime_error("Decoder troncato");
                for (float v:s.decoder) if (!std::isfinite(v)) throw std::runtime_error("Decoder non finito");
            }
            if (basis.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Dati in eccesso nella base");
            for (float v:s.basis) if (!std::isfinite(v)) throw std::runtime_error("Base non finita");
            s.mode="basis";
            }
        }
        if (fs::exists(argv[4])) throw std::runtime_error("Il file delle risposte esiste gia'");
        const auto runtime=fs::absolute(argv[1]);
        const int gpu=std::stoi(argv[5]);
        if (gpu < -1 || gpu>15) throw std::runtime_error("Dispositivo non valido");
#ifdef _WIN32
        SetDllDirectoryW(runtime.wstring().c_str());
        Library base(runtime/"ggml-base.dll"), backend(runtime/"ggml.dll"), llama(runtime/"llama.dll");
#else
        Library base(runtime/"libggml-base.so"), backend(runtime/"libggml.so"), llama(runtime/"libllama.so");
#endif
#define FN(name) auto name=llama.symbol<decltype(&::name)>(#name)
        FN(llama_backend_init);FN(llama_model_default_params);FN(llama_context_default_params);
        FN(llama_model_load_from_file);FN(llama_init_from_model);FN(llama_model_n_layer);
        FN(llama_model_get_vocab);FN(llama_vocab_n_tokens);FN(llama_vocab_is_eog);
        FN(llama_get_memory);FN(llama_memory_clear);FN(llama_batch_get_one);FN(llama_decode);FN(llama_get_logits_ith);
        free_model=llama.symbol<decltype(free_model)>("llama_model_free");
        free_ctx=llama.symbol<decltype(free_ctx)>("llama_free");
        auto load=backend.symbol<decltype(&ggml_backend_load_all_from_path)>("ggml_backend_load_all_from_path");
        s.get=base.symbol<decltype(s.get)>("ggml_backend_tensor_get");
        s.set=base.symbol<decltype(s.set)>("ggml_backend_tensor_set");
        load(runtime.string().c_str());llama_backend_init();
        auto mp=llama_model_default_params();
        mp.n_gpu_layers=gpu<0 ? 0 : -1;mp.split_mode=LLAMA_SPLIT_MODE_NONE;
        mp.main_gpu=std::max(gpu,0);mp.load_mtp=false;
        model=llama_model_load_from_file(argv[2],mp);
        if (!model) throw std::runtime_error("Caricamento del modello fallito");
        const auto * vocab=llama_model_get_vocab(model);
        const int vocab_n=llama_vocab_n_tokens(vocab), layers=llama_model_n_layer(model);
        if (layers<1 || layers>256) throw std::runtime_error("Numero di layer non valido");
        if ((s.mode=="channel-mask" || s.mode=="channel-reconstruction") && s.channel_masks.size()!=size_t(layers))
            throw std::runtime_error("La maschera non copre tutti i layer del modello");
        const auto check_coverage=[&s]() {
            if ((s.mode=="channel-mask" || s.mode=="channel-reconstruction") &&
                std::any_of(s.layer_calls.begin(),s.layer_calls.end(),[](uint32_t n){return !n;}))
                throw std::runtime_error("Intervento non osservato in tutti i layer");
        };
        s.target="blk."+std::to_string(layers-1)+".ffn_down.weight";
        s.deadline=Clock::now()+std::chrono::seconds(900);
        auto cp=llama_context_default_params();
        cp.n_ctx=8192;cp.n_batch=512;cp.n_ubatch=512;cp.n_seq_max=1;
        cp.n_threads=4;cp.n_threads_batch=4;cp.type_k=GGML_TYPE_Q8_0;cp.type_v=GGML_TYPE_Q8_0;
        cp.flash_attn_type=LLAMA_FLASH_ATTN_TYPE_ENABLED;cp.cb_eval=project;cp.cb_eval_user_data=&s;
        ctx=llama_init_from_model(model,cp);
        if (!ctx) throw std::runtime_error("Contesto non disponibile");
        Projection baseline{};
        baseline.get=s.get;baseline.set=s.set;baseline.target=s.target;
        baseline.mode="none";baseline.deadline=s.deadline;
        if (scoring) {
            cp.cb_eval_user_data=&baseline;
            baseline_ctx=llama_init_from_model(model,cp);
            if (!baseline_ctx) throw std::runtime_error("Contesto di controllo non disponibile");
        }
        std::vector<bool> eog(vocab_n);
        for (int i=0;i<vocab_n;++i) eog[i]=llama_vocab_is_eog(vocab,i);
        std::ifstream in(argv[3],std::ios::binary);
        char magic[8];
        if (!in.read(magic,8) || std::memcmp(magic,"SGAP0001",8)) throw std::runtime_error("Replay non valido");
        const auto jobs=read<uint32_t>(in);
        if (!jobs || jobs>16) throw std::runtime_error("Numero di casi fuori budget");
        std::ofstream out(argv[4],std::ios::binary);
        out.write(scoring ? "SGAS0001" : "SGAG0001",8);write(out,jobs);
        for (uint32_t job=0; job<jobs; ++job) {
            const auto prefix_n=read<uint32_t>(in), budget=read<uint32_t>(in);
            if (!prefix_n || !budget || budget>512 || prefix_n+budget>8192) throw std::runtime_error("Token fuori budget");
            std::vector<llama_token> prefix(prefix_n), ignored(budget);
            if (!in.read(reinterpret_cast<char *>(prefix.data()),prefix_n*4) ||
                !in.read(reinterpret_cast<char *>(ignored.data()),budget*4)) throw std::runtime_error("Replay troncato");
            for (auto token:prefix) if (token<0 || token>=vocab_n) throw std::runtime_error("Token fuori vocabolario");
            if (scoring) {
                for (uint32_t i=0;i<budget;++i)
                    if (ignored[i]<0 || ignored[i]>=vocab_n || (i+1<budget && eog[ignored[i]]))
                        throw std::runtime_error("Riferimento con token non valido o arresto anticipato");
                if (!eog[ignored.back()]) throw std::runtime_error("Il riferimento deve includere la decisione di arresto");
                llama_memory_clear(llama_get_memory(baseline_ctx),true);
                baseline.calls=0;baseline.error.clear();
            }
            llama_memory_clear(llama_get_memory(ctx),true);s.calls=0;s.error.clear();
            std::fill(s.layer_calls.begin(),s.layer_calls.end(),0);
            const auto start=Clock::now();
            for (uint32_t offset=0; offset<prefix_n;) {
                const auto count=std::min(uint32_t(512),prefix_n-offset);
                auto batch=llama_batch_get_one(prefix.data()+offset,count);
                if (llama_decode(ctx,batch) || !s.error.empty()) throw std::runtime_error("Prefill: "+s.error);
                if (scoring && (llama_decode(baseline_ctx,batch) || !baseline.error.empty()))
                    throw std::runtime_error("Prefill del controllo: "+baseline.error);
                offset+=count;
            }
            if (scoring) {
                write(out,budget);
                for (uint32_t step=0;step<budget;++step) {
                    if (Clock::now()>s.deadline) throw std::runtime_error("Tempo della misura esaurito");
                    const auto * p=llama_get_logits_ith(baseline_ctx,-1);
                    const auto * q=llama_get_logits_ith(ctx,-1);
                    if (!p || !q) throw std::runtime_error("Logits di confronto mancanti");
                    const auto pt=static_cast<int32_t>(std::max_element(p,p+vocab_n)-p);
                    const auto qt=static_cast<int32_t>(std::max_element(q,q+vocab_n)-q);
                    const double pm=p[pt],qm=q[qt];
                    double ps=0,qs=0;
                    double pe=-std::numeric_limits<double>::infinity(),qe=pe,pn=pe,qn=pe;
                    for (int i=0;i<vocab_n;++i) {
                        if (!std::isfinite(p[i]) || !std::isfinite(q[i])) throw std::runtime_error("Logits non finiti");
                        ps+=std::exp(double(p[i])-pm);qs+=std::exp(double(q[i])-qm);
                        if (eog[i]) {pe=std::max(pe,double(p[i]));qe=std::max(qe,double(q[i]));}
                        else {pn=std::max(pn,double(p[i]));qn=std::max(qn,double(q[i]));}
                    }
                    const double pl=pm+std::log(ps),ql=qm+std::log(qs);
                    double kl=0,tv=0,ep=0,eq=0;
                    for (int i=0;i<vocab_n;++i) {
                        const double lp=double(p[i])-pl,lq=double(q[i])-ql;
                        const double pp=std::exp(lp),qq=std::exp(lq);
                        kl+=pp*(lp-lq);tv+=std::abs(pp-qq);
                        if (eog[i]) {ep+=pp;eq+=qq;}
                    }
                    write(out,ignored[step]);write(out,pt);write(out,qt);
                    write(out,static_cast<uint32_t>(eog[ignored[step]]));
                    for (double value : {std::max(0.0,kl),tv*.5,pl-p[ignored[step]],ql-q[ignored[step]],ep,eq,pe-pn,qe-qn})
                        write(out,value);
                    if (step+1<budget) {
                        auto next=ignored[step];auto batch=llama_batch_get_one(&next,1);
                        if (llama_decode(ctx,batch) || !s.error.empty()) throw std::runtime_error("Replay: "+s.error);
                        if (llama_decode(baseline_ctx,batch) || !baseline.error.empty()) throw std::runtime_error("Replay del controllo: "+baseline.error);
                    }
                }
                if (!s.calls || !baseline.calls) throw std::runtime_error("Controllo non eseguito");
                check_coverage();
                write(out,s.calls);write(out,baseline.calls);
                const double seconds=std::chrono::duration<double>(Clock::now()-start).count();write(out,seconds);
                out.flush();
                std::cout<<"scored "<<job+1<<"/"<<jobs<<" positions "<<budget<<" seconds "<<seconds<<std::endl;
                continue;
            }
            std::vector<llama_token> generated;
            uint32_t ended=0;
            for (uint32_t step=0; step<budget; ++step) {
                if (Clock::now()>s.deadline) throw std::runtime_error("Tempo di generazione esaurito");
                const auto * logits=llama_get_logits_ith(ctx,-1);
                if (!logits) throw std::runtime_error("Logits mancanti");
                const auto token=static_cast<llama_token>(std::max_element(logits,logits+vocab_n)-logits);
                if (llama_vocab_is_eog(vocab,token)) { ended=1;break; }
                generated.push_back(token);
                if (step+1==budget) break;
                auto next=token;auto batch=llama_batch_get_one(&next,1);
                if (llama_decode(ctx,batch) || !s.error.empty()) throw std::runtime_error("Generazione: "+s.error);
            }
            if (!s.calls) throw std::runtime_error("Intervento non eseguito");
            check_coverage();
            const double seconds=std::chrono::duration<double>(Clock::now()-start).count();
            write(out,static_cast<uint32_t>(generated.size()));write(out,ended);write(out,s.calls);write(out,seconds);
            write_vector(out,generated);out.flush();
            std::cout<<"case "<<job+1<<"/"<<jobs<<" tokens "<<generated.size()<<" ended "<<ended<<" seconds "<<seconds<<std::endl;
        }
        if (in.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Replay con dati in eccesso");
        out.close();if (!out) throw std::runtime_error("Salvataggio incompleto");
        if (baseline_ctx) {free_ctx(baseline_ctx);baseline_ctx=nullptr;}
        free_ctx(ctx);ctx=nullptr;free_model(model);model=nullptr;
        std::cout<<"SIGMA-CHECK {\"check\":\""<<(scoring ? "paired-token-scoring" : "causal-generation")<<"\",\"checked\":"<<jobs<<",\"problems\":0}"<<std::endl;
        return 0;
    } catch (const std::exception & e) {
        if (baseline_ctx && free_ctx) free_ctx(baseline_ctx);
        if (ctx && free_ctx) free_ctx(ctx);if (model && free_model) free_model(model);
        std::cerr<<e.what()<<std::endl;return 1;
    }
}
