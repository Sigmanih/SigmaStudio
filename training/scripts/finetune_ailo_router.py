#!/usr/bin/env python3
"""
finetune_ailo_router.py — Fine-tune Ailo-152M as Sigma Router
==============================================================
Fine-tunes xxrickyxx/ailo-152m on the sigma_intent_dataset.jsonl
using LoRA (PEFT) for intent classification.

Requirements:
    pip install transformers>=4.40 peft>=0.10 trl>=0.8 datasets accelerate

CPU-only:  ~30-60 min, ~2GB RAM
GPU (opt): ~3-5 min, ~4GB VRAM

Usage:
    python training/scripts/finetune_ailo_router.py
    python training/scripts/finetune_ailo_router.py --dry-run
    python training/scripts/finetune_ailo_router.py --epochs 3 --gpu
"""

import os
import sys
import json
import time
import argparse
import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

BASE_DIR     = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = BASE_DIR / "training" / "datasets" / "sigma_intent_dataset.jsonl"
OUTPUT_DIR   = BASE_DIR / "training" / "jobs" / "sigma-router-ailo"
LOG_PATH     = OUTPUT_DIR / "training.log"

BASE_MODEL   = "xxrickyxx/ailo-152m"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sigma.finetune")


# ---------------------------------------------------------------------------
# Dependency check
# ---------------------------------------------------------------------------

