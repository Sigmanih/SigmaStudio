# Gradus — Functional Weight Engine (vendored in Sigma Studio)

Questo pacchetto è il motore **Gradus FWE** integrato in Sigma Studio.

- **Upstream:** https://github.com/xxrickyxx/Gradus-LLM-
- **Licenza:** MIT (vedi [LICENSE](LICENSE)) — copyright degli autori originali.
- **Modello sorgente:** Qwen2.5 (Alibaba, Apache 2.0). Codebook e indici compressi
  sono un derivato dei pesi Qwen.
- **Backbone generatore:** `xxrickyxx/ailo-152m`.
- **Documentazione architetturale originale:** [docs/MODELLO.md](docs/MODELLO.md)

## Cos'è

Invece di *memorizzare* le matrici di pesi di un transformer, Gradus le **genera**
con una funzione: un decoder AILO da 152M congelato, guidato da un codebook VQ e da
coordinate semantiche (tipo di tensore, layer, posizione del blocco), produce i
blocchi 32×32 di pesi su richiesta. Il payload per-modello scende a ~0.5 MB perché
il decoder si paga una volta sola ed è riusabile su modelli diversi.

Il motore non usa l'autograd: forward **e** backward sono scritti a mano per ogni op
(Linear, LayerNorm, RMSNorm, attenzione causale + RoPE, GQA, SwiGLU, VQ con
straight-through estimator, Adam con gradient clipping). Nell'upstream serviva a
girare su GPU AMD via DirectML, dove l'autograd sospende il device.

## Modifiche Sigma Studio (CUDA)

Le modifiche restano **matematicamente equivalenti** all'originale: i percorsi
DirectML/CPU sono invariati e i gradient-check upstream continuano a passare
(`python -m gradus engine-test --brick 1|2|3`).

| File | Modifica | Perché |
|---|---|---|
| `config.py` | `pick_device` CUDA-first (cuda → xpu → mps → dml → cpu); nuove `setup_device`, `is_cuda`, `device_summary` | L'originale sceglieva DirectML prima di MPS; su NVIDIA ora si usano i tensor core. `setup_device` abilita TF32 e cudnn.benchmark su Ampere+ |
| `engine/nn.py` | `Embedding.backward` e `VQLatent` usano `index_add_`/`bincount` su CUDA | La one-hot `(N,K)` dell'originale (necessaria su DML) alloca ~1 GB con N=8192, K=30000 |
| `engine/nn.py` | `Adam` con `torch._foreach_*` su CUDA | Un kernel fuso per l'intera lista di parametri invece di ~6 per parametro; la norma per il clipping resta sul device (niente sync host per step) |
| `engine/ailo_ops.py` | Cache di RoPE e maschera causale; `baddbmm` per gli score | Erano ricalcolate a ogni forward di ogni layer |
| `engine/qwen_ops.py` | Stesse cache + `baddbmm` sul percorso GQA | Idem |
| `engine/fwe.py` | Accumulatore gradienti allocato una volta, `_foreach_add_`, indici randint sul device, loss di eval accumulata sul device, chunk 1024 su CUDA | Elimina churn dell'allocatore e sincronizzazioni host nel loop di training |

Il percorso non-CUDA è selezionato a runtime da `is_cuda_tensor()`: su DirectML,
CPU e MPS il codice eseguito è identico a quello upstream.

## Sharding multi-GPU (`engine/multigpu.py`)

Il profiling del loop FWE (`GRADUS_PROFILE=1`) dice dove va il tempo:

```
gen_backward 67% | gen_forward 27% | blockify 5% | qwen 0% | optim 0%
```

Il generatore domina e il modello target è irrilevante. Quel lavoro è
**indipendente blocco per blocco**, quindi si divide fra GPU senza toccare la
matematica: ogni scheda tiene una replica del generatore e una fetta dei
blocchi, i gradienti degli adattatori vengono sommati sul primario, Adam
aggiorna e ridistribuisce.

