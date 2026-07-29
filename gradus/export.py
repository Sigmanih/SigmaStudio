"""Da checkpoint del generatore a modello HuggingFace utilizzabile.

Un run FWE non produce un modello: produce il **generatore** dei pesi
(`engine_ckpt.pt`, decoder AILO congelato + adattatori + codebook VQ). Per
usarlo altrove — Ollama, llama.cpp, transformers — i pesi vanno prima
*materializzati*: si rigenerano tutti i blocchi, si ricompongono le matrici e si
iniettano nel modello target, che a quel punto è un normale modello HF.

È il passaggio che rende concreta la compressione: si distribuiscono ~0.5 MB di
codebook e indici, e il modello si ricostruisce a destinazione.
"""
from __future__ import annotations

from pathlib import Path

import torch

from .config import GradusConfig, BlockConfig, TrainConfig, setup_device
from .modelio import TENSOR_TYPES, build_plan, load_target_model


def reconstruct_to_hf(ckpt_path, out_dir, device="auto", logger=None, chunk=256):
    """Rigenera i pesi da un checkpoint FWE e salva un modello HF completo.

    Ritorna un dizionario con il percorso del modello e i metadati del run.
    """
    from .engine.fwe import _stats, _assemble_matrix, _load_gen_state
    from .engine.generator import build_ailo_generator

    ckpt_path, out_dir = Path(ckpt_path), Path(out_dir)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"Checkpoint non trovato: {ckpt_path}")

    def log(msg, *args):
        if logger:
            logger.info(msg, *args)
        else:
            print("[GRADUS] " + (msg % args if args else msg), flush=True)

    ck = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    cfg = ck["cfg"]
    step = ck.get("step")
    log("Checkpoint step %s | modello %s | include=%s | VQ K=%s",
        step, cfg["model"], cfg["include"], cfg.get("vq"))

    hf, tok, _ = load_target_model(cfg["model"], "cpu", torch.float32)
    gcfg = GradusConfig(model=cfg["model"],
                        block=BlockConfig(block_size=cfg["block_size"]),
                        train=TrainConfig(include=cfg["include"],
                                          max_layers=cfg["max_layers"]))
    plan = build_plan(hf, gcfg)
    mean, std = _stats(hf, plan)
    feats = plan.features()

    _label, dev = setup_device(device)
    gen = build_ailo_generator(plan, len(TENSOR_TYPES), cfg["block_size"], dev,
                               latent_dim=cfg["latent_dim"], seq_len=4,
                               vq_k=cfg["vq"], logger=logger)
    _load_gen_state(gen, ck["state"])

    bs, nb = cfg["block_size"], plan.num_blocks
    bid = plan.block_ids().to(dev)
    tid = feats["type_id"].to(dev)
    lid = feats["layer_id"].to(dev)
    cont = feats["cont"].to(dev)
    std_d, mean_d = std.to(dev), mean.to(dev)

    log("Rigenero %d blocchi da %d tensori...", nb, plan.num_tensors)
    blocks = torch.zeros(nb, bs, bs)
    with torch.no_grad():
        for i in range(0, nb, chunk):
            sl = slice(i, min(i + chunk, nb))
            out = gen.forward(bid[sl], tid[sl], lid[sl], cont[sl]).reshape(-1, bs, bs)
            blocks[sl] = (out * std_d[sl][:, None, None] + mean_d[sl][:, None, None]).cpu()

    params = dict(hf.named_parameters())
    replaced = 0
    with torch.no_grad():
        for e in plan.entries:
            W = _assemble_matrix(blocks[e.block_start:e.block_start + e.grid_r * e.grid_c],
                                 e, bs)
            if e.name in params:
                params[e.name].data.copy_(W.to(params[e.name].dtype))
                replaced += 1
    log("Pesi sostituiti: %d tensori su %d del piano", replaced, plan.num_tensors)

    health = check_fp16_safety(hf, tok, log)

    out_dir.mkdir(parents=True, exist_ok=True)
    hf.save_pretrained(out_dir, safe_serialization=True)
    tok.save_pretrained(out_dir)
    _restore_legacy_chat_template(out_dir, tok, log)
    log("Modello ricostruito salvato in %s", out_dir)

    return {
        "success": True,
        "model_dir": str(out_dir),
        "base_model": cfg["model"],
        "step": step,
        "tensors_replaced": replaced,
        "num_blocks": nb,
        "vq": cfg.get("vq"),
        **health,
    }


FP16_MAX = 65504.0


def check_fp16_safety(model, tok, log=print) -> dict:
    """Il modello ricostruito sopravvive alla mezza precisione?

    Serve perché la destinazione tipica (GGUF/Ollama) converte in F16. Un
    generatore poco addestrato produce pesi che gonfiano le attivazioni ben
    oltre il massimo rappresentabile (65504): il modello *sembra* esportato
    correttamente e poi in inferenza restituisce NaN, cioè token ripetuti.
    """
    try:
        ids = tok("The history of", return_tensors="pt").input_ids
        with torch.no_grad():
            out = model(ids, output_hidden_states=True)
        peak = max(h.abs().max().item() for h in out.hidden_states)
    except Exception as exc:                                   # pragma: no cover
        log("Controllo fp16 non eseguibile: %s", exc)
        return {"fp16_safe": None, "max_activation": None}

    safe = peak < FP16_MAX
    if safe:
        log("Attivazioni max %.3e: compatibili con fp16 (limite %.2e)", peak, FP16_MAX)
    else:
        log("ATTENZIONE: attivazioni max %.3e, oltre il limite fp16 (%.2e). "
            "In F16 — la conversione usata da Ollama/GGUF — il modello produrrà "
            "NaN e testo degenere. Serve fp32/bf16, oppure un generatore più "
            "addestrato.", peak, FP16_MAX)
    return {"fp16_safe": safe, "max_activation": peak}


def _restore_legacy_chat_template(out_dir, tok, log=print) -> None:
    """Riporta il chat template dentro tokenizer_config.json.

    transformers 5 lo salva in `chat_template.jinja`, ma i convertitori GGUF lo
    cercano ancora nel tokenizer_config: senza, Ollama importa il modello come
    sola 'completion' e non applica alcun formato conversazionale.
    """
    import json

    template = getattr(tok, "chat_template", None)
    if not template:
        return
    config = Path(out_dir) / "tokenizer_config.json"
    if not config.exists():
        return
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
        if data.get("chat_template"):
            return
        data["chat_template"] = template
        config.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        log("Chat template riportato in tokenizer_config.json (per i convertitori GGUF)")
    except Exception as exc:                                   # pragma: no cover
        log("Chat template non ripristinato: %s", exc)
