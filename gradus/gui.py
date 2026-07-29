"""Ambiente grafico Gradus — vedi TUTTO quello che succede in tempo reale.

Pannello log live (cattura logger gradus, transformers, download e warning) +
tutti i comandi a pulsante: info / analyze / train / reconstruct / eval / chat.
Tkinter: nessuna dipendenza extra, gira nativo su Windows.
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import ttk, scrolledtext

from . import logging_utils
from .config import (
    BlockConfig, GeneratorConfig, GradusConfig, TrainConfig,
    MODEL_PRESETS, resolve_model, pick_device, AILO_BACKBONE,
)
from .logging_utils import get_logger, new_run_dir


# ----------------------------------------------------------------------------- IO
class _QueueLogHandler(logging.Handler):
    def __init__(self, q: "queue.Queue[str]"):
        super().__init__()
        self.q = q
        self.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))

    def emit(self, record):
        try:
            self.q.put(self.format(record))
        except Exception:
            pass


class _StreamToQueue:
    """Redirige stdout/stderr (tqdm, print, warning) nel pannello log."""
    def __init__(self, q: "queue.Queue[str]", mirror=None):
        self.q = q
        self.mirror = mirror
        self._buf = ""

    def write(self, s):
        if self.mirror:
            try:
                self.mirror.write(s)
            except Exception:
                pass
        self._buf += s
        while "\n" in self._buf or "\r" in self._buf:
            idx = min((i for i in (self._buf.find("\n"), self._buf.find("\r")) if i >= 0))
            line, self._buf = self._buf[:idx], self._buf[idx + 1:]
            if line.strip():
                self.q.put(line)

    def flush(self):
        if self._buf.strip():
            self.q.put(self._buf)
            self._buf = ""


# ----------------------------------------------------------------------------- GUI
class GradusGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gradus — Functional Weight Engine")
        self.geometry("1080x760")
        self.queue: "queue.Queue[str]" = queue.Queue()
        self.busy = False
        self.eng_proc = None          # processo di training del motore (subprocess)

        # log gradus -> solo pannello (niente doppioni su console)
        logging_utils.SUPPRESS_CONSOLE = True
        self.logger = get_logger()
        self.logger.handlers = [h for h in self.logger.handlers
                                if not isinstance(h, logging.StreamHandler)
                                or isinstance(h, logging.FileHandler)]
        qh = _QueueLogHandler(self.queue)
        self.logger.addHandler(qh)
        logging.getLogger("transformers").addHandler(qh)
        logging.getLogger("transformers").setLevel(logging.INFO)
        # download/tqdm/warning -> pannello (mantieni anche terminale)
        sys.stdout = _StreamToQueue(self.queue, mirror=sys.__stdout__)
        sys.stderr = _StreamToQueue(self.queue, mirror=sys.__stderr__)

        self._build_ui()
        self._refresh_runs()
        self.after(120, self._drain)
        self.logger.info("GUI pronta. Device auto: %s", pick_device("auto"))

    # ----- layout
    def _build_ui(self):
        top = ttk.Frame(self, padding=8)
        top.pack(fill=tk.X)

        self.var = {
            "model": tk.StringVar(value="qwen0.5b"),
            "generator": tk.StringVar(value="ailo"),
            "device": tk.StringVar(value="auto"),
            "block_size": tk.StringVar(value="64"),
            "latent_dim": tk.StringVar(value="48"),
            "steps": tk.StringVar(value="2000"),
            "batch_blocks": tk.StringVar(value="256"),
            "max_layers": tk.StringVar(value="-1"),
            "include": tk.StringVar(value=""),
            "objective": tk.StringVar(value="weight"),
        }

        def row(parent, r, label, key, width=18, values=None):
            ttk.Label(parent, text=label).grid(row=r, column=0, sticky=tk.W, padx=4, pady=3)
            if values:
                ttk.Combobox(parent, textvariable=self.var[key], values=values,
                             width=width - 3, state="readonly").grid(row=r, column=1, sticky=tk.W)
            else:
                ttk.Entry(parent, textvariable=self.var[key], width=width).grid(row=r, column=1, sticky=tk.W)

        left = ttk.LabelFrame(top, text="Configurazione", padding=8)
        left.grid(row=0, column=0, sticky=tk.NW, padx=(0, 10))
        row(left, 0, "Modello target", "model", values=list(MODEL_PRESETS) + ["custom..."])
        row(left, 1, "Generatore", "generator", values=["ailo", "mlp"])
        row(left, 2, "Device", "device", values=["auto", "cpu", "cuda", "mps", "dml"])
        row(left, 3, "Block size", "block_size")
        row(left, 4, "Latent dim", "latent_dim")
        row(left, 5, "Steps", "steps")
        row(left, 6, "Batch blocchi", "batch_blocks")
        row(left, 7, "Max layers (-1=tutti)", "max_layers")
        row(left, 8, "Include (substring)", "include")
        row(left, 9, "Obiettivo", "objective", values=["weight", "task"])
        self.freeze_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left, text="Congela AILO (allena solo latent+adattatori)",
                        variable=self.freeze_var).grid(row=10, column=0, columnspan=2,
                                                       sticky=tk.W, padx=4, pady=3)

        # bottoni comandi
        btns = ttk.LabelFrame(top, text="Comandi", padding=8)
        btns.grid(row=0, column=1, sticky=tk.NW, padx=(0, 10))
        self.cmd_buttons = []
        for i, (txt, fn) in enumerate([
            ("Info", self._info), ("Analyze", self._analyze), ("Train", self._train),
            ("Reconstruct", self._reconstruct), ("Eval", self._eval),
        ]):
            b = ttk.Button(btns, text=txt, width=16, command=fn)
            b.grid(row=i, column=0, pady=3)
            self.cmd_buttons.append(b)

        # run selector + chat
        right = ttk.LabelFrame(top, text="Run & Chat", padding=8)
        right.grid(row=0, column=2, sticky=tk.NW)
        ttk.Label(right, text="Run (per reconstruct/eval/chat):").grid(row=0, column=0, sticky=tk.W)
        self.run_var = tk.StringVar()
        self.run_combo = ttk.Combobox(right, textvariable=self.run_var, width=34, state="readonly")
        self.run_combo.grid(row=1, column=0, sticky=tk.W, pady=3)
        ttk.Button(right, text="Aggiorna lista run", command=self._refresh_runs).grid(row=2, column=0, sticky=tk.W)
        ttk.Separator(right, orient=tk.HORIZONTAL).grid(row=3, column=0, sticky=tk.EW, pady=6)
        ttk.Label(right, text="Messaggio chat:").grid(row=4, column=0, sticky=tk.W)
        self.chat_var = tk.StringVar()
        ent = ttk.Entry(right, textvariable=self.chat_var, width=37)
        ent.grid(row=5, column=0, sticky=tk.W, pady=3)
        ent.bind("<Return>", lambda e: self._chat())
        cf = ttk.Frame(right)
        cf.grid(row=6, column=0, sticky=tk.W)
        ttk.Button(cf, text="Chat (ricostruito)", command=lambda: self._chat(use_run=True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(cf, text="Chat (originale)", command=lambda: self._chat(use_run=False)).pack(side=tk.LEFT, padx=2)

        # ---- Motore FWE: training del modello completo sul 6750 + chat dal checkpoint ----
        eng = ttk.LabelFrame(top, text="Motore FWE — modello completo (6750, checkpoint + chat live)",
                             padding=8)
        eng.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(8, 0))
        self.evar = {
            "include": tk.StringVar(value="_proj"),
            "max_layers": tk.StringVar(value="-1"),
            "vq": tk.StringVar(value="512"),
            "latent": tk.StringVar(value="64"),
            "steps": tk.StringVar(value="600"),
            "lr": tk.StringVar(value="2e-4"),
            "batch": tk.StringVar(value="8"),
            "run_dir": tk.StringVar(value="runs/engine-full"),
        }
        labels = [("Include", "include"), ("Max layers", "max_layers"), ("VQ (K)", "vq"),
                  ("Latent", "latent"), ("Steps", "steps"), ("LR", "lr"),
                  ("Batch", "batch"), ("Run dir", "run_dir")]
        for i, (txt, key) in enumerate(labels):
            ttk.Label(eng, text=txt).grid(row=0, column=i, padx=3)
            w = 16 if key == "run_dir" else 7
            ttk.Entry(eng, textvariable=self.evar[key], width=w).grid(row=1, column=i, padx=3)
        bf = ttk.Frame(eng)
        bf.grid(row=2, column=0, columnspan=8, sticky=tk.W, pady=(6, 0))
        ttk.Button(bf, text="Avvia training", command=self._eng_start).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="Riprendi da checkpoint", command=lambda: self._eng_start(resume=True)).pack(side=tk.LEFT, padx=3)
        ttk.Button(bf, text="Stop", command=self._eng_stop).pack(side=tk.LEFT, padx=3)
        ttk.Label(bf, text="   Chat (dal checkpoint, anche durante il training):").pack(side=tk.LEFT)
        self.eng_chat_var = tk.StringVar()
        ec = ttk.Entry(bf, textvariable=self.eng_chat_var, width=34)
        ec.pack(side=tk.LEFT, padx=3)
        ec.bind("<Return>", lambda e: self._eng_chat())
        ttk.Button(bf, text="Chiedi", command=self._eng_chat).pack(side=tk.LEFT, padx=3)

        # stato
        self.status = ttk.Label(self, text="pronto", anchor=tk.W, relief=tk.SUNKEN, padding=4)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)

        # log
        logf = ttk.LabelFrame(self, text="Log live — tutto quello che succede", padding=4)
        logf.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))
        self.log = scrolledtext.ScrolledText(logf, state="disabled", wrap=tk.WORD,
                                             font=("Consolas", 9), bg="#11141a", fg="#d6e2f0")
        self.log.pack(fill=tk.BOTH, expand=True)
        bar = ttk.Frame(self)
        bar.pack(fill=tk.X, padx=8, pady=(0, 6))
        ttk.Button(bar, text="Pulisci log", command=self._clear_log).pack(side=tk.LEFT)

    # ----- log plumbing
    def _drain(self):
        try:
            while True:
                line = self.queue.get_nowait()
                self.log.configure(state="normal")
                self.log.insert(tk.END, line + "\n")
                self.log.see(tk.END)
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.after(120, self._drain)

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", tk.END)
        self.log.configure(state="disabled")

    def _set_busy(self, busy: bool, what: str = ""):
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        for b in self.cmd_buttons:
            b.configure(state=state)
        self.status.configure(text=(f"in esecuzione: {what}..." if busy else "pronto"))

    def _run_async(self, what: str, target, on_done=None):
        if self.busy:
            self.logger.warning("Operazione gia' in corso, attendi.")
            return
        self._set_busy(True, what)

        def wrapper():
            try:
                target()
            except Exception as exc:
                self.logger.error("ERRORE: %s", exc)
                for ln in traceback.format_exc().splitlines():
                    self.queue.put(ln)
            finally:
                self.after(0, lambda: self._set_busy(False))
                if on_done:
                    self.after(0, on_done)

        threading.Thread(target=wrapper, daemon=True).start()

    # ----- config
    def _cfg(self) -> GradusConfig:
        v = self.var
        return GradusConfig(
            model=resolve_model(v["model"].get()),
            device=v["device"].get(),
            block=BlockConfig(block_size=int(v["block_size"].get())),
            generator=GeneratorConfig(kind=v["generator"].get(),
                                      latent_dim=int(v["latent_dim"].get()),
                                      freeze_backbone=bool(self.freeze_var.get())),
            train=TrainConfig(steps=int(v["steps"].get()),
                              batch_blocks=int(v["batch_blocks"].get()),
                              max_layers=int(v["max_layers"].get()),
                              include=v["include"].get().strip(),
                              objective=v["objective"].get()),
        )

    def _refresh_runs(self):
        base = Path("runs")
        runs = sorted([p.name for p in base.glob("*") if (p / "generator.pt").exists()], reverse=True)
        self.run_combo["values"] = runs
        if runs and not self.run_var.get():
            self.run_var.set(runs[0])

    def _selected_run(self) -> Path | None:
        name = self.run_var.get().strip()
        if not name:
            self.logger.warning("Nessun run selezionato (serve un train completato).")
            return None
        return Path("runs") / name

    # ----- comandi
    def _info(self):
        import torch
        self.logger.info("== Ambiente ==")
        self.logger.info("torch %s | cuda: %s", torch.__version__, torch.cuda.is_available())
        if torch.cuda.is_available():
            self.logger.info("GPU: %s", torch.cuda.get_device_name(0))
        self.logger.info("device auto: %s | backbone AILO: %s", pick_device("auto"), AILO_BACKBONE)

    def _analyze(self):
        def task():
            from .analyze import analyze
            cfg = self._cfg()
            rd = new_run_dir(tag="analyze")
            get_logger(rd)
            analyze(cfg, rd, self.logger)
        self._run_async("analyze", task)

    def _train(self):
        def task():
            from .train import train
            cfg = self._cfg()
            rd = new_run_dir(tag="train")
            get_logger(rd)
            res = train(cfg, rd, self.logger)
            self.logger.info("TRAIN FATTO: %s", res)
        self._run_async("train", task, on_done=self._refresh_runs)

    def _reconstruct(self):
        rd = self._selected_run()
        if not rd:
            return
        def task():
            import torch
            from .reconstruct import reconstruct_state
            get_logger(rd)
            sd, plan = reconstruct_state(rd / "generator.pt", device="cpu", logger=self.logger)
            torch.save(sd, rd / "reconstructed_state.pt")
            self.logger.info("Ricostruiti %d tensori -> %s", len(sd), rd / "reconstructed_state.pt")
        self._run_async("reconstruct", task)

    def _eval(self):
        rd = self._selected_run()
        if not rd:
            return
        def task():
            import json
            from .evaluate import evaluate
            cfg = GradusConfig.from_json(rd / "config.json")
            get_logger(rd)
            res = evaluate(cfg.model, rd / "generator.pt", device=cfg.device, logger=self.logger)
            (rd / "eval.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
            self.logger.info("EVAL: cosine=%.4f ppl_orig=%.2f ppl_ric=%.2f",
                             res["cosine_mean"], res["ppl_original"], res["ppl_reconstructed"])
        self._run_async("eval", task)

    def _chat(self, use_run: bool = True):
        msg = self.chat_var.get().strip()
        if not msg:
            return
        self.chat_var.set("")
        self.logger.info("[tu] %s", msg)
        def task():
            import torch
            from .modelio import load_target_model
            from .chat import _generate
            if use_run:
                rd = self._selected_run()
                if not rd:
                    return
                from .reconstruct import load_reconstructed_model
                cfg = GradusConfig.from_json(rd / "config.json")
                model, tok, dev, _ = load_reconstructed_model(cfg.model, rd / "generator.pt",
                                                              device=cfg.device, logger=self.logger)
            else:
                cfg = self._cfg()
                model, tok, dev = load_target_model(cfg.model, cfg.device, torch.float32)
            reply = _generate(model, tok, msg, dev)
            self.logger.info("[ai] %s", reply)
        self._run_async("chat", task)

    # ----- motore FWE (subprocess: sopravvive nel suo processo, log in streaming)
    def _engine_python(self):
        venv = Path(".venv/Scripts/python.exe")
        return str(venv) if venv.exists() else sys.executable

    def _spawn(self, args, tag):
        env = dict(os.environ, PYTHONPATH=str(Path.cwd()), PYTHONIOENCODING="utf-8")
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, encoding="utf-8", errors="replace", env=env)

        def reader():
            for line in proc.stdout:
                self.queue.put(f"[{tag}] {line.rstrip()}")
            self.queue.put(f"[{tag}] processo terminato (exit {proc.wait()})")
        threading.Thread(target=reader, daemon=True).start()
        return proc

    def _eng_args(self, resume=False):
        v = self.evar
        rd = v["run_dir"].get().strip() or "runs/engine-full"
        a = [self._engine_python(), "-m", "gradus", "engine-fwe",
             "--objective", "task", "--qwen-manual", "--dataset", "wikitext",
             "--include", v["include"].get().strip() or "_proj",
             "--max-layers", v["max_layers"].get(), "--vq", v["vq"].get(),
             "--latent-dim", v["latent"].get(), "--steps", v["steps"].get(),
             "--lr", v["lr"].get(), "--batch", v["batch"].get(),
             "--device", "dml", "--run-dir", rd, "--save-every", "25"]
        if resume:
            a += ["--resume", str(Path(rd) / "engine_ckpt.pt")]
        return a

    def _eng_start(self, resume=False):
        if self.eng_proc is not None and self.eng_proc.poll() is None:
            self.logger.warning("Training gia' in corso (usa Stop prima).")
            return
        if resume and not (Path(self.evar["run_dir"].get().strip() or "runs/engine-full") / "engine_ckpt.pt").exists():
            self.logger.warning("Nessun checkpoint da cui riprendere.")
            return
        self.eng_proc = self._spawn(self._eng_args(resume), "train")
        self.logger.info("Training %s — log live qui sotto. Checkpoint ogni 25 step.",
                         "RIPRESO" if resume else "avviato")

    def _eng_stop(self):
        if self.eng_proc is not None and self.eng_proc.poll() is None:
            self.eng_proc.terminate()
            self.logger.info("Training fermato (il checkpoint resta: puoi riprendere).")
        else:
            self.logger.info("Nessun training in corso.")

    def _eng_chat(self):
        msg = self.eng_chat_var.get().strip()
        if not msg:
            return
        self.eng_chat_var.set("")
        rd = Path(self.evar["run_dir"].get().strip() or "runs/engine-full")
        ck = rd / "engine_ckpt.pt"
        if not ck.exists():
            self.logger.warning("Nessun checkpoint in %s (aspetta il primo salvataggio).", rd)
            return
        self.logger.info("[tu -> checkpoint] %s", msg)
        self._spawn([self._engine_python(), "-m", "gradus", "engine-chat",
                     "--ckpt", str(ck), "--prompt", msg, "--device", "cpu"], "chat")


def launch():
    GradusGUI().mainloop()


if __name__ == "__main__":
    launch()
