"""CLI unica di Gradus — tutta la pipeline, dalla generazione alla chat.

    python -m gradus info
    python -m gradus analyze     --model qwen0.5b
    python -m gradus train       --model qwen0.5b --generator ailo
    python -m gradus reconstruct --run runs/<dir>
    python -m gradus eval        --run runs/<dir>
    python -m gradus chat        --run runs/<dir>     # ricostruito
    python -m gradus chat        --model qwen0.5b     # originale
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from .config import (
    BlockConfig, GeneratorConfig, GradusConfig, TrainConfig,
    MODEL_PRESETS, resolve_model, pick_device, AILO_BACKBONE,
)
from .logging_utils import get_logger, new_run_dir, section


def _cfg_from_args(args) -> GradusConfig:
    return GradusConfig(
        model=resolve_model(args.model),
        device=args.device,
        dtype=args.dtype,
        block=BlockConfig(block_size=args.block_size),
        generator=GeneratorConfig(
            kind=args.generator,
            backbone=args.backbone,
            latent_dim=args.latent_dim,
            seq_len=args.seq_len,
            freeze_backbone=args.freeze_backbone,
        ),
        train=TrainConfig(
            steps=args.steps,
            batch_blocks=args.batch_blocks,
            lr=args.lr,
            eval_every=args.eval_every,
            max_layers=args.max_layers,
            include=args.include,
            objective=args.objective,
            dataset=args.dataset,
        ),
    )


def _add_model_args(p):
    p.add_argument("--model", default="qwen0.5b",
                   help=f"preset {list(MODEL_PRESETS)} oppure id HF / path")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps", "dml"],
                   help="dml = GPU AMD su Windows via DirectML (es. RX 6750 XT)")
    p.add_argument("--dtype", default="float32", choices=["float32", "float16", "bfloat16"])
    p.add_argument("--block-size", dest="block_size", type=int, default=64)


def _add_gen_args(p):
    p.add_argument("--generator", default="ailo", choices=["ailo", "mlp"])
    p.add_argument("--backbone", default=AILO_BACKBONE, help="backbone HF per il generatore ailo")
    p.add_argument("--latent-dim", dest="latent_dim", type=int, default=48)
    p.add_argument("--seq-len", dest="seq_len", type=int, default=4)
    p.add_argument("--freeze-backbone", dest="freeze_backbone", action="store_true")


def _add_train_args(p):
    p.add_argument("--steps", type=int, default=2000)
    p.add_argument("--batch-blocks", dest="batch_blocks", type=int, default=256)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--eval-every", dest="eval_every", type=int, default=200)
    p.add_argument("--max-layers", dest="max_layers", type=int, default=-1,
                   help="limita ai primi N layer (smoke test); -1 = tutti")
    p.add_argument("--include", default="", help="comprimi solo tensori il cui nome contiene questa stringa")
    p.add_argument("--objective", default="weight", choices=["weight", "task"],
                   help="weight = copia i pesi (MSE) | task = mantieni la perplexity (LM loss)")
    p.add_argument("--dataset", default="", help="objective=task: '' corpus interno | 'wikitext'")


def cmd_info(_args):
    logger = get_logger()
    section(logger, "Ambiente Gradus")
    logger.info("torch %s | cuda disponibile: %s", torch.__version__, torch.cuda.is_available())
    if torch.cuda.is_available():
        logger.info("GPU: %s", torch.cuda.get_device_name(0))
    logger.info("device scelto (auto): %s", pick_device("auto"))
    logger.info("preset modelli: %s", MODEL_PRESETS)
    logger.info("backbone generatore di default (AILO): %s", AILO_BACKBONE)


def cmd_analyze(args):
    from .analyze import analyze
    cfg = _cfg_from_args(args)
    run_dir = new_run_dir(tag="analyze")
    logger = get_logger(run_dir)
    analyze(cfg, run_dir, logger)


def cmd_train(args):
    from .train import train
    cfg = _cfg_from_args(args)
    run_dir = new_run_dir(tag="train")
    logger = get_logger(run_dir)
    res = train(cfg, run_dir, logger)
    logger.info("FATTO. %s", json.dumps(res, ensure_ascii=False))
    print(f"\nRun: {run_dir}\nProssimo: python -m gradus eval --run {run_dir}")


def cmd_demo(args):
    """Tutto il giro in un comando: train veloce -> eval -> chat di prova."""
    from .train import train
    from .evaluate import evaluate
    from .chat import chat as chat_fn
    cfg = _cfg_from_args(args)
    # config 'demo': un solo tensore, latent ampio -> mostra la cosine salire
    cfg.block.block_size = 32
    cfg.generator.latent_dim = 512
    cfg.train.include = "layers.0.self_attn.q_proj"
    cfg.train.eval_every = max(50, args.steps // 6)
    run_dir = new_run_dir(tag="demo")
    logger = get_logger(run_dir)
    section(logger, "DEMO 1/3 — alleno il generatore (la cosine deve salire)")
    res = train(cfg, run_dir, logger)
    section(logger, "DEMO 2/3 — ricostruisco i pesi e misuro la fedelta'")
    ev = evaluate(cfg.model, run_dir / "generator.pt", device=cfg.device, logger=logger)
    (run_dir / "eval.json").write_text(json.dumps(ev, indent=2), encoding="utf-8")
    section(logger, "DEMO 3/3 — chat dal modello RICOSTRUITO")
    chat_fn(cfg.model, run_dir / "generator.pt", cfg.device, logger,
            prompt=args.prompt or "Ciao, come stai?")
    logger.info("DEMO completata. cosine=%.3f | ppl orig=%.2f ric=%.2f | run=%s",
                res.get("best_cosine", 0.0), ev["ppl_original"], ev["ppl_reconstructed"], run_dir)


def _load_run(run_dir: str):
    rd = Path(run_dir)
    cfg = GradusConfig.from_json(rd / "config.json")
    ckpt = rd / "generator.pt"
    if not ckpt.exists():
        raise FileNotFoundError(f"Checkpoint mancante: {ckpt}")
    return rd, cfg, ckpt


def cmd_reconstruct(args):
    from .reconstruct import reconstruct_state
    rd, cfg, ckpt = _load_run(args.run)
    logger = get_logger(rd)
    section(logger, "Ricostruzione pesi")
    sd, plan = reconstruct_state(ckpt, device="cpu", logger=logger)
    out = rd / "reconstructed_state.pt"
    torch.save(sd, out)
    logger.info("State dict ricostruito (%d tensori) -> %s", len(sd), out)


def cmd_eval(args):
    from .evaluate import evaluate
    rd, cfg, ckpt = _load_run(args.run)
    logger = get_logger(rd)
    section(logger, "Valutazione")
    res = evaluate(cfg.model, ckpt, device=cfg.device, logger=logger)
    (rd / "eval.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    logger.info("Report eval -> %s", rd / "eval.json")


def cmd_engine_test(args):
    logger = get_logger()
    if args.brick == 3:
        from .engine.brick3 import run
    elif args.brick == 2:
        from .engine.brick2 import run
    else:
        from .engine.brick1 import run
    run(logger, device=args.device, steps=args.steps)


def cmd_engine_fwe(args):
    logger = get_logger()
    if args.objective == "task" and args.qwen_manual:
        from .engine.fwe import run_task_engine
        run_task_engine(logger, model=args.model, device=args.device, include=args.include,
                        block_size=args.block_size, latent_dim=args.latent_dim, steps=args.steps,
                        prompt=args.prompt, lr=args.lr, max_layers=args.max_layers,
                        dataset=args.dataset, vq=args.vq, batch=args.batch,
                        run_dir=args.run_dir, save_every=args.save_every, resume=args.resume,
                        devices=getattr(args, "devices", ""),
                        device_weights=getattr(args, "device_weights", ""))
    elif args.objective == "task":
        from .engine.fwe import run_task
        run_task(logger, model=args.model, device=args.device, include=args.include,
                 block_size=args.block_size, latent_dim=args.latent_dim, steps=args.steps,
                 prompt=args.prompt, ailo=args.ailo, freeze=args.freeze, lr=args.lr)
    else:
        from .engine.fwe import run
        run(logger, model=args.model, device=args.device, include=args.include,
            block_size=args.block_size, latent_dim=args.latent_dim, steps=args.steps,
            prompt=args.prompt, ailo=args.ailo, freeze=args.freeze, lr=args.lr)


def cmd_engine_chat(args):
    from .engine.fwe import chat_from_ckpt
    logger = get_logger()
    chat_from_ckpt(logger, args.ckpt, args.prompt, device=args.device)


def cmd_gui(_args):
    from .gui import launch
    launch()


def cmd_chat(args):
    from .chat import chat
    if args.run:
        rd, cfg, ckpt = _load_run(args.run)
        logger = get_logger(rd)
        chat(cfg.model, ckpt, cfg.device, logger, prompt=args.prompt)
    else:
        logger = get_logger()
        chat(resolve_model(args.model), None, args.device, logger, prompt=args.prompt)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gradus", description="Functional Weight Engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info", help="ambiente e device")
    p.set_defaults(func=cmd_info)

    p = sub.add_parser("gui", help="ambiente grafico (log live + tutti i comandi)")
    p.set_defaults(func=cmd_gui)

    p = sub.add_parser("engine-fwe", help="FWE completo sul motore: train su GPU -> prompt")
    p.add_argument("--model", default="qwen0.5b-instruct")
    p.add_argument("--device", default="auto",
                   help="auto | cpu | cuda | cuda:N (GPU specifica) | xpu | mps | dml")
    p.add_argument("--include", default="layers.0.self_attn.q_proj")
    p.add_argument("--block-size", dest="block_size", type=int, default=32)
    p.add_argument("--latent-dim", dest="latent_dim", type=int, default=512)
    p.add_argument("--steps", type=int, default=600)
    p.add_argument("--prompt", default="Spiegami cos'è un buco nero in una frase.")
    p.add_argument("--lr", type=float, default=2e-3)
    p.add_argument("--objective", default="weight", choices=["weight", "task"],
                   help="weight=copia i pesi | task=mantieni la perplexity")
    p.add_argument("--ailo", action="store_true", help="decoder = AILO pretrained (12x768)")
    p.add_argument("--freeze", action="store_true", help="congela il decoder, allena solo latent+adattatori")
    p.add_argument("--qwen-manual", dest="qwen_manual", action="store_true",
                   help="objective=task TUTTO sul 6750 (Qwen col motore manuale)")
    p.add_argument("--max-layers", dest="max_layers", type=int, default=-1,
                   help="limita ai primi N layer (-1=tutti)")
    p.add_argument("--dataset", default="", help="'' corpus interno | 'wikitext' (corpus grande)")
    p.add_argument("--vq", type=int, default=0, help="codebook VQ: K atomi condivisi (0=latent liberi)")
    p.add_argument("--batch", type=int, default=8, help="sequenze per step (task): batch grande = loss stabile")
    p.add_argument("--run-dir", dest="run_dir", default="runs/engine", help="cartella per checkpoint/log")
    p.add_argument("--save-every", dest="save_every", type=int, default=25, help="salva checkpoint ogni N step")
    p.add_argument("--resume", default="", help="riprendi da un checkpoint (path a engine_ckpt.pt)")
    p.add_argument("--devices", default="",
                   help="sharding multi-GPU: 'all' oppure 'cuda:0,cuda:1'. "
                        "Il generatore (94%% del tempo) viene diviso fra le schede")
    p.add_argument("--device-weights", dest="device_weights", default="",
                   help="quote di ripartizione, es. '2,1'. Vuoto = misurate al volo")
    p.set_defaults(func=cmd_engine_fwe)

    p = sub.add_parser("engine-chat", help="chatta col modello ricostruito da un checkpoint del motore")
    p.add_argument("--ckpt", required=True, help="path a engine_ckpt.pt")
    p.add_argument("--prompt", required=True)
    p.add_argument("--device", default="cpu", choices=["cpu", "dml", "cuda"])
    p.set_defaults(func=cmd_engine_chat)

    p = sub.add_parser("engine-test", help="motore manuale: gradient-check + training su GPU")
    p.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps", "dml"])
    p.add_argument("--brick", type=int, default=1, choices=[1, 2, 3],
                   help="1=Linear/MLP, 2=blocco AILO, 3=generatore completo")
    p.add_argument("--steps", type=int, default=400)
    p.set_defaults(func=cmd_engine_test)

    p = sub.add_parser("analyze", help="statistiche pesi del modello target")
    _add_model_args(p)
    _add_train_args(p)
    _add_gen_args(p)
    p.set_defaults(func=cmd_analyze)

    p = sub.add_parser("train", help="allena il generatore di pesi")
    _add_model_args(p)
    _add_gen_args(p)
    _add_train_args(p)
    p.set_defaults(func=cmd_train)

    p = sub.add_parser("demo", help="tutto il giro in un comando: train->eval->chat")
    _add_model_args(p)
    _add_gen_args(p)
    _add_train_args(p)
    p.add_argument("--prompt", default="", help="messaggio per la chat finale")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("reconstruct", help="ricostruisci lo state dict dal generatore")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_reconstruct)

    p = sub.add_parser("eval", help="fedeltà pesi + perplexity")
    p.add_argument("--run", required=True)
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("chat", help="chat col modello (originale o ricostruito)")
    p.add_argument("--run", default="", help="run dir col generatore (chat ricostruito)")
    _add_model_args(p)
    p.add_argument("--prompt", default="", help="one-shot; vuoto = interattivo")
    p.set_defaults(func=cmd_chat)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    # normalizza opzionali assenti
    if not getattr(args, "run", None):
        args.run = ""
    if not getattr(args, "prompt", None):
        args.prompt = ""
    args.run = args.run or None
    args.prompt = args.prompt or None
    args.func(args)


if __name__ == "__main__":
    main()
