"""Brick 4 — flusso FWE completo sul MOTORE manuale:
allena il generatore su un tensore vero di Qwen sulla 6750, ricostruisce i pesi,
li inietta nel modello e prova un prompt. Tutto end-to-end, training sulla tua GPU.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import torch

from ..config import (GradusConfig, BlockConfig, TrainConfig, GeneratorConfig,
                      pick_device, torch_device, resolve_model,
                      setup_device, device_summary, is_cuda)
from ..logging_utils import section
from ..modelio import (TENSOR_TYPES, build_plan, load_target_model,
                       materialize_targets, reconstruct_state_dict, model_hparams)
from .nn import Adam, mse_loss
from .generator import ManualGenerator


class PhaseProfiler:
    """Cronometro per fase del loop di training.

    Le fasi sono utili per capire dove va il tempo (generazione dei blocchi,
    modello target, backward del generatore...). Attivo solo con la variabile
    d'ambiente GRADUS_PROFILE=1: le sincronizzazioni CUDA necessarie a misurare
    correttamente falserebbero altrimenti il throughput.
    """

    def __init__(self, enabled: bool, device=None):
        self.enabled = enabled
        self.device = device
        self.totals: dict[str, float] = {}
        self._current = None
        self._t0 = 0.0

    def _sync(self):
        if self.device is not None and getattr(self.device, "type", "") == "cuda":
            torch.cuda.synchronize(self.device)

    def __call__(self, name):
        """Chiude la fase corrente e ne apre una nuova (None = solo chiusura)."""
        if not self.enabled:
            return
        import time as _time
        self._sync()
        now = _time.time()
        if self._current is not None:
            self.totals[self._current] = self.totals.get(self._current, 0.0) + (now - self._t0)
        self._current, self._t0 = name, now

    def summary(self) -> str:
        if not self.enabled or not self.totals:
            return ""
        total = sum(self.totals.values()) or 1.0
        parts = [f"{k} {v / total * 100:.0f}%"
                 for k, v in sorted(self.totals.items(), key=lambda kv: -kv[1])]
        return "  [" + " | ".join(parts) + "]"


def _stats(model, plan):
    params = dict(model.named_parameters())
    mean = torch.zeros(plan.num_blocks)
    std = torch.ones(plan.num_blocks)
    for e in plan.entries:
        w = params[e.name].detach().float()
        m, s = w.mean().item(), w.std().item()
        s = s if s > 1e-8 else 1.0
        n = e.grid_r * e.grid_c
        mean[e.block_start:e.block_start + n] = m
        std[e.block_start:e.block_start + n] = s
    return mean, std


@torch.no_grad()
def _cosine(pred_blocks, target_blocks):
    a, b = pred_blocks.flatten(), target_blocks.flatten()
    return (a @ b / (a.norm() * b.norm() + 1e-9)).item()


def _is_exact_grid(e, bs) -> bool:
    """True se la matrice si divide in blocchi bs×bs senza resti."""
    return e.rows == e.grid_r * bs and e.cols == e.grid_c * bs


def _assemble_matrix(blocks_real, e, bs, out=None):
    W = out if out is not None else torch.zeros(e.rows, e.cols, dtype=blocks_real.dtype,
                                                device=blocks_real.device)
    if _is_exact_grid(e, bs):
        # Niente bordi ragged: si copia in una VISTA permutata di W invece di
        # ciclare su grid_r*grid_c (con 349k blocchi il ciclo Python domina).
        # La vista e' essenziale: `permute(...).reshape(...)` su un tensore non
        # contiguo materializzerebbe un temporaneo per ogni tensore del piano,
        # ~1.4 GB per step che frammentano l'allocatore fino all'OOM.
        W.view(e.grid_r, bs, e.grid_c, bs).permute(0, 2, 1, 3).copy_(
            blocks_real.view(e.grid_r, e.grid_c, bs, bs))
        return W
    for br in range(e.grid_r):
        for bc in range(e.grid_c):
            gi = br * e.grid_c + bc
            r0, c0 = br * bs, bc * bs
            r1, c1 = min(r0 + bs, e.rows), min(c0 + bs, e.cols)
            W[r0:r1, c0:c1] = blocks_real[gi, :r1 - r0, :c1 - c0]
    return W


def _blockify_grad(G, e, bs, out=None):
    if _is_exact_grid(e, bs):
        # sorgente come vista strided (nessuna copia), destinazione come vista
        # di `out`: la permutazione la risolve copy_ leggendo con gli stride
        src = G.view(e.grid_r, bs, e.grid_c, bs).permute(0, 2, 1, 3)
        dst = out if out is not None else torch.empty(e.grid_r * e.grid_c, bs, bs,
                                                      dtype=G.dtype, device=G.device)
        dst.view(e.grid_r, e.grid_c, bs, bs).copy_(src)
        return dst
    dst = out if out is not None else torch.zeros(e.grid_r * e.grid_c, bs, bs,
                                                  dtype=G.dtype, device=G.device)
    dst.zero_()
    for br in range(e.grid_r):
        for bc in range(e.grid_c):
            gi = br * e.grid_c + bc
            r0, c0 = br * bs, bc * bs
            r1, c1 = min(r0 + bs, e.rows), min(c0 + bs, e.cols)
            dst[gi, :r1 - r0, :c1 - c0] = G[r0:r1, c0:c1]
    return dst


_TASK_TEXT = (
    "La fotosintesi converte la luce solare in energia chimica nelle piante. "
    "I modelli linguistici prevedono la parola successiva a partire dal contesto. "
    "Le stelle nascono dal collasso di nubi di gas e polvere nello spazio. "
    "Un algoritmo e' una sequenza di istruzioni per risolvere un problema. "
    "Imparare una lingua apre le porte a nuove culture e idee. "
    "Gli oceani regolano il clima del pianeta assorbendo calore e anidride carbonica."
)

# Corpora DISGIUNTI: si allena su TRAIN, si misura su HELD-OUT (frasi mai viste).
_TRAIN_TEXT = (
    "La fotosintesi converte la luce solare in energia chimica nelle foglie verdi. "
    "Il cuore umano pompa il sangue attraverso le arterie e le vene del corpo. "
    "I vulcani eruttano lava quando la pressione del magma diventa troppo alta. "
    "Le api impollinano i fiori trasportando il polline da una pianta all'altra. "
    "Il sole e' una stella di medie dimensioni situata al centro del sistema solare. "
    "L'acqua bolle a cento gradi Celsius a livello del mare. "
    "La gravita' fa cadere gli oggetti verso il centro della Terra. "
    "Le piante assorbono anidride carbonica e rilasciano ossigeno nell'aria. "
    "Il ghiaccio si scioglie quando la temperatura supera lo zero. "
    "I fiumi trasportano l'acqua dalle montagne fino al mare. "
    "Il cervello umano contiene miliardi di neuroni collegati tra loro. "
    "La luna orbita intorno alla Terra in circa ventotto giorni."
)
_EVAL_TEXT = (
    "I terremoti avvengono quando le placche della crosta terrestre si muovono. "
    "Le foreste pluviali ospitano una enorme varieta' di animali e piante. "
    "Il vento nasce dalle differenze di pressione nell'atmosfera terrestre. "
    "Gli alberi crescono lentamente aggiungendo un anello ogni anno. "
    "La neve si forma quando il vapore acqueo congela nelle nuvole fredde. "
    "Il deserto riceve pochissima pioggia durante tutto l'arco dell'anno."
)


def run_task(logger, model="qwen0.5b-instruct", device="auto",
             include="layers.0.self_attn.q_proj", block_size=32, latent_dim=64,
             steps=200, prompt="Cos'è la fotosintesi?", ailo=True, freeze=True, lr=1e-3):
    """Fedelta-al-compito sul motore: generatore su GPU (backward manuale),
    gradienti del modello target da autograd CPU. Allena il generatore a MANTENERE
    la perplexity, non a copiare i pesi."""
    from torch.func import functional_call
    model_id = resolve_model(model)
    section(logger, "FWE task — carico il modello target (CPU, autograd)")
    qwen, tok, _ = load_target_model(model_id, "cpu", torch.float32)
    qwen.requires_grad_(False)

    cfg = GradusConfig(model=model_id, block=BlockConfig(block_size=block_size),
                       train=TrainConfig(include=include))
    plan = build_plan(qwen, cfg)
    logger.info("Piano: %d tensori, %d blocchi", plan.num_tensors, plan.num_blocks)
    mean, std = _stats(qwen, plan)
    feats = plan.features()

    label, dev = setup_device(device)
    logger.info("Device: %s", device_summary(label))
    if ailo:
        from .generator import build_ailo_generator
        gen = build_ailo_generator(plan, len(TENSOR_TYPES), block_size, dev,
                                   latent_dim=latent_dim, seq_len=4, logger=logger)
    else:
        gen = ManualGenerator(plan.num_blocks, len(TENSOR_TYPES), plan.num_layers, block_size, dev,
                              latent_dim=latent_dim, d_model=128, n_layers=4, n_heads=4, inter=256, seq_len=4)
    logger.info("Generatore su '%s'%s | obiettivo=task", label,
                " [AILO frozen]" if (ailo and freeze) else "")

    bid = plan.block_ids().to(dev); tid = feats["type_id"].to(dev)
    lid = feats["layer_id"].to(dev); cont = feats["cont"].to(dev)
    nb = plan.num_blocks
    CH = 196   # blocchi per chunk (limita la memoria GPU delle attivazioni)
    grads_fn = (lambda: gen.adapter_grads()) if freeze else (lambda: gen.grads())

    ids = tok(_TASK_TEXT, return_tensors="pt").input_ids[0]
    L = 48
    seqs = [ids[i:i + L] for i in range(0, max(1, len(ids) - L), L)]
    seqs = [s for s in seqs if len(s) >= 8] or [ids[:L]]
    text = torch.stack([torch.nn.functional.pad(s, (0, L - len(s)), value=tok.pad_token_id or 0) for s in seqs])

    @torch.no_grad()
    def gen_blocks_cpu():
        """Genera tutti i blocchi (normalizzati) a chunk -> (nb,bs,bs) su CPU."""
        outs = []
        for i in range(0, nb, CH):
            sl = slice(i, min(i + CH, nb))
            o = gen.forward(bid[sl], tid[sl], lid[sl], cont[sl])
            outs.append(o.reshape(-1, block_size, block_size).cpu())
        return torch.cat(outs, 0)

    def overrides_from(blocks_cpu, leaf=False):
        real = blocks_cpu * std[:, None, None] + mean[:, None, None]
        ov = {}
        for e in plan.entries:
            W = _assemble_matrix(real[e.block_start:e.block_start + e.grid_r * e.grid_c], e, block_size)
            ov[e.name] = W.requires_grad_(True) if leaf else W
        return ov

    def ppl_now():
        ov = overrides_from(gen_blocks_cpu())
        with torch.no_grad():
            return float(torch.exp(functional_call(qwen, ov, args=(), kwargs={"input_ids": text, "labels": text}).loss).item())

    base = float(torch.exp(qwen(input_ids=text, labels=text).loss).item())
    logger.info("Perplexity originale: %.3f | ricostruito iniziale: %.3f", base, ppl_now())

    train_params = gen.adapter_params() if freeze else gen.params()
    opt = Adam(train_params, lr=lr)
    section(logger, f"Training task-fidelity su '{label}' (Qwen autograd su CPU)")
    for step in range(1, steps + 1):
        # 1) genera i pesi (chunked, no-grad) e prendi dL/dpesi da Qwen (autograd CPU)
        leaves = overrides_from(gen_blocks_cpu(), leaf=True)
        batch = text[torch.randint(0, len(text), (min(2, len(text)),))]
        loss = functional_call(qwen, leaves, args=(), kwargs={"input_ids": batch, "labels": batch}).loss
        loss.backward()
        gb_cpu = torch.zeros(nb, block_size, block_size)
        for e in plan.entries:
            gb_cpu[e.block_start:e.block_start + e.grid_r * e.grid_c] = _blockify_grad(leaves[e.name].grad, e, block_size)
        # grad rispetto all'output NORMALIZZATO del generatore (chain del denorm: x std)
        dout = (gb_cpu * std[:, None, None]).reshape(nb, block_size * block_size).to(dev)
        # 2) backward del generatore a chunk, accumulando i gradienti
        acc = [torch.zeros_like(p) for p in train_params]
        for i in range(0, nb, CH):
            sl = slice(i, min(i + CH, nb))
            gen.forward(bid[sl], tid[sl], lid[sl], cont[sl])
            gen.backward(dout[sl])
            for a, g in zip(acc, grads_fn()):
                a += g
        opt.step(acc)
        if step % max(1, steps // 8) == 0 or step == 1:
            logger.info("step %4d/%d  LM_loss=%.4f", step, steps, loss.item())

    logger.info("Perplexity originale: %.3f | ricostruito finale: %.3f", base, ppl_now())
    section(logger, "Provo un prompt (modello con pesi task-generati)")
    real_blocks = gen_blocks_cpu() * std[:, None, None] + mean[:, None, None]
    sd = reconstruct_state_dict(plan, real_blocks)
    params = dict(qwen.named_parameters())
    with torch.no_grad():
        for name, w in sd.items():
            if name in params and tuple(params[name].shape) == tuple(w.shape):
                params[name].data.copy_(w.to(params[name].dtype))
    from ..chat import _generate
    reply = _generate(qwen, tok, prompt, "cpu", max_new_tokens=70)
    print("\n=== RISPOSTA (pesi allenati per il COMPITO sul motore) ===\n" + reply.strip() + "\n")
    return {"ppl_original": round(base, 3), "ppl_reconstructed": round(ppl_now(), 3)}


def _gen_state(gen):
    """Stato serializzabile del generatore (adattatori + latent/codebook)."""
    st = {"type_W": gen.type_emb.W.detach().cpu(), "layer_W": gen.layer_emb.W.detach().cpu(),
          "in_proj_W": gen.in_proj.W.detach().cpu(), "in_proj_b": gen.in_proj.b.detach().cpu(),
          "head_W": gen.head.W.detach().cpu(), "head_b": gen.head.b.detach().cpu()}
    lat = gen.latent
    if hasattr(lat, "z"):                       # VQLatent
        st["z_W"] = lat.z.W.detach().cpu()
        st["C"] = lat.C.detach().cpu()
        if getattr(lat, "ema", False):
            st["ema_count"] = lat.ema_count.detach().cpu()
            st["ema_sum"] = lat.ema_sum.detach().cpu()
    else:                                       # Embedding semplice
        st["z_W"] = lat.W.detach().cpu()
    return st


def _load_gen_state(gen, st):
    def cp(dst, key):
        dst.copy_(st[key].to(dst.device))
    cp(gen.type_emb.W, "type_W"); cp(gen.layer_emb.W, "layer_W")
    cp(gen.in_proj.W, "in_proj_W"); cp(gen.in_proj.b, "in_proj_b")
    cp(gen.head.W, "head_W"); cp(gen.head.b, "head_b")
    lat = gen.latent
    if hasattr(lat, "z"):
        cp(lat.z.W, "z_W"); cp(lat.C, "C")
        if getattr(lat, "ema", False) and "ema_count" in st:
            cp(lat.ema_count, "ema_count"); cp(lat.ema_sum, "ema_sum")
    else:
        cp(lat.W, "z_W")


def _save_ckpt(path, gen, step, cfg):
    import os
    tmp = str(path) + ".tmp"                    # scrittura atomica: mai ckpt corrotti
    torch.save({"step": step, "state": _gen_state(gen), "cfg": cfg}, tmp)
    os.replace(tmp, str(path))


def run_task_engine(logger, model="qwen0.5b-instruct", device="auto",
                    include="layers.0.self_attn.q_proj", block_size=32, latent_dim=64,
                    steps=120, prompt="Cos'è la fotosintesi?", lr=1e-3, max_layers=-1,
                    dataset="", vq=0, batch=8, run_dir="runs/engine",
                    save_every=25, resume="", devices="", device_weights=""):
    """Task objective TUTTO sul 6750: generatore manuale + Qwen manuale (no autograd).
    Misura la perplexity su testo HELD-OUT (mai visto) = generalizzazione.
    Checkpoint ogni save_every step (i run multi-giorno sopravvivono ai crash)."""
    import re
    import time
    from transformers import AutoConfig
    from .qwen_model import QwenModel
    from .generator import build_ailo_generator

    model_id = resolve_model(model)
    rd = Path(run_dir)
    rd.mkdir(parents=True, exist_ok=True)
    section(logger, "FWE task (motore puro) — carico Qwen")
    hf, tok, _ = load_target_model(model_id, "cpu", torch.float32)
    c = AutoConfig.from_pretrained(model_id)
    cfg = GradusConfig(model=model_id, block=BlockConfig(block_size=block_size),
                       train=TrainConfig(include=include, max_layers=max_layers))
    plan = build_plan(hf, cfg)
    logger.info("Piano: %d tensori, %d blocchi", plan.num_tensors, plan.num_blocks)
    mean, std = _stats(hf, plan)
    feats = plan.features()
    from .multigpu import ShardedGenerator, measure_device_weights, resolve_devices

    # Multi-GPU: il device primario ospita anche il modello target, quindi e' il
    # primo della lista (con 'all' = quello con piu' VRAM).
    shard_devices = resolve_devices(devices, logger)
    if len(shard_devices) > 1:
        dev = shard_devices[0]
        label = str(dev)
        setup_device(label)                              # TF32/cudnn sul primario
        for d in shard_devices[1:]:
            setup_device(str(d))
    else:
        label, dev = setup_device(device)                # CUDA-first + TF32/cudnn
        shard_devices = []
    logger.info("Device: %s", device_summary(label))
    std_d = std.to(dev); mean_d = mean.to(dev)

    hp = model_hparams(c)
    logger.info("Architettura target: %d layer, hidden %d, GQA %d:%d, RoPE theta %.0f",
                hp["n_layers"], hp["hidden"], hp["n_heads"], hp["n_kv"], hp["theta"])
    qm = QwenModel(hp["hidden"], hp["n_layers"], hp["n_heads"], hp["n_kv"],
                   hp["inter"], hp["vocab"], dev, hp["eps"], hp["theta"]).load_hf(hf)

    def lin_for(name):
        m = re.search(r"layers\.(\d+)\.(self_attn|mlp)\.(\w+)_proj", name)
        L = qm.layers[int(m.group(1))]
        if m.group(2) == "self_attn":
            return {"q": L.attn.q, "k": L.attn.k, "v": L.attn.v, "o": L.attn.o}[m.group(3)]
        return {"gate": L.mlp.gate, "up": L.mlp.up, "down": L.mlp.down}[m.group(3)]
    target_lin = {e.name: lin_for(e.name) for e in plan.entries}

    bid_all = plan.block_ids()
    feats_all = (bid_all, feats["type_id"], feats["layer_id"], feats["cont"])

    def build_replica(target_dev):
        """Una replica del generatore + le coordinate dei blocchi, su `target_dev`."""
        replica = build_ailo_generator(plan, len(TENSOR_TYPES), block_size, target_dev,
                                       latent_dim=latent_dim, seq_len=4, vq_k=vq,
                                       logger=None)
        return replica, tuple(t.to(target_dev) for t in feats_all)

    sharded = None
    if len(shard_devices) > 1:
        from .multigpu import chunk_for_devices, probe_memory_per_block

        section(logger, f"Sharding del generatore su {len(shard_devices)} GPU")
        chunk_mg = int(os.environ.get("GRADUS_CHUNK") or 1024)

        # Il primario allochera' DOPO questo punto i buffer del modello target:
        # real_buf, gb (nb blocchi ciascuno) e W_buf, dW_acc (i pesi coperti).
        # Vanno sottratti dalla memoria disponibile, altrimenti la scheda grande
        # sembra la piu' libera e prende il chunk piu' grosso proprio mentre e'
        # l'unica che deve ancora ospitare quei GB.
        covered = sum(e.rows * e.cols for e in plan.entries)
        primary_reserve = (2 * plan.num_blocks * block_size * block_size + 2 * covered) * 4
        reserves = [primary_reserve] + [0] * (len(shard_devices) - 1)

        per_block = [probe_memory_per_block(build_replica, d) for d in shard_devices]
        shard_chunks = chunk_for_devices(shard_devices, chunk_mg,
                                         bytes_per_block=per_block, reserve_bytes=reserves)
        logger.info("Attivazioni: %s | buffer da riservare sul primario: %.1f GB",
                    ", ".join(f"{d}={b / 1024:.0f} KB/blocco" for d, b in zip(shard_devices, per_block)),
                    primary_reserve / 1024 ** 3)
        if device_weights:
            weights = [float(w) for w in str(device_weights).split(",")]
            total = sum(weights) or 1.0
            weights = [w / total for w in weights]
            logger.info("Pesi di ripartizione forniti: %s",
                        ", ".join(f"{w:.2f}" for w in weights))
        else:
            weights = measure_device_weights(build_replica, shard_devices,
                                             chunks=shard_chunks, logger=logger)
            logger.info("Pesi di ripartizione misurati: %s",
                        ", ".join(f"{d}={w:.2f}" for d, w in zip(shard_devices, weights)))
        sharded = ShardedGenerator(build_replica, feats_all, plan.num_blocks,
                                   shard_devices, weights, chunks=shard_chunks,
                                   logger=logger)
        gen = sharded.master
    else:
        gen = build_ailo_generator(plan, len(TENSOR_TYPES), block_size, dev,
                                   latent_dim=latent_dim, seq_len=4, vq_k=vq, logger=logger)
    logger.info("Generatore = AILO frozen | target = Qwen manuale | device=%s", label)
    if vq > 0:
        import math
        covered = sum(e.rows * e.cols for e in plan.entries)
        idx_bits = math.ceil(math.log2(vq))
        deploy_floats = vq * latent_dim + plan.num_blocks * idx_bits / 32.0
        logger.info("CODEBOOK VQ K=%d: deploy = %d atomi×%d + %d indici×%dbit = %.2fM float-eq | "
                    "compressione lato-latent %.1fx (pesi coperti %.2fM)",
                    vq, vq, latent_dim, plan.num_blocks, idx_bits,
                    deploy_floats / 1e6, covered / max(1.0, deploy_floats), covered / 1e6)
    bid = plan.block_ids().to(dev); tid = feats["type_id"].to(dev)
    lid = feats["layer_id"].to(dev); cont = feats["cont"].to(dev)
    nb = plan.num_blocks
    # Chunk di blocchi per passata del generatore. Su CUDA i chunk piccoli lasciano
    # la GPU sotto-occupata (kernel launch bound): con VRAM abbondante si sale.
    # Override con GRADUS_CHUNK per calibrare sulla propria scheda.
    CH = int(os.environ.get("GRADUS_CHUNK") or (1024 if is_cuda(label) else 256))

    def to_seqs(s, cap=None):
        ids = tok(s, return_tensors="pt").input_ids[0]
        Lt = 48
        seqs = [ids[i:i + Lt] for i in range(0, max(1, len(ids) - Lt), Lt)]
        seqs = [x for x in seqs if len(x) >= 8] or [ids[:Lt]]
        if cap:
            seqs = seqs[:cap]
        return torch.stack([torch.nn.functional.pad(x, (0, Lt - len(x)), value=tok.pad_token_id or 0) for x in seqs]).to(dev)

    if dataset.lower() == "wikitext":
        from ..modelio import load_hf_dataset
        ds = load_hf_dataset("wikitext", "wikitext-2-raw-v1")
        raw_tr = "\n".join(t for t in ds["train"]["text"] if len(t.strip()) > 40)
        raw_ev = "\n".join(t for t in ds["validation"]["text"] if len(t.strip()) > 40)
        text_tr, text_ev = to_seqs(raw_tr, cap=4000), to_seqs(raw_ev, cap=200)
        logger.info("Corpus wikitext: train %d seq, held-out %d seq", len(text_tr), len(text_ev))
    else:
        text_tr, text_ev = to_seqs(_TRAIN_TEXT), to_seqs(_EVAL_TEXT)

    @torch.no_grad()
    def loss_on(txt, mbs=4):
        # accumula sul device: una sola sincronizzazione host alla fine invece
        # di una per micro-batch (su held-out sono decine di sync per eval)
        tot = torch.zeros((), device=dev)
        n = 0
        for i in range(0, len(txt), mbs):
            b = txt[i:i + mbs]
            tot += qm.forward(b, b) * len(b); n += len(b)
        return (tot / max(1, n)).item()
    ev_eval = text_ev                 # held-out completo
    tr_eval = text_tr[:200]           # sottoinsieme di train (solo diagnostica)

    # perplexity coi pesi ORIGINALI (prima che il modello punti ai buffer generati)
    base_tr = float(torch.exp(torch.tensor(loss_on(tr_eval))).item())
    base_ev = float(torch.exp(torch.tensor(loss_on(ev_eval))).item())
    logger.info("Perplexity ORIGINALE: train %.2f | held-out %.2f", base_tr, base_ev)

    # ---- buffer riusati: zero allocazioni per step, VRAM sotto controllo (run lunghi) ----
    real_buf = torch.zeros(nb, block_size, block_size, device=dev)
    gb = torch.zeros(nb, block_size, block_size, device=dev)
    scale_buf = torch.empty(nb, device=dev)      # std/nmb riusato, zero allocazioni
    W_buf, dW_acc = {}, {}
    for e in plan.entries:
        W_buf[e.name] = torch.zeros(e.rows, e.cols, device=dev)
        dW_acc[e.name] = torch.zeros(e.rows, e.cols, device=dev)
        target_lin[e.name].W = W_buf[e.name]   # il modello punta ai buffer: fill in-place

    @torch.no_grad()
    def refresh_weights():
        """Genera tutti i blocchi (a chunk) e riempie i pesi del modello in-place."""
        if sharded is not None:
            sharded.refresh(real_buf, std_d, mean_d, block_size)
        else:
            for i in range(0, nb, CH):
                sl = slice(i, min(i + CH, nb))
                o = gen.forward(bid[sl], tid[sl], lid[sl], cont[sl]).reshape(-1, block_size, block_size)
                real_buf[sl] = o * std_d[sl][:, None, None] + mean_d[sl][:, None, None]
        for e in plan.entries:
            _assemble_matrix(real_buf[e.block_start:e.block_start + e.grid_r * e.grid_c],
                             e, block_size, out=W_buf[e.name])

    def ppl(txt):
        refresh_weights()
        return float(torch.exp(torch.tensor(loss_on(txt))).item())

    ckpt_path = rd / "engine_ckpt.pt"
    cfg_save = {"model": model_id, "include": include, "max_layers": max_layers,
                "block_size": block_size, "latent_dim": latent_dim, "vq": vq,
                "dataset": dataset, "lr": lr, "batch": batch}
    start_step = 1
    if resume:
        ck = torch.load(resume, map_location="cpu", weights_only=False)
        _load_gen_state(gen, ck["state"])
        # Il checkpoint entra nel MASTER: senza questa riga le repliche sui
        # worker restano allo stato iniziale non addestrato, e la loro fetta di
        # blocchi (qui il 32%) verrebbe generata da un generatore vergine.
        # Il loop le riallinea solo a fine step, quindi la ripresa perderebbe
        # terreno a ogni riavvio.
        if sharded is not None:
            sharded.sync_params()
        start_step = int(ck.get("step", 0)) + 1
        logger.info("RIPRESO da %s (%d step gia' fatti)", resume, start_step - 1)

    # La valutazione iniziale va DOPO la ripresa: prima misurerebbe il
    # generatore vergine anche quando si sta continuando un run.
    logger.info("Ricostruito %s: train %.2f | held-out %.2f",
                "al checkpoint" if resume else "iniziale", ppl(tr_eval), ppl(ev_eval))

    train_params = gen.adapter_params()
    opt = Adam(train_params, lr=lr)
    # accumulatore dei gradienti allocato UNA volta: nel loop originale veniva
    # ricreato a ogni step (churn dell'allocatore CUDA su run da migliaia di step)
    acc = [torch.zeros_like(p) for p in train_params]
    cuda = is_cuda(label)
    profiler = PhaseProfiler(os.environ.get("GRADUS_PROFILE") == "1",
                             dev if cuda else None)
    phase = profiler
    section(logger, f"Training task-fidelity TUTTO su '{label}' (Qwen manuale)")
    t0 = time.time()
    done = 0
    for step in range(start_step, steps + 1):
        phase("gen_forward")
        refresh_weights()                                    # genera + inietta (in-place, no alloc)
        for name in dW_acc:
            dW_acc[name].zero_()
        phase("qwen")
        mb = 2                                               # gradient accumulation
        nmb = 0
        for _ in range(0, max(mb, batch), mb):
            # indici generati sul device: indicizzare un tensore CUDA con indici CPU
            # costa una copia H2D sincrona a ogni micro-batch
            sel = torch.randint(0, len(text_tr), (min(mb, len(text_tr)),), device=dev)
            bb = text_tr[sel]
            loss = qm.forward(bb, bb)
            qm.backward()                                    # dL/dW nei .dW dei Linear target
            for e in plan.entries:
                dW_acc[e.name] += target_lin[e.name].dW
            nmb += 1
        phase("blockify")
        for e in plan.entries:
            n_e = e.grid_r * e.grid_c
            # niente `dW_acc / nmb`: allocherebbe una matrice per ognuno dei 168
            # tensori. La media dei micro-batch si fonde nello scaling qui sotto.
            _blockify_grad(dW_acc[e.name], e, block_size,
                           out=gb[e.block_start:e.block_start + n_e])
        gb.mul_(scale_buf.copy_(std_d).div_(nmb)[:, None, None])   # denorm + media, in-place
        dout = gb.reshape(nb, block_size * block_size)
        for a in acc:
            a.zero_()
        phase("gen_backward")
        if sharded is not None:
            sharded.backward(dout, acc)
        else:
            for i in range(0, nb, CH):
                sl = slice(i, min(i + CH, nb))
                gen.forward(bid[sl], tid[sl], lid[sl], cont[sl])
                gen.backward(dout[sl])
                grads = gen.adapter_grads()
                if cuda:
                    torch._foreach_add_(acc, grads)  # un kernel per l'intera lista
                else:
                    for a, g in zip(acc, grads):
                        a += g
        phase("optim")
        opt.step(acc)
        if vq > 0:
            gen.latent.ema_update(bid)               # codebook via EMA (chunked)
        if sharded is not None:
            sharded.sync_params()                    # ridistribuisce i pesi aggiornati
        phase(None)
        done += 1
        if step % 10 == 0 or step == start_step:
            vram = ""
            if cuda:
                # picco e riservato: se il riservato cresce mentre il picco resta
                # stabile, l'allocatore si sta frammentando
                vram = " | VRAM %.1f/%.1f GB" % (
                    torch.cuda.max_memory_allocated(dev) / 1024 ** 3,
                    torch.cuda.memory_reserved(dev) / 1024 ** 3)
            logger.info("step %5d/%d  LM_loss=%.4f  (%.1fs/step)%s%s",
                        step, steps, loss.item(), (time.time() - t0) / max(1, done),
                        vram, profiler.summary())
        if save_every and step % save_every == 0:
            _save_ckpt(ckpt_path, gen, step, cfg_save)
            logger.info("checkpoint -> %s (step %d)", ckpt_path, step)

    _save_ckpt(ckpt_path, gen, steps, cfg_save)

    fin_tr, fin_ev = ppl(tr_eval), ppl(ev_eval)
    logger.info("Ricostruito FINALE: train %.2f | held-out %.2f  (originale held-out %.2f)",
                fin_tr, fin_ev, base_ev)
    gap = "GENERALIZZA" if fin_ev <= base_ev * 1.15 else "non generalizza (held-out peggiore)"
    logger.info("Verdetto held-out: %s", gap)
    section(logger, "Provo un prompt")
    refresh_weights()
    sd = {name: W.detach().cpu() for name, W in W_buf.items()}
    params = dict(hf.named_parameters())
    with torch.no_grad():
        for name, w in sd.items():
            if name in params:
                params[name].data.copy_(w.to(params[name].dtype))
    from ..chat import _generate
    print("\n=== RISPOSTA (task sul motore puro, 6750) ===\n"
          + _generate(hf, tok, prompt, "cpu", max_new_tokens=70).strip() + "\n")
    return {"ppl_original_heldout": round(base_ev, 3), "ppl_reconstructed_heldout": round(fin_ev, 3),
            "ppl_train": round(fin_tr, 3), "ckpt": str(ckpt_path)}


def chat_from_ckpt(logger, ckpt, prompt, device="cpu", max_new_tokens=90):
    """Chatta col modello ricostruito da un checkpoint del motore (anche MENTRE
    un altro processo sta allenando: gira su CPU e legge solo il file)."""
    from .generator import build_ailo_generator
    ck = torch.load(ckpt, map_location="cpu", weights_only=False)
    c = ck["cfg"]
    logger.info("Checkpoint: %s (step %s) | modello %s", ckpt, ck.get("step"), c["model"])
    hf, tok, _ = load_target_model(c["model"], "cpu", torch.float32)
    gcfg = GradusConfig(model=c["model"], block=BlockConfig(block_size=c["block_size"]),
                        train=TrainConfig(include=c["include"], max_layers=c["max_layers"]))
    plan = build_plan(hf, gcfg)
    mean, std = _stats(hf, plan)
    feats = plan.features()
    _label, dev = setup_device(device)
    gen = build_ailo_generator(plan, len(TENSOR_TYPES), c["block_size"], dev,
                               latent_dim=c["latent_dim"], seq_len=4, vq_k=c["vq"], logger=logger)
    _load_gen_state(gen, ck["state"])
    nb, bs = plan.num_blocks, c["block_size"]
    bid = plan.block_ids().to(dev); tid = feats["type_id"].to(dev)
    lid = feats["layer_id"].to(dev); cont = feats["cont"].to(dev)
    std_d, mean_d = std.to(dev), mean.to(dev)
    logger.info("Genero %d blocchi dal checkpoint (qualche minuto su CPU)...", nb)
    blocks = torch.zeros(nb, bs, bs)
    with torch.no_grad():
        for i in range(0, nb, 256):
            sl = slice(i, min(i + 256, nb))
            o = gen.forward(bid[sl], tid[sl], lid[sl], cont[sl]).reshape(-1, bs, bs)
            blocks[sl] = (o * std_d[sl][:, None, None] + mean_d[sl][:, None, None]).cpu()
    sd = reconstruct_state_dict(plan, blocks)
    params = dict(hf.named_parameters())
    with torch.no_grad():
        for name, w in sd.items():
            if name in params:
                params[name].data.copy_(w.to(params[name].dtype))
    logger.info("Pesi iniettati (%d tensori). Genero la risposta...", len(sd))
    from ..chat import _generate
    reply = _generate(hf, tok, prompt, "cpu", max_new_tokens=max_new_tokens)
    print("\n=== CHAT (pesi dal checkpoint) ===\n" + reply.strip() + "\n")
    return reply


def run(logger, model="qwen0.5b-instruct", device="auto",
        include="layers.0.self_attn.q_proj", block_size=32, latent_dim=512,
        steps=600, prompt="Spiegami cos'è un buco nero in una frase.",
        ailo=False, freeze=False, lr=2e-3):
    model_id = resolve_model(model)
    section(logger, "FWE sul motore — carico il modello target")
    tgt_model, tok, _ = load_target_model(model_id, "cpu", torch.float32)

    cfg = GradusConfig(model=model_id, block=BlockConfig(block_size=block_size),
                       train=TrainConfig(include=include))
    plan = build_plan(tgt_model, cfg)
    logger.info("Piano: %d tensori, %d blocchi (bs=%d)", plan.num_tensors, plan.num_blocks, block_size)
    if plan.num_blocks == 0:
        raise RuntimeError("Nessun blocco — controlla --include")

    targets = materialize_targets(tgt_model, plan)         # (nb,bs,bs) cpu
    mean, std = _stats(tgt_model, plan)
    targets_norm = (targets - mean[:, None, None]) / std[:, None, None]
    feats = plan.features()

    # ---- training del generatore sul device (il nostro motore) ----
    label, dev = setup_device(device)
    logger.info("Device: %s", device_summary(label))
    section(logger, f"Alleno il generatore (motore manuale) su device='{label}'")
    if ailo:
        from .generator import build_ailo_generator
        gen = build_ailo_generator(plan, len(TENSOR_TYPES), block_size, dev,
                                   latent_dim=latent_dim, seq_len=4, logger=logger)
        logger.info("Decoder = AILO PRETRAINED (12x768)%s", " [CONGELATO]" if freeze else "")
    else:
        gen = ManualGenerator(plan.num_blocks, len(TENSOR_TYPES), plan.num_layers, block_size, dev,
                              latent_dim=latent_dim, d_model=128, n_layers=4, n_heads=4,
                              inter=256, seq_len=4)
    tn = targets_norm.reshape(plan.num_blocks, -1).to(dev)
    bid_all = plan.block_ids().to(dev)
    tid = feats["type_id"].to(dev); lid = feats["layer_id"].to(dev); cont = feats["cont"].to(dev)
    train_params = gen.adapter_params() if freeze else gen.params()
    opt = Adam(train_params, lr=lr)
    for step in range(1, steps + 1):
        idx = torch.randint(0, plan.num_blocks, (min(256, plan.num_blocks),), device=dev)
        pred = gen.forward(bid_all[idx], tid[idx], lid[idx], cont[idx])
        loss, dpred = mse_loss(pred, tn[idx])
        gen.backward(dpred)
        opt.step(gen.adapter_grads() if freeze else gen.grads())
        if step % max(1, steps // 8) == 0 or step == 1:
            logger.info("step %4d/%d  loss=%.5f", step, steps, loss.item())

    # ---- ricostruzione dei pesi ----
    section(logger, "Ricostruisco i pesi dal generatore")
    with torch.no_grad():
        chunks = []
        for i in range(0, plan.num_blocks, 1024):          # batch: evita OOM su GPU
            sl = slice(i, min(i + 1024, plan.num_blocks))
            p = gen.forward(bid_all[sl], tid[sl], lid[sl], cont[sl])
            chunks.append(p.reshape(-1, block_size, block_size).cpu())
        out = torch.cat(chunks, 0)
        out = out * std[:, None, None] + mean[:, None, None]
    cos = _cosine(out, targets)
    logger.info("Cosine pesi ricostruiti vs originali: %.4f", cos)
    sd = reconstruct_state_dict(plan, out)

    # ---- iniezione + prova prompt ----
    section(logger, "Inietto i pesi generati e provo un prompt")
    params = dict(tgt_model.named_parameters())
    with torch.no_grad():
        for name, w in sd.items():
            if name in params and tuple(params[name].shape) == tuple(w.shape):
                params[name].data.copy_(w.to(params[name].dtype))
    logger.info("Tensori sostituiti: %d/%d", len(sd), plan.num_tensors)

    from ..chat import _generate
    reply = _generate(tgt_model, tok, prompt, "cpu", max_new_tokens=80)
    logger.info("PROMPT: %s", prompt)
    print("\n=== RISPOSTA (modello con q_proj rigenerata da AILO sul motore) ===\n"
          + reply.strip() + "\n")
    return {"cosine": cos, "device": label, "blocks": plan.num_blocks}