Le fette sono proporzionali alla throughput **misurata** di ogni scheda (una
calibrazione di un chunk per device all'avvio), non al numero di core: su GPU
diverse una divisione a metà sarebbe limitata dalla più lenta.

Anche il chunk di ogni device è dimensionato su misure, non su stime: si rileva
la memoria di attivazioni per blocco con un forward+backward reale (5,7 MB/blocco
su questo modello) e si sottrae la memoria che quel device dovrà **ancora**
allocare. Sul primario sono diversi GB (i buffer dei pesi e dei gradienti del
modello target), quindi al momento del calcolo sembra la scheda più libera pur
essendo l'unica che deve ancora ospitarli.

Misure su RTX 5070 Ti + RTX 5060 (`_proj`, 349.440 blocchi, VQ K=512, wikitext,
21 step consecutivi):

| Configurazione | s/step | picco VRAM |
|---|---|---|
| Singola GPU (versione iniziale) | 61,9 | — |
| Singola GPU + blockify vettorizzato | 55,5 | — |
| Due GPU, chunk fisso 1024 | 39,1 → 43,5 (in deriva) | 13,2 GB |
| **Due GPU, chunk dimensionato sulle misure** | **39,3 costante** | **12,2 GB** |

1,57× complessivo; il solo sharding vale 1,41× contro un tetto teorico di 1,50×
dato dal rapporto di throughput misurato (2:1 fra le due schede). Su 600 step:
10,3 h → 6,5 h. I chunk più piccoli non costano velocità: eliminano la deriva
del tempo per step, che era pressione sull'allocatore.

Uso: `--devices all` (o `cuda:0,cuda:1`) da CLI, casella "Dividi il generatore
su tutte le GPU" nel Training Lab. Con una sola GPU il percorso è quello
originale, invariato.

Tre cose imparate a caro prezzo, tutte coperte da test:

* il `join()` di un thread Python **non** aspetta i kernel CUDA che ha accodato:
  senza `torch.cuda.synchronize` per device si leggono buffer ancora in
  scrittura, e il training diverge silenziosamente (ppl finale 123 invece di 66);
* i buffer di scambio vanno preallocati: allocarli a ogni step frammenta
  l'allocatore fino all'OOM, e su Windows `expandable_segments` non esiste;
* `permute(...).reshape(...)` su un tensore non contiguo **materializza una
  copia**. Nel blockify vettorizzato erano ~1,4 GB di temporanei per step su 168
  tensori: si copia invece dentro una *vista* permutata della destinazione, che
  non alloca nulla.

`_blockify_grad` e `_assemble_matrix` avevano un ciclo Python per blocco:
349.440 iterazioni per step. Le matrici di Qwen sono tutte multiple di 32,
quindi il caso allineato ora è una singola copia fra viste (il ramo con bordi
ragged resta per le architetture che non si dividono esatte). Vale 1,12× anche
su GPU singola.

## Compatibilità transformers 5.x

L'upstream è scritto per transformers 4.x. Sigma Studio usa la 5.5, che ha
cambiato tre cose:

| Cosa | Prima (4.x) | Ora (5.x) | Soluzione |
|---|---|---|---|
| RoPE theta | `config.rope_theta` | `config.rope_parameters["rope_theta"]` | `modelio.config_get()` / `model_hparams()` leggono entrambi i layout |
| Chat template | ritorna un tensore | ritorna un `BatchEncoding` | `chat._to_input_ids()` normalizza prima di `generate()` |

Il modello Qwen manuale ricostruito da `model_hparams()` è stato verificato
contro il forward di HuggingFace: **loss 4.117368 vs 4.117335 (Δ 3.3e-05)**,
in linea con il 4e-5 dichiarato dall'upstream.

## Backbone AILO

L'upstream si aspetta una cartella `./ailo_backbone` creata a mano con
`scripts/prepare_ailo_backbone.py`, risolta rispetto alla directory di lavoro —
inutilizzabile dai job del Training Lab, che girano nella propria cartella.

`gradus/backbone.py` lo risolve in posizioni indipendenti dalla CWD (argomento
esplicito → `$GRADUS_AILO_BACKBONE` → `training/backbones/ailo_backbone` →
`./ailo_backbone`) e, se non lo trova, lo scarica e converte in safetensors
automaticamente al primo run. La conversione serve ancora: AILO è pubblicato in
`.bin` e transformers con torch < 2.6 (ambiente torch-directml) rifiuta di
caricarlo.

Il download usa `trust_remote_code=True` perché l'architettura AILO include
codice del modello nel repository HuggingFace: è un requisito dell'upstream, non
una scelta di Sigma. I pesi (~600 MB) finiscono in `training/backbones/`, che è
in `.gitignore`.
