// Sonda di sola lettura: ABI degli header e librerie devono avere la stessa build.
#include "probe_common.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <random>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
using Clock = std::chrono::steady_clock;

struct Stats {
    uint32_t width = 0, count = 0;
    std::vector<uint32_t> channels;
    std::vector<double> sum, sum2;
    std::vector<float> samples;
};
struct Capture {
    decltype(&ggml_backend_tensor_get) tensor_get;
    std::set<int> layers;
    std::map<std::string, Stats> stats;
    bool active = false;
    bool full_output = false;
    bool distill = false;
    bool channel_input = false;
    uint32_t input_width = 0;
    std::vector<std::vector<uint32_t>> channel_plan;
    std::string hidden_name;
    std::vector<float> hidden_samples;
    std::string error;
    Clock::time_point deadline;
};

bool collect(ggml_tensor * tensor, bool ask, void * opaque) noexcept {
    auto & state = *static_cast<Capture *>(opaque);
    if (!state.active) return ask ? false : true;
    if (state.distill && state.hidden_name==tensor->name) {
        if (ask) return true;
        try {
            if (tensor->type!=GGML_TYPE_F32 || tensor->ne[0]<128 || tensor->ne[0]>8192 ||
                tensor->ne[1]!=1 || tensor->ne[2]!=1 || tensor->ne[3]!=1 || tensor->nb[0]!=4 ||
                state.hidden_samples.size()+tensor->ne[0]>512*8192)
                throw std::runtime_error("Stato pre-normalizzazione fuori budget");
            const auto before=state.hidden_samples.size();
            state.hidden_samples.resize(before+tensor->ne[0]);
            state.tensor_get(tensor,state.hidden_samples.data()+before,0,tensor->ne[0]*4);
            for (size_t i=before;i<state.hidden_samples.size();++i)
                if (!std::isfinite(state.hidden_samples[i])) throw std::runtime_error("Stato nascosto non finito");
            return true;
        } catch (const std::exception & e) {state.error=e.what();return false;}
        catch (...) {state.error="Acquisizione dello stato nascosto fallita";return false;}
    }
    const auto * weight = tensor->src[0];
    const auto * input = state.full_output ? tensor : tensor->src[1];
    int layer = -1;
    char family[16]{};
    if (tensor->op != GGML_OP_MUL_MAT || !weight || !input ||
        std::sscanf(weight->name, "blk.%d.%15[^.]", &layer, family) != 2 ||
        !state.layers.count(layer) ||
        (std::strcmp(family, "ffn_gate") && std::strcmp(family, "ffn_down")))
        return ask ? false : true;
    if ((state.full_output || state.channel_input) && std::strcmp(family, "ffn_down")) return ask ? false : true;
    if (ask) return true;
    // Nessuna eccezione deve attraversare il confine C della callback.
    try {
        if (Clock::now() > state.deadline) throw std::runtime_error("Tempo di acquisizione esaurito");
        if (input->type != GGML_TYPE_F32 || input->ne[0] < 128 || input->ne[0] > 65536 ||
            input->ne[1] != 1 || input->ne[2] != 1 || input->ne[3] != 1 || input->nb[0] != 4)
            throw std::runtime_error("Forma o tipo dell'attivazione non supportato");
        auto & item = state.stats[weight->name];
        const auto width = static_cast<uint32_t>(input->ne[0]);
        if (state.channel_input && width!=state.input_width) throw std::runtime_error("Dimensione del piano non compatibile");
        if (!item.width) {
            item.width = width;
            item.sum.resize(width); item.sum2.resize(width);
            item.channels.resize(width);
            std::iota(item.channels.begin(), item.channels.end(), 0);
            std::mt19937 rng(42 + width);
            std::shuffle(item.channels.begin(), item.channels.end(), rng);
            if (state.channel_input) {
                item.channels=state.channel_plan[layer];
                std::cout<<"input_node "<<layer<<" "<<input->name<<std::endl;
            } else item.channels.resize(state.full_output ? width : 128);
            std::sort(item.channels.begin(), item.channels.end());
        }
        if (item.width != width || item.count >= 512)
            throw std::runtime_error("Budget o dimensione delle attivazioni incoerente");
        std::vector<float> values(width);
        state.tensor_get(input, values.data(), 0, width*sizeof(float));
        for (uint32_t i=0; i<width; ++i) {
            const double value = values[i];
            if (!std::isfinite(value)) throw std::runtime_error("Attivazione non finita");
            item.sum[i] += value; item.sum2[i] += value*value;
        }
        for (auto index : item.channels) item.samples.push_back(values[index]);
        ++item.count;
        return true;
    } catch (const std::exception & e) {
        state.error = e.what();
        return false;
    } catch (...) {
        state.error = "Errore inatteso nella callback";
        return false;
    }
}