def check_deps(dry_run: bool = False):
    missing = []
    for pkg in ["transformers", "peft", "trl", "datasets", "accelerate"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        log.error("Missing packages: %s", ", ".join(missing))
        log.error("Install with: pip install %s", " ".join(missing))
        if not dry_run:
            sys.exit(1)
        return False
    return True


def check_dataset():
    if not DATASET_PATH.exists():
        log.error("Dataset not found: %s", DATASET_PATH)
        log.error("Run first: python training/scripts/generate_sigma_intent_dataset.py")
        sys.exit(1)
    with open(DATASET_PATH, encoding="utf-8") as f:
        n = sum(1 for _ in f)
    log.info("Dataset: %d examples at %s", n, DATASET_PATH)
    return n


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_for_sft(example: dict) -> dict:
    """Convert messages list → single 'text' field for SFTTrainer."""
    msgs = example.get("messages", [])
    parts = []
    for m in msgs:
        role = m.get("role", "")
        content = m.get("content", "")
        if role == "system":
            parts.append(f"<|system|>\n{content}<|end|>")
        elif role == "user":
            parts.append(f"<|user|>\n{content}<|end|>")
        elif role == "assistant":
            parts.append(f"<|assistant|>\n{content}<|end|>")
    return {"text": "\n".join(parts)}


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def run_training(args):
    log.info("=" * 60)
    log.info("  Sigma Router — Ailo-152M Fine-Tuning")
    log.info("=" * 60)
    log.info("Base model : %s", BASE_MODEL)
    log.info("Dataset    : %s", DATASET_PATH)
    log.info("Output     : %s", OUTPUT_DIR)
    log.info("Epochs     : %d", args.epochs)
    log.info("GPU        : %s", "yes" if args.gpu else "no (CPU-only)")
    log.info("Dry-run    : %s", "yes" if args.dry_run else "no")
    log.info("=" * 60)

    if args.dry_run:
        log.info("✅ Dry-run complete. All checks passed. Ready to train.")
        return

    # --- Imports (after dep check) ---
    import torch
    from datasets import load_dataset
    from transformers import (
        AutoTokenizer,
        AutoModelForCausalLM,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, TaskType
    from trl import SFTTrainer, SFTConfig

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    device = "cuda" if (args.gpu and torch.cuda.is_available()) else "cpu"
    log.info("Device: %s", device.upper())
    if args.gpu and device == "cpu":
        log.warning("GPU requested but CUDA not available, falling back to CPU")

    # --- Load tokenizer ---
    log.info("Loading tokenizer from %s ...", BASE_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    # --- Load model ---
    log.info("Loading model %s ...", BASE_MODEL)
    load_kwargs = {
        "trust_remote_code": True,
        "torch_dtype": torch.float32 if device == "cpu" else torch.float16,
    }
    if device == "cpu":
        load_kwargs["low_cpu_mem_usage"] = True
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, **load_kwargs)

    # --- LoRA config ---
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=16,                        # rank — small enough for 152M
        lora_alpha=32,
        target_modules=["q_proj", "v_proj"],  # attention projections
        lora_dropout=0.05,
        bias="none",
        inference_mode=False,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # --- Load dataset ---
    log.info("Loading dataset ...")
    raw_ds = load_dataset("json", data_files=str(DATASET_PATH), split="train")
    raw_ds = raw_ds.map(format_for_sft, remove_columns=raw_ds.column_names)

    # Train/eval split (90/10)
    split = raw_ds.train_test_split(test_size=0.1, seed=42)
    train_ds = split["train"]
    eval_ds  = split["test"]
    log.info("Train: %d, Eval: %d", len(train_ds), len(eval_ds))

    # --- Training args ---
    sft_config = SFTConfig(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=4 if device == "cuda" else 2,
        per_device_eval_batch_size=2,
        gradient_accumulation_steps=4 if device == "cpu" else 2,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        max_seq_length=256,          # router outputs are short
        logging_steps=20,
        save_steps=100,
        eval_strategy="steps",
        eval_steps=100,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        report_to="none",            # no wandb
        fp16=(device == "cuda"),
        bf16=False,
        dataloader_num_workers=0,
        optim="adamw_torch",
        save_total_limit=2,
        dataset_text_field="text",
    )

    # --- Trainer ---
    trainer = SFTTrainer(
        model=model,
        args=sft_config,
        train_dataset=train_ds,
        eval_dataset=eval_ds,
        tokenizer=tokenizer,
    )

    # --- Train ---
    log.info("🚀 Starting training...")
    t0 = time.time()
    trainer.train()
    elapsed = time.time() - t0
    log.info("✅ Training complete in %.0f seconds (%.1f min)", elapsed, elapsed / 60)

    # --- Save adapter ---
    adapter_path = OUTPUT_DIR / "lora_adapter"
    trainer.model.save_pretrained(str(adapter_path))
    tokenizer.save_pretrained(str(adapter_path))
    log.info("LoRA adapter saved → %s", adapter_path)

    # --- Save metadata ---
    meta = {
        "base_model": BASE_MODEL,
        "adapter_path": str(adapter_path),
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "epochs": args.epochs,
        "train_examples": len(train_ds),
        "eval_examples": len(eval_ds),
        "device": device,
        "version": "1.0.0",
        "task": "sigma_intent_classification",
        "output_schema": {
            "mode": ["LOOP", "INFO", "PLAN"],
            "agent": ["math_researcher", "code_architect", "viz_designer",
                      "test_engineer", "proof_reviewer", "sigma_architect", "sigma_assistant"],
            "intent": ["create_topic_file", "edit_code", "run_test", "explain_concept",
                       "create_viz", "create_module", "plan_roadmap", "general_chat",
                       "review_proof", "debug_code", "delete_file", "rename_file"],
            "actions": ["list of action strings"]
        }
    }
    meta_path = OUTPUT_DIR / "model_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Metadata saved → %s", meta_path)

    # --- Export merged model for Ollama (optional) ---
    if args.export_gguf:
        log.info("Merging LoRA into base model for GGUF export...")
        try:
            from peft import AutoPeftModelForCausalLM
            merged = AutoPeftModelForCausalLM.from_pretrained(
                str(adapter_path), torch_dtype=torch.float32
            )
            merged_path = OUTPUT_DIR / "merged"
            merged.save_pretrained(str(merged_path))
            tokenizer.save_pretrained(str(merged_path))
            log.info("Merged model saved → %s", merged_path)
            log.info("To convert to GGUF, run:")
            log.info("  python llama.cpp/convert_hf_to_gguf.py %s --outtype q4_k_m", merged_path)
        except Exception as e:
            log.warning("GGUF export skipped: %s", e)

    log.info("=" * 60)
    log.info("🎉 Sigma Router Ailo fine-tuning complete!")
    log.info("   Adapter: %s", adapter_path)
    log.info("   Load in router_trainer.py with:")
    log.info("   classify_intent_with_ailo(message)")
    log.info("=" * 60)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fine-tune Ailo-152M as Sigma Router intent classifier"
    )
    parser.add_argument("--epochs",      type=int,  default=5,     help="Training epochs (default: 5)")
    parser.add_argument("--gpu",         action="store_true",      help="Use GPU if available")
    parser.add_argument("--dry-run",     action="store_true",      help="Check deps and config, don't train")
    parser.add_argument("--export-gguf", action="store_true",      help="Merge LoRA + export for Ollama")
    parser.add_argument("--dataset",     type=str, default=str(DATASET_PATH), help="Dataset path")
    args = parser.parse_args()

    # Update dataset path if overridden
    if args.dataset != str(DATASET_PATH):
        DATASET_PATH = Path(args.dataset)

    # Dependency check
    deps_ok = check_deps(dry_run=args.dry_run)

    # Dataset check (always)
    if not args.dry_run:
        check_dataset()

    # Run
    if deps_ok or args.dry_run:
        run_training(args)
