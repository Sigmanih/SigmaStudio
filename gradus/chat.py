"""Chat interattiva col modello — originale o ricostruito dal generatore."""
from __future__ import annotations

import logging
from pathlib import Path

import torch

from .config import pick_device, torch_device
from .modelio import load_target_model


def _to_input_ids(encoded):
    """Normalizza l'output del tokenizer in un tensore di input_ids.

    transformers 5.x fa restituire ad `apply_chat_template` un BatchEncoding
    (dict-like) anche con return_tensors='pt'; nelle 4.x era un tensore nudo.
    `model.generate()` vuole il tensore.
    """
    if hasattr(encoded, "keys") and "input_ids" in encoded:
        return encoded["input_ids"]
    return encoded


def _generate(model, tok, prompt: str, device, max_new_tokens: int = 200) -> str:
    dev = torch_device(device) if isinstance(device, str) else device
    if hasattr(tok, "apply_chat_template") and tok.chat_template:
        msgs = [{"role": "user", "content": prompt}]
        ids = _to_input_ids(tok.apply_chat_template(
            msgs, add_generation_prompt=True, return_tensors="pt")).to(dev)
    else:
        ids = _to_input_ids(tok(prompt, return_tensors="pt")).to(dev)
    with torch.no_grad():
        out = model.generate(
            ids, attention_mask=torch.ones_like(ids),
            max_new_tokens=max_new_tokens, do_sample=True,
            temperature=0.7, top_p=0.9,
            pad_token_id=tok.pad_token_id or tok.eos_token_id,
        )
    return tok.decode(out[0, ids.shape[1]:], skip_special_tokens=True)


def chat(model_id: str, ckpt_path: Path | None, device: str,
         logger: logging.Logger, prompt: str | None = None) -> None:
    dev = pick_device(device)
    if ckpt_path:
        from .reconstruct import load_reconstructed_model
        logger.info("Carico modello RICOSTRUITO da %s", ckpt_path)
        model, tok, dev, _plan = load_reconstructed_model(model_id, ckpt_path, device=dev, logger=logger)
    else:
        logger.info("Carico modello ORIGINALE %s", model_id)
        model, tok, dev = load_target_model(model_id, dev, torch.float32)

    if prompt:
        reply = _generate(model, tok, prompt, dev)
        logger.info("PROMPT: %s", prompt)
        print("\n" + reply + "\n")
        return

    print("Chat Gradus — scrivi 'exit' per uscire.\n")
    while True:
        try:
            user = input("tu> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if user.lower() in {"exit", "quit", ":q"}:
            break
        if not user:
            continue
        reply = _generate(model, tok, user, dev)
        print(f"ai> {reply}\n")