int main(int argc, char ** argv) {
    llama_model * model = nullptr;
    llama_context * ctx = nullptr;
    decltype(&llama_model_free) model_free = nullptr;
    decltype(&llama_free) context_free = nullptr;
    try {
        if (argc != 6 && argc != 7 && argc != 8) throw std::runtime_error("Uso: sonda runtime_dir modello.gguf jobs.bin misure.bin gpu [last-output|distill|channel-input piano.bin]");
        const bool channel_input=argc==8 && std::string(argv[6])=="channel-input";
        const bool distill=argc==7 && std::string(argv[6])=="distill";
        const bool full_output=distill || (argc==7 && std::string(argv[6])=="last-output");
        if ((argc==7 && !full_output) || (argc==8 && !channel_input)) throw std::runtime_error("Modalita' non valida");
        const fs::path runtime = fs::absolute(argv[1]);
        const int gpu = std::stoi(argv[5]);
        if (gpu < -1 || gpu > 15) throw std::runtime_error("Dispositivo non valido");
#ifdef _WIN32
        SetDllDirectoryW(runtime.wstring().c_str());
        Library base(runtime / "ggml-base.dll"), backend(runtime / "ggml.dll"), llama(runtime / "llama.dll");
#else
        Library base(runtime / "libggml-base.so"), backend(runtime / "libggml.so"), llama(runtime / "libllama.so");
#endif
#define LLAMA_FN(name) auto name = llama.symbol<decltype(&::name)>(#name)
        LLAMA_FN(llama_backend_init); LLAMA_FN(llama_model_default_params);
        LLAMA_FN(llama_context_default_params); LLAMA_FN(llama_model_load_from_file);
        LLAMA_FN(llama_init_from_model); LLAMA_FN(llama_model_n_layer);
        LLAMA_FN(llama_get_memory); LLAMA_FN(llama_memory_clear);
        LLAMA_FN(llama_batch_get_one); LLAMA_FN(llama_decode);
        LLAMA_FN(llama_get_logits_ith); LLAMA_FN(llama_model_get_vocab); LLAMA_FN(llama_vocab_n_tokens);
        model_free = llama.symbol<decltype(model_free)>("llama_model_free");
        context_free = llama.symbol<decltype(context_free)>("llama_free");
        auto load_backends = backend.symbol<decltype(&ggml_backend_load_all_from_path)>("ggml_backend_load_all_from_path");
        auto tensor_get = base.symbol<decltype(&ggml_backend_tensor_get)>("ggml_backend_tensor_get");
        load_backends(runtime.string().c_str());
        llama_backend_init();
        auto mp = llama_model_default_params();
        mp.n_gpu_layers = gpu < 0 ? 0 : -1;
        mp.split_mode = LLAMA_SPLIT_MODE_NONE; mp.main_gpu = std::max(gpu, 0); mp.load_mtp = false;
        model = llama_model_load_from_file(argv[2], mp);
        if (!model) throw std::runtime_error("Caricamento del modello fallito");
        const int vocab_size=llama_vocab_n_tokens(llama_model_get_vocab(model));
        Capture capture{};
        capture.tensor_get = tensor_get;
        capture.full_output = full_output;
        capture.distill=distill;
        capture.channel_input=channel_input;
        const int n_layers = llama_model_n_layer(model);
        if (n_layers < 1 || n_layers > 256) throw std::runtime_error("Numero di layer non supportato");
        capture.hidden_name="l_out-"+std::to_string(n_layers-1);
        if (channel_input) {
            std::ifstream plan(argv[7],std::ios::binary);char header[8];
            if (!plan.read(header,8) || std::memcmp(header,"SGCP0001",8)) throw std::runtime_error("Piano non valido");
            const auto count=read<uint32_t>(plan),width=read<uint32_t>(plan),sampled=read<uint32_t>(plan);
            if (count!=uint32_t(n_layers) || count>64 || width<128 || width>65536 || !sampled || sampled>2048 || sampled>width)
                throw std::runtime_error("Piano fuori budget");
            capture.input_width=width;capture.channel_plan.resize(count);
            for (uint32_t layer=0;layer<count;++layer) {
                auto & indices=capture.channel_plan[layer];indices.resize(sampled);
                for (uint32_t j=0;j<sampled;++j) {
                    indices[j]=read<uint32_t>(plan);
                    if (indices[j]>=width || (j && indices[j]<=indices[j-1])) throw std::runtime_error("Canali del piano non validi");
                }
                capture.layers.insert(layer);
            }
            if (plan.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Dati in eccesso nel piano");
        }
        else if (full_output) capture.layers.insert(n_layers-1);
        else for (int i=0; i<5; ++i) capture.layers.insert(i*(n_layers-1)/4);
        capture.deadline = Clock::now() + std::chrono::seconds(900);
        auto cp = llama_context_default_params();
        cp.n_ctx=8192; cp.n_batch=512; cp.n_ubatch=512; cp.n_seq_max=1;
        cp.n_threads=4; cp.n_threads_batch=4;
        cp.type_k=GGML_TYPE_Q8_0; cp.type_v=GGML_TYPE_Q8_0;
        cp.flash_attn_type=LLAMA_FLASH_ATTN_TYPE_ENABLED;
        cp.cb_eval=collect; cp.cb_eval_user_data=&capture;
        ctx = llama_init_from_model(model, cp);
        if (!ctx) throw std::runtime_error("Creazione del contesto fallita");
        std::ifstream in(argv[3], std::ios::binary);
        char magic[8];
        if (!in.read(magic, 8) || std::memcmp(magic,"SGAP0001",8)) throw std::runtime_error("Protocollo di ingresso non valido");
        const auto jobs = read<uint32_t>(in);
        if (!jobs || jobs > 16) throw std::runtime_error("Numero di casi oltre il budget");
        // Un file preesistente potrebbe contenere misure da conservare.
        if (fs::exists(argv[4])) throw std::runtime_error("Il file delle misure esiste gia'");
        std::ofstream out(argv[4], std::ios::binary);
        out.write(channel_input ? "SGAO0005" : (distill ? "SGAO0004" : (full_output ? "SGAO0003" : "SGAO0001")),8); write(out,jobs);
        uint64_t capture_bytes=12;
        for (uint32_t job=0; job<jobs; ++job) {
            const auto prefix_n=read<uint32_t>(in), response_n=read<uint32_t>(in);
            if (!prefix_n || !response_n || response_n>512 || prefix_n+response_n>8192)
                throw std::runtime_error("Token oltre il budget");
            if (channel_input) {
                capture_bytes+=12+capture.layers.size()*(128+uint64_t(capture.input_width)*16+
                    uint64_t(capture.channel_plan[0].size())*(4+uint64_t(response_n)*4));
                if (capture_bytes>512ULL*1024*1024) throw std::runtime_error("Cattura oltre il budget del file");
            }
            std::vector<llama_token> prefix(prefix_n), response(response_n);
            if (!in.read(reinterpret_cast<char *>(prefix.data()), prefix_n*4) ||
                !in.read(reinterpret_cast<char *>(response.data()), response_n*4))
                throw std::runtime_error("Token troncati");
            for (const auto token : prefix) if (token<0 || token>=vocab_size) throw std::runtime_error("Token fuori vocabolario");
            for (const auto token : response) if (token<0 || token>=vocab_size) throw std::runtime_error("Token fuori vocabolario");
            llama_memory_clear(llama_get_memory(ctx), true);
            capture.active=false; capture.stats.clear(); capture.error.clear();capture.hidden_samples.clear();
            for (uint32_t i=0; i+1<prefix_n;) {
                if (Clock::now()>capture.deadline) throw std::runtime_error("Tempo esaurito");
                const auto count=std::min(uint32_t(512),prefix_n-1-i);
                auto batch=llama_batch_get_one(prefix.data()+i, count);
                if (llama_decode(ctx,batch)) throw std::runtime_error("Prefill fallito");
                i+=count;
            }
            capture.active=true;
            uint32_t greedy_matches=0;
            std::vector<int32_t> first_choices,second_choices;
            std::vector<float> margins;
            std::vector<float> first_probabilities,second_probabilities;
            // Ogni misura precede il token della risposta: nessun accesso ai token futuri.
            for (uint32_t step=0; step<response_n; ++step) {
                if (Clock::now()>capture.deadline) throw std::runtime_error("Tempo esaurito");
                auto token = step ? response[step-1] : prefix.back();
                auto batch=llama_batch_get_one(&token,1);
                const auto code=llama_decode(ctx,batch);
                if (code || !capture.error.empty()) throw std::runtime_error("Replay fallito: " + capture.error);
                const auto * logits=llama_get_logits_ith(ctx,-1);
                if (!logits || vocab_size<1) throw std::runtime_error("Logits mancanti");
                const auto greedy=std::max_element(logits,logits+vocab_size)-logits;
                greedy_matches += greedy==response[step];
                if (full_output) {
                    int32_t runner=greedy==0 ? 1 : 0;
                    for (int32_t i=0;i<vocab_size;++i)
                        if (i!=greedy && logits[i]>logits[runner]) runner=i;
                    const float margin=logits[greedy]-logits[runner];
                    if (!std::isfinite(margin)) throw std::runtime_error("Margine non finito");
                    first_choices.push_back(static_cast<int32_t>(greedy));
                    second_choices.push_back(runner);margins.push_back(margin);
                    if (distill) {
                        double total=0;
                        for (int32_t i=0;i<vocab_size;++i) total+=std::exp(double(logits[i])-logits[greedy]);
                        first_probabilities.push_back(static_cast<float>(1/total));
                        second_probabilities.push_back(static_cast<float>(std::exp(-double(margin))/total));
                    }
                }
            }
            if (capture.stats.size()!=capture.layers.size()*((full_output || channel_input) ? 1 : 2)) throw std::runtime_error("Tensori attesi non acquisiti");
            write(out,greedy_matches);write(out,response_n);
            write(out,static_cast<uint32_t>(capture.stats.size()));
            for (const auto & pair : capture.stats) {
                const auto & name=pair.first; const auto & s=pair.second;
                if (s.count!=response_n) throw std::runtime_error("Campionamento duplicato o incompleto");
                write(out,static_cast<uint32_t>(name.size()));out.write(name.data(),name.size());
                write(out,s.width);write(out,s.count);write(out,static_cast<uint32_t>(s.channels.size()));
                write_vector(out,s.channels);write_vector(out,s.sum);write_vector(out,s.sum2);write_vector(out,s.samples);
            }
            if (full_output) {write_vector(out,first_choices);write_vector(out,second_choices);write_vector(out,margins);}
            if (distill) {
                const auto width=capture.stats.begin()->second.width;
                if (capture.hidden_samples.size()!=size_t(response_n)*width)
                    throw std::runtime_error("Stato pre-normalizzazione mancante o duplicato");
                write_vector(out,capture.hidden_samples);
                write_vector(out,first_probabilities);write_vector(out,second_probabilities);
            }
            out.flush();
            std::cout << "case " << job+1 << "/" << jobs << " tokens " << response_n
                      << " greedy_matches " << greedy_matches << std::endl;
        }
        if (in.peek()!=std::char_traits<char>::eof()) throw std::runtime_error("Dati in eccesso nel protocollo");
        out.close();
        if (!out) throw std::runtime_error("Chiusura delle misure fallita");
        context_free(ctx);ctx=nullptr;model_free(model);model=nullptr;
        std::cout << "SIGMA-CHECK {\"check\":\"activation-capture\",\"checked\":" << jobs << ",\"problems\":0}" << std::endl;
        return 0;
    } catch (const std::exception & e) {
        if (ctx && context_free) context_free(ctx);
        if (model && model_free) model_free(model);
        std::cerr << e.what() << std::endl;
        return 1;
    }
}
