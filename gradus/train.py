"""Allenamento del generatore. Due obiettivi:

  objective="weight"  -> ricostruire i pesi (MSE mascherata, normalizzata per-tensore).
  objective="task"    -> mantenere la PERPLEXITY: i pesi generati vengono iniettati nel
                         modello (functional_call, differenziabile) e si minimizza la
                         loss del linguaggio. E' la via per la compressione "utile":
                         non servono pesi identici, serve un modello che funziona.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import torch

from .config import GradusConfig, torch_device
from .generator import build_generator, count_params
from .logging_utils import section
from .modelio import (
    TENSOR_TYPES,
    build_plan,
    load_target_model,
    materialize_targets,
    plan_summary,
)

# Corpus interno di fallback per objective=task (frasi distinte, così train/held-out
# non si sovrappongono). Per misure serie usare --dataset wikitext (HF datasets).
_TASK_CORPUS = (
    "L'intelligenza artificiale impara a prevedere la parola successiva dal contesto. "
    "I modelli linguistici sono reti neurali profonde addestrate su grandi quantita' di testo. "
    "Gradus genera i pesi di un modello invece di memorizzarli esplicitamente. "
    "The quick brown fox jumps over the lazy dog while the sun sets behind the hills. "
    "Le matrici di peso di un transformer codificano la conoscenza appresa nel training. "
    "Un buon modello generalizza a frasi mai viste mantenendo bassa la perplexity. "
    "La citta' di Roma sorge sulle rive del fiume Tevere nel centro Italia. "
    "Gli oceani coprono gran parte della superficie del nostro pianeta azzurro. "
    "La fotosintesi converte la luce del sole in energia chimica nelle piante verdi. "
    "Le stelle nascono dal collasso gravitazionale di enormi nubi di gas e polvere. "
    "Un algoritmo e' una sequenza finita di istruzioni per risolvere un problema. "
    "La musica combina ritmo, melodia e armonia per esprimere emozioni profonde. "
    "Il caffe' del mattino aiuta molte persone a iniziare la giornata con energia. "
    "Le montagne piu' alte del mondo si trovano nella catena dell'Himalaya in Asia. "
    "Imparare una lingua nuova apre le porte a culture e modi di pensare diversi. "
    "La memoria di un computer conserva dati e istruzioni durante l'esecuzione."
)


def _load_text_sequences(tok, cfg, dev):
    """Ritorna (train_text, eval_text) come tensori (n, L), con split held-out.
    L'eval e' su testo NON usato in training => misura la generalizzazione."""
    L = cfg.train.text_len
    raw_train, raw_eval = None, None
    if cfg.train.dataset.lower() == "wikitext":
        try:
            from .modelio import load_hf_dataset
            ds = load_hf_dataset("wikitext", "wikitext-2-raw-v1")
            raw_train = "\n".join(t for t in ds["train"]["text"] if t.strip())
            raw_eval = "\n".join(t for t in ds["validation"]["text"] if t.strip())
        except Exception as e:
            raw_train = None  # fallback sotto
            _wt_err = str(e)[:80]
    if raw_train is None:
        # fallback: corpus interno, split 75/25 a livello di frase
        sents = [s.strip() + " " for s in _TASK_CORPUS.split(". ") if s.strip()]
        cut = max(1, int(len(sents) * 0.75))
        raw_train = "".join(sents[:cut])
        raw_eval = "".join(sents[cut:]) or raw_train

    def chunk(text, limit_seqs):
        ids = tok(text, return_tensors="pt").input_ids[0]
        seqs = [ids[i:i + L] for i in range(0, max(1, len(ids) - L), L)]
        seqs = [s for s in seqs if len(s) >= 8][:limit_seqs] or [ids[:L]]
        pad = tok.pad_token_id or 0
        return torch.stack([torch.nn.functional.pad(s, (0, L - len(s)), value=pad) for s in seqs])

    train_text = chunk(raw_train, 2048).to(dev)
    eval_text = chunk(raw_eval, 256).to(dev)
    return train_text, eval_text


def _per_tensor_stats(model, plan) -> tuple[torch.Tensor, torch.Tensor]:
    """mean/std per blocco, calcolati sui pesi VERI (no padding)."""
    params = dict(model.named_parameters())
    mean = torch.zeros(plan.num_blocks)
    std = torch.ones(plan.num_blocks)
    for e in plan.entries:
        w = params[e.name].detach().float()
        m = w.mean().item()
        s = w.std().item()
        s = s if s > 1e-8 else 1.0
        n_blocks = e.grid_r * e.grid_c
        mean[e.block_start : e.block_start + n_blocks] = m
        std[e.block_start : e.block_start + n_blocks] = s
    return mean, std


def _build_mask(vr: torch.Tensor, vc: torch.Tensor, bs: int) -> torch.Tensor:
    ar = torch.arange(bs, device=vr.device)
    rmask = (ar[None, :] < vr[:, None]).float()
    cmask = (ar[None, :] < vc[:, None]).float()
    return rmask[:, :, None] * cmask[:, None, :]


def _assemble_tensor(blocks_real: torch.Tensor, e, bs: int) -> torch.Tensor:
    """(grid_r*grid_c, bs, bs) reali -> matrice (rows, cols), differenziabile."""
    gr, gc = e.grid_r, e.grid_c
    m = blocks_real.view(gr, gc, bs, bs).permute(0, 2, 1, 3).reshape(gr * bs, gc * bs)
    return m[: e.rows, : e.cols]


@torch.no_grad()
def _cosine_sample(gen, feats, targets_norm, mean, std, vr, vc, bs, dev, n=128):
    nb = targets_norm.shape[0]
    n = min(n, nb)
    sel = torch.randperm(nb)[:n]
    pred = gen(sel.to(dev), feats["type_id"][sel].to(dev),
               feats["layer_id"][sel].to(dev), feats["cont"][sel].to(dev)).cpu()
    pred = pred * std[sel][:, None, None] + mean[sel][:, None, None]
    tgt = targets_norm[sel] * std[sel][:, None, None] + mean[sel][:, None, None]
    mask = _build_mask(vr[sel], vc[sel], bs)
    cos = []
    for i in range(n):
        a = (pred[i] * mask[i]).flatten()
        b = (tgt[i] * mask[i]).flatten()
        d = a.norm() * b.norm()
        if d > 0:
            cos.append((a @ b / d).item())
    return sum(cos) / max(1, len(cos))


def _setup(cfg: GradusConfig, logger):
    section(logger, "Carico modello target")
    model, tok, dev = load_target_model(cfg.model, cfg.device, cfg.torch_dtype())
    gen_dev = torch_device(dev)
    logger.info("Modello: %s | device: %s | obiettivo: %s", cfg.model, dev, cfg.train.objective)

    section(logger, "Costruisco il piano dei blocchi")
    plan = build_plan(model, cfg)
    summ = plan_summary(plan)
    logger.info("Piano: %s", summ)
    if plan.num_blocks == 0:
        raise RuntimeError("Nessun blocco selezionato — controlla i filtri (include/max_layers).")
    tset = sorted({TENSOR_TYPES[e.ttype] for e in plan.entries})
    logger.info("Tipi coperti: %s | layer distinti: %d", tset, len({e.layer for e in plan.entries}))

    section(logger, "Estraggo target e statistiche")
    targets = materialize_targets(model, plan)
    mean, std = _per_tensor_stats(model, plan)
    feats = plan.features()

    section(logger, "Costruisco il generatore")
    gen = build_generator(cfg.generator.kind, plan.num_blocks, plan.block_size,
                          len(TENSOR_TYPES), plan.num_layers, cfg.generator).to(gen_dev)
    n_total = count_params(gen)
    logger.info("Generatore '%s': %.2fM params (allenabili %.2fM)%s",
                cfg.generator.kind, n_total / 1e6, count_params(gen, True) / 1e6,
                "  [BACKBONE CONGELATO]" if cfg.generator.freeze_backbone else "")
    ratio = summ["params_covered"] / max(1, n_total)
    logger.info("Compressione potenziale: %.2fx (target %.2fM / generatore %.2fM)",
                ratio, summ["params_covered_M"], n_total / 1e6)
    opt = torch.optim.AdamW([p for p in gen.parameters() if p.requires_grad],
                            lr=cfg.train.lr, weight_decay=cfg.train.weight_decay)
    return model, tok, dev, gen_dev, plan, targets, mean, std, feats, gen, opt, summ, n_total


def _save(cfg, run_dir, gen, plan, mean, std, history, summ):
    ckpt_path = run_dir / "generator.pt"
    torch.save({"generator_state": gen.state_dict(), "plan": plan.to_dict(),
                "mean": mean, "std": std, "kind": cfg.generator.kind,
                "generator_cfg": cfg.generator.__dict__}, ckpt_path)
    cfg.to_json(run_dir / "config.json")
    (run_dir / "history.json").write_text(json.dumps(history, indent=2), encoding="utf-8")
    (run_dir / "plan_summary.json").write_text(json.dumps(summ, indent=2), encoding="utf-8")
    return ckpt_path


def train(cfg: GradusConfig, run_dir: Path, logger: logging.Logger) -> dict:
    torch.manual_seed(cfg.train.seed)
    (model, tok, dev, gen_dev, plan, targets, mean, std, feats,
     gen, opt, summ, n_total) = _setup(cfg, logger)
    if cfg.train.objective == "task":
        return _train_task(cfg, run_dir, logger, model, tok, dev, gen_dev, plan,
                           targets, mean, std, feats, gen, opt, summ, n_total)
    return _train_weight(cfg, run_dir, logger, model, dev, gen_dev, plan,
                         targets, mean, std, feats, gen, opt, summ, n_total)


# --------------------------------------------------------------------------- weight
def _train_weight(cfg, run_dir, logger, model, dev, gen_dev, plan, targets,
                  mean, std, feats, gen, opt, summ, n_total):
    targets_norm = (targets - mean[:, None, None]) / std[:, None, None]
    vr, vc = plan.valid_dims()
    bs = plan.block_size
    block_ids = plan.block_ids()
    del model
    if dev == "cuda":
        torch.cuda.empty_cache()

    section(logger, "Training (objective=weight)")
    history, best_cos = [], -1.0
    for step in range(1, cfg.train.steps + 1):
        idx = torch.randint(0, plan.num_blocks, (cfg.train.batch_blocks,))
        pred = gen(idx.to(gen_dev), feats["type_id"][idx].to(gen_dev),
                   feats["layer_id"][idx].to(gen_dev), feats["cont"][idx].to(gen_dev))
        tgt = targets_norm[idx].to(gen_dev)
        mask = _build_mask(vr[idx].to(gen_dev), vc[idx].to(gen_dev), bs)
        loss = ((pred - tgt) ** 2 * mask).sum() / mask.sum().clamp_min(1.0)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 50 == 0 or step == 1:
            logger.info("step %5d/%d  loss=%.5f", step, cfg.train.steps, loss.item())
        if step % cfg.train.eval_every == 0 or step == cfg.train.steps:
            cos = _cosine_sample(gen, feats, targets_norm, mean, std, vr, vc, bs, gen_dev)
            best_cos = max(best_cos, cos)
            logger.info("  [eval] cosine medio = %.4f", cos)
            history.append({"step": step, "loss": loss.item(), "cosine": cos})

    section(logger, "Salvo checkpoint")
    ckpt = _save(cfg, run_dir, gen, plan, mean, std, history, summ)
    logger.info("Checkpoint: %s", ckpt)
    return {"ckpt": str(ckpt), "objective": "weight",
            "final_cosine": history[-1]["cosine"] if history else None,
            "best_cosine": round(best_cos, 4), "summary": summ,
            "generator_params_M": round(n_total / 1e6, 2)}


# ----------------------------------------------------------------------------- task
def _train_task(cfg, run_dir, logger, model, tok, dev, gen_dev, plan, targets,
                mean, std, feats, gen, opt, summ, n_total):
    from torch.func import functional_call

    # il modello target e' CONGELATO: alleniamo solo il generatore
    model.requires_grad_(False)
    mean_d = mean.to(gen_dev); std_d = std.to(gen_dev)
    all_ids = plan.block_ids().to(gen_dev)
    tid = feats["type_id"].to(gen_dev)
    lid = feats["layer_id"].to(gen_dev)
    cont = feats["cont"].to(gen_dev)
    bs = plan.block_size
    dtype = cfg.torch_dtype()

    # dataset testo -> train / held-out (eval su testo mai visto = generalizzazione)
    train_text, eval_text = _load_text_sequences(tok, cfg, gen_dev)
    src = cfg.train.dataset or "corpus-interno"
    logger.info("Testo (%s): train %d seq, held-out %d seq (L=%d)",
                src, len(train_text), len(eval_text), cfg.train.text_len)

    @torch.no_grad()
    def ppl_on(txt):
        return float(torch.exp(model(input_ids=txt, labels=txt).loss).item())
    base_train = ppl_on(train_text)
    base_eval = ppl_on(eval_text)
    logger.info("Perplexity originale: train %.3f | held-out %.3f", base_train, base_eval)

    def gen_overrides():
        out = gen(all_ids, tid, lid, cont)                       # (Nb,bs,bs) norm
        out = out * std_d[:, None, None] + mean_d[:, None, None]  # reali
        ov = {}
        for e in plan.entries:
            blk = out[e.block_start: e.block_start + e.grid_r * e.grid_c]
            ov[e.name] = _assemble_tensor(blk, e, bs).to(dtype)
        return ov

    section(logger, "Training (objective=task — mantieni la perplexity)")
    history, best_ppl = [], float("inf")
    for step in range(1, cfg.train.steps + 1):
        ov = gen_overrides()
        batch = train_text[torch.randint(0, len(train_text), (min(4, len(train_text)),))]
        out = functional_call(model, ov, args=(), kwargs={"input_ids": batch, "labels": batch})
        loss = out.loss
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 20 == 0 or step == 1:
            logger.info("step %5d/%d  LM_loss=%.4f  ppl_train=%.3f",
                        step, cfg.train.steps, loss.item(), float(torch.exp(loss).item()))
        if step % cfg.train.eval_every == 0 or step == cfg.train.steps:
            with torch.no_grad():
                ov = gen_overrides()
                full = functional_call(model, ov, args=(), kwargs={"input_ids": eval_text, "labels": eval_text})
                ppl = float(torch.exp(full.loss).item())
            best_ppl = min(best_ppl, ppl)
            logger.info("  [eval] perplexity HELD-OUT ricostruito = %.3f (originale %.3f)", ppl, base_eval)
            history.append({"step": step, "lm_loss": loss.item(), "ppl_heldout": ppl})

    section(logger, "Salvo checkpoint")
    ckpt = _save(cfg, run_dir, gen, plan, mean, std, history, summ)
    logger.info("Checkpoint: %s", ckpt)
    return {"ckpt": str(ckpt), "objective": "task",
            "ppl_original_heldout": round(base_eval, 3),
            "final_ppl_heldout": history[-1]["ppl_heldout"] if history else None,
            "best_ppl_heldout": round(best_ppl, 3), "summary": summ,
            "generator_params_M": round(n_total / 1e6, 2)}
