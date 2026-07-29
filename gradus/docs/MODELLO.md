# Gradus-AILO — definizione del modello

*Documento di architettura e identità del sistema. Aggiornato al run "modello completo
Qwen2.5-0.5B" (in corso sul motore sovrano, RX 6750 XT).*

---

## 1. L'artefatto

L'artefatto finale **non è una copia di Qwen**: è un **generatore di pesi**. I 358M di parametri del transformer di Qwen non
esistono più come tabella — vengono **ricostruiti on-demand da una funzione**:

```
indice del blocco (9 bit) ──► atomo del codebook (64 numeri)
                                      │
   contesto (tipo q/k/v/o/gate/up/down, layer, posizione)
                                      │
                                      ▼
                        AILO 152M (decoder CONGELATO)
                                      │
                                      ▼
                          blocco di pesi 32×32 di "Qwen"
```

### Composizione dell'artefatto (numeri esatti, Qwen2.5-0.5B)

| Componente | Dimensione | Ruolo |
|---|---|---|
| **AILO** (12 layer, 768) | 152.3M | decoder condiviso, congelato — la "fabbrica di pesi" |
| Adattatori (in_proj + head + embedding tipo/layer) | 1.3M | traducono contesto → spazio AILO → blocco |
| **Codebook VQ** (K=512 atomi × 64) | 131 KB | il "DNA" compresso dei pesi |
| **Indici** (349.440 blocchi × 9 bit) | 0.39 MB | quale atomo usa ogni blocco |
| Embedding token (non compresso) | 136.1M | vocabolario (fuori ambito v1) |
| Statistiche per-tensore (mean/std) + norm/bias 1D | <1M | denormalizzazione |
| **TOTALE deploy** | **~290M** | vs **494M** originali → **1.7× netto** |

Il transformer vero e proprio passa da **358M → ~154M equivalenti** (2.3×), e la parte
*specifica di Qwen* dentro l'artefatto è **solo ~0.5MB** (codebook+indici): tutto il
resto è AILO riusabile. **È qui la scala**: lo stesso decoder da 152M ammortizzato su
modelli più grandi dà 4× sull'1.5B e ~10× sul 7B (vedi §5).

---

## 2. Architettura in dettaglio

### 2.1 Il generatore (l'artefatto)
- **Decoder**: AILO 152M (`tok_emb/head testuali scartati; usati blocks + ln_f`),
  **congelato** — non vede mai testo, riceve "pseudo-token" di contesto.
- **Latent**: VQ codebook (K atomi condivisi, EMA + reinit atomi morti). A deploy
  restano solo **indici** (log₂K bit/blocco) + codebook. Niente latent liberi:
  la compressione nasce dalla **ridondanza tra blocchi** che collassano sugli
  stessi atomi.
- **Contesto** (l'input della "funzione dei pesi"): embedding del **tipo** di tensore
  (q/k/v/o/gate/up/down/embed), embedding del **layer**, posizione del blocco
  (riga/colonna normalizzate + assolute + aspect) con Fourier features.
- **Testa**: mean-pool sull'output di AILO → lineare → blocco 32×32.

### 2.2 L'obiettivo di training
**Task-fidelity, non copia dei pesi**: i pesi generati vengono iniettati nel Qwen
(manuale) e si minimizza la **loss del linguaggio** su wikitext. Il generatore impara
pesi *che fanno funzionare il modello*, non pesi identici — è ciò che permette
compressione oltre il muro rate-distortion (misurato: la copia esatta si ferma a ~2×).

### 2.3 Il motore di training
Tutto il training gira su un **motore scritto da zero** (`gradus/engine/`):
- forward **e backward a mano** per ogni op (Linear, LayerNorm, RMSNorm, attention
  causale con RoPE, GQA 14:2, SwiGLU, softmax, embedding, cross-entropy, VQ-STE),
  ognuna **gradient-checked** contro PyTorch (errori 1e-6/1e-9);
- Adam manuale con gradient clipping; gradient accumulation (micro-batch);
- checkpoint atomici + resume; buffer riusati (VRAM costante);
- gira su **RX 6750 XT via DirectML usando solo forward-op** — l'autograd dei
  framework standard su quella scheda crasha (TDR), quello di Gradus no.
  Niente CUDA, niente ROCm.

---

## 3. Cronologia dei risultati

| Tappa | Risultato misurato |
|---|---|
| Coordinate→peso (funzione pura) | cosine ~0.05 → i pesi NON sono funzione delle coordinate |
| Latent liberi + AILO | cosine 0.98 con latent grande, ma latent = storage → non comprime |
| AILO **congelato** + latent 2× | cosine **0.996** → AILO è una base di decodifica ricchissima |
| Latent liberi 8×, held-out wikitext | ppl 47.6→85.1 ✗ |
| **Codebook VQ** K=256, held-out | ppl 47.6→70.6 (274× lato-latent, meglio dei liberi a 8×!) |
| + **batch fix** (grad. accumulation) | ppl 47.6→**53.35 = GENERALIZZA (+12%)** ✓ |
| Modello completo (_proj, 24 layer) | **in corso** |

---

## 4. Ricetta di training (riproducibile)

```bash
# dalla GUI:  python run_gui.py  → sezione "Motore FWE" → Avvia
# o da CLI:
.venv/Scripts/python -m gradus engine-fwe --objective task --qwen-manual \
  --dataset wikitext --include _proj --max-layers -1 \
  --vq 512 --latent-dim 64 --block-size 32 \
  --steps 600 --lr 2e-4 --batch 8 --device dml \
  --run-dir runs/engine-full --save-every 25
# chat durante il training:
.venv/Scripts/python -m gradus engine-chat --ckpt runs/engine-full/engine_ckpt.pt --prompt "..."
```

---

## 5. Roadmap di scala

| Target | Transformer → artefatto | Netto (con embed) | Dove |
|---|---|---|---|
| **0.5B** (in corso) | 358M → ~154M | 494M → **~290M (1.7×)** | 6750, 2-3 giorni |
| **1.5B** | 1.3B → ~154M | 1.5B → **~390M (4×)** | 6750 **dopo ottimizzazioni fp16** |
| 7B | 6.5B → ~155M | 7.6B → **~0.7B (~11×)** | serve CUDA (training); inferenza anche locale |
| 500B (visione) | — | decoder ammortizzato ~totalmente | ricerca futura, ferro grosso |

Nota: la parte *per-modello* dell'artefatto cresce pochissimo (indici ∝ n. blocchi:
il 7B sono ~27MB di indici). **Il decoder AILO è pagato una volta sola.**

---

## 6. Licenze e attribuzioni

- **Gradus (codice, motore, architettura)**: MIT (repo Gradus-LLM-).
- **AILO**: modello dell'autore (licenza dual CC BY-NC-SA).
- **Qwen2.5-0.5B/1.5B-Instruct**: Apache 2.0 (Alibaba) → derivati permessi con
  attribuzione e notice; la model card deve citare Qwen come modello sorgente.
- **wikitext-2**: dataset pubblico (CC BY-SA), usato solo per il training del generatore.
