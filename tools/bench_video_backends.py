"""Confronto dei motori video su MiniMax H3: worker nativo (sd.cpp) e ComfyUI.

Ogni configurazione genera lo stesso clip (prompt, seed, risoluzione, frame,
step, sampler) e misura tempo totale, tempo di campionamento per step e picco
di VRAM per GPU. Il primo clip di ogni configurazione e' "a freddo" (include
il caricamento dei pesi); dal secondo in poi si misura il regime, che e' cio'
che conta per una produzione di cento clip.

    python tools/bench_video_backends.py --configs native_q4,comfy_int8 --frames 124 --runs 2

Risultati in var/bench_video/results.json; provini dei fotogrammi accanto ai video.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.logger import get_logger  # noqa: E402

log = get_logger("bench_video")

PROMPT = ("A cute silver tabby kitten surfs on a tropical ocean wave riding a white surfboard. "
          "Cinematic tracking shot, realistic water, bright sunlight, consistent character appearance.\n"
          "Audio: upbeat tropical surf-rock music with cheerful drums and guitar.")

CONFIGS = {
    "comfy_int8": {"engine": "comfyui", "label": "ComfyUI · int8 convrot + encoder nvfp4"},
    "comfy_int8_gpu1": {"engine": "comfyui", "gpu": 1, "label": "ComfyUI · int8 convrot sulla 5060 (8 GB)"},
    "comfy_base": {"engine": "comfyui", "gpu": 0, "flags": [], "label": "ComfyUI · nessuna ottimizzazione"},
    "comfy_sage": {"engine": "comfyui", "gpu": 0, "flags": ["--use-sage-attention"],
                   "label": "ComfyUI · SageAttention"},
    "comfy_sage_easycache": {"engine": "comfyui", "gpu": 0, "flags": ["--use-sage-attention"],
                             "graph": {"easycache": True, "easycache_threshold": 0.2},
                             "label": "ComfyUI · Sage + EasyCache 0.2"},
    "comfy_sage_fp16acc": {"engine": "comfyui", "gpu": 0, "flags": ["--use-sage-attention", "--fast", "fp16_accumulation"],
                           "label": "ComfyUI · Sage + accumulo FP16"},
    "comfy_sage_w6a8": {"engine": "comfyui", "gpu": 0, "flags": ["--use-sage-attention"], "graph": {"weights": "w6a8"},
                        "label": "ComfyUI · Sage + pesi w6a8"},
    "comfy_sage_fp8": {"engine": "comfyui", "gpu": 0, "flags": ["--use-sage-attention"], "graph": {"weights": "fp8"},
                       "label": "ComfyUI · Sage + pesi fp8"},
    "comfy_sage_w6a8_gpu1": {"engine": "comfyui", "gpu": 1, "flags": ["--use-sage-attention"],
                             "graph": {"weights": "w6a8"}, "label": "ComfyUI · Sage + w6a8 sulla 5060"},
    "comfy_sage_easycache_gpu1": {"engine": "comfyui", "gpu": 1, "flags": ["--use-sage-attention"],
                                  "graph": {"easycache": True}, "label": "ComfyUI · Sage + EasyCache sulla 5060"},
    "comfy_sage_gpu1": {"engine": "comfyui", "gpu": 1, "flags": ["--use-sage-attention"],
                        "label": "ComfyUI · SageAttention sulla 5060"},
    "native_q4": {"engine": "native", "profile": "minimax-h3-q4", "placement": "offload",
                  "label": "Nativo · Q4_K_M, pesi in RAM"},
    "native_q4_gpu1": {"engine": "native", "profile": "minimax-h3-q4", "placement": "gpu:1",
                       "label": "Nativo · Q4_K_M sulla 5060 (8 GB), pesi in RAM"},
    "native_int8": {"engine": "native", "profile": "minimax-h3-int8", "placement": "offload",
                    "label": "Nativo · int8 convrot (stessi pesi di ComfyUI)"},
    "native_q4_vram": {"engine": "native", "profile": "minimax-h3-q4",
                       "load": {"params_backend": "te=cpu"}, "placement": "none",
                       "label": "Nativo · Q4_K_M, DiT residente in VRAM"},
    "native_q4_split": {"engine": "native", "profile": "minimax-h3-q4", "placement": "split_gpu",
                        "label": "Nativo · Q4_K_M, DiT diviso su 5070 Ti + 5060"},
    "native_q4_sage": {"engine": "native", "profile": "minimax-h3-q4", "placement": "offload",
                       "load": {"sage_attn": True}, "label": "Nativo · Q4_K_M + SageAttention2++"},
    "native_int8_sage": {"engine": "native", "profile": "minimax-h3-int8", "placement": "offload",
                         "load": {"sage_attn": True}, "label": "Nativo · int8 convrot + SageAttention2++"},
    "native_q4_sage_gpu1": {"engine": "native", "profile": "minimax-h3-q4", "placement": "gpu:1",
                            "load": {"sage_attn": True}, "label": "Nativo · Q4_K_M + Sage sulla 5060"},
    "native_q4_easycache": {"engine": "native", "profile": "minimax-h3-q4", "placement": "offload",
                            "job": {"cache_mode": "easycache", "cache_option": "threshold=0.2"},
                            "label": "Nativo · Q4_K_M + EasyCache 0.2"},
    "native_q4_cachedit": {"engine": "native", "profile": "minimax-h3-q4", "placement": "offload",
                           "job": {"cache_mode": "cache-dit"},
                           "label": "Nativo · Q4_K_M + cache-dit"},
}


class VramSampler:
    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self.peak: dict[int, int] = {}
        self.llm_seen = False
        self._stop = threading.Event()
        self._t = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while not self._stop.is_set():
            try:
                out = subprocess.run(["nvidia-smi", "--query-gpu=index,memory.used", "--format=csv,noheader,nounits"],
                                     capture_output=True, text=True, timeout=10).stdout
                for line in out.strip().splitlines():
                    i, m = (int(x) for x in line.split(","))
                    self.peak[i] = max(self.peak.get(i, 0), m)
                apps = subprocess.run(["nvidia-smi", "--query-compute-apps=process_name", "--format=csv,noheader"],
                                      capture_output=True, text=True, timeout=10).stdout
                self.llm_seen |= "llama-server" in apps
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
            self._stop.wait(self.interval)

    def __enter__(self):
        self._t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._t.join(timeout=5)


def free_all_engines(native_port: int) -> None:
    """Ogni configurazione parte con le GPU vuote: un motore che tiene pesi in
    cache ruberebbe VRAM all'altro e ne falserebbe tempi e picchi."""
    import requests
    from core.modules.sigma_creative_lab.backends.comfy_launcher import BASE_PORT
    for port in (BASE_PORT, BASE_PORT + 1):
        try:
            requests.post(f"http://127.0.0.1:{port}/free", json={"unload_models": True, "free_memory": True}, timeout=30)
        except requests.RequestException:
            pass
    try:
        from core.modules.sigma_creative_lab.native.runtime import get_runtime
        rt = get_runtime({"port": native_port})
        if rt.is_alive():
            rt.post("/v1/unload", {}, timeout=120)
    except Exception as e:
        print(f"    unload nativo non riuscito: {e}")
    time.sleep(3)


def contact_sheet(video: Path) -> str:
    from core.modules.sigma_creative_lab.video.production import ffmpeg_bin
    out = video.with_suffix(".sheet.png")
    subprocess.run([ffmpeg_bin(), "-v", "error", "-y", "-i", str(video), "-vf",
                    "select='not(mod(n\\,20))',scale=320:-1,tile=4x2", "-frames:v", "1", str(out)],
                   capture_output=True, timeout=120)
    return str(out) if out.exists() else ""


async def run_native(cfg: dict, args, out: Path, seed: int) -> dict:
    from core.modules.sigma_creative_lab.backends.sigma_native_backend import SigmaNativeBackend
    backend = SigmaNativeBackend(config={"port": args.native_port})
    placement = cfg.get("placement", "offload")
    overrides = dict(cfg.get("load") or {})
    if placement == "none":
        placement, overrides = "offload", {**overrides, "offload_to_cpu": False}
    t_load = time.monotonic()
    loaded = await backend.ensure_profile(cfg["profile"], placement, overrides)
    load_s = time.monotonic() - t_load
    job = {"prompt": PROMPT, "width": args.width, "height": args.height, "video_frames": args.frames,
           "seed": seed, "steps": args.steps, "output_path": str(out), "save_last_frame": False,
           **(cfg.get("job") or {})}
    t0 = time.monotonic()
    record = await backend.run_job({"profile": cfg["profile"], "placement": placement, "load_overrides": overrides,
                                    "job": job})
    timings = record.get("timings") or {}
    return {"wall_s": time.monotonic() - t0, "load_s": load_s, "model_load_s": loaded.get("load_seconds"),
            "sample_s": timings.get("sample_s"), "s_per_step": timings.get("s_per_step"),
            "decode_s": timings.get("decode_s"), "condition_s": timings.get("condition_s"),
            "frames": (record.get("result") or {}).get("frame_count"),
            "has_audio": (record.get("result") or {}).get("has_audio")}


async def run_comfy(cfg: dict, args, out: Path, seed: int) -> dict:
    from core.modules.sigma_creative_lab.backends.comfyui_backend import ComfyUIBackend
    from core.modules.sigma_creative_lab.generators.adapters.comfy_h3 import build_h3_video
    url = args.comfy_url
    if cfg.get("gpu") is not None:
        # Istanza dedicata a quella GPU, avviata se manca (vedi comfy_launcher).
        from core.modules.sigma_creative_lab.backends.comfy_launcher import instances
        url = await asyncio.to_thread(instances.ensure, int(cfg["gpu"]), None, "", 180.0, cfg.get("flags"))
    backend = ComfyUIBackend(base_url=url, config={"timeout": 7200})
    graph = build_h3_video({"prompt": PROMPT, "width": args.width, "height": args.height, "length": args.frames,
                            "seed": seed, "steps": args.steps, "filename_prefix": "sigma/bench",
                            **(cfg.get("graph") or {})})
    steps_seen = []

    def on_progress(p):
        if p.get("progress") is not None:
            steps_seen.append((time.monotonic(), p["progress"]))

    t0 = time.monotonic()
    data, _name = await backend.run({"workflow": graph}, progress_cb=on_progress, timeout_s=7200)
    wall = time.monotonic() - t0
    out.write_bytes(data)
    # ComfyUI notifica l'avanzamento per step: dal primo all'ultimo evento del
    # campionatore si ricava il tempo per step senza caricamento e decodifica.
    sample_s = None
    sampling = [t for t, p in steps_seen if p and 0 < p <= 100]
    if len(sampling) >= 2:
        sample_s = (sampling[-1] - sampling[0]) * args.steps / max(1, args.steps - 1)
    return {"wall_s": wall, "sample_s": sample_s, "s_per_step": sample_s / args.steps if sample_s else None,
            "frames": args.frames, "has_audio": True}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--configs", default="native_q4,comfy_int8")
    ap.add_argument("--frames", type=int, default=124)
    ap.add_argument("--width", type=int, default=864)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--keep", action="store_true", help="aggiunge ai risultati precedenti invece di sostituirli")
    ap.add_argument("--comfy-url", default="http://127.0.0.1:8188")
    ap.add_argument("--native-port", type=int, default=8091)
    ap.add_argument("--out", default=str(ROOT / "var" / "bench_video"))
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    results_file = out_dir / "results.json"
    previous = json.loads(results_file.read_text(encoding="utf-8")) if results_file.exists() and args.keep else []
    results, problems = [], 0

    for name in [c.strip() for c in args.configs.split(",") if c.strip()]:
        cfg = CONFIGS.get(name)
        if not cfg:
            print(f"configurazione sconosciuta: {name}")
            problems += 1
            continue
        free_all_engines(args.native_port)
        for run in range(args.runs):
            video = out_dir / f"{name}_{args.frames}f_run{run}.mp4"
            print(f"[{name}] run {run + 1}/{args.runs} · {cfg['label']}", flush=True)
            with VramSampler() as vram:
                try:
                    runner = run_comfy if cfg["engine"] == "comfyui" else run_native
                    rec = asyncio.run(runner(cfg, args, video, args.seed + run))
                    rec["ok"] = True
                except Exception as e:
                    rec = {"ok": False, "error": str(e)}
                    problems += 1
            rec.update({"config": name, "label": cfg["label"], "run": run, "cold": run == 0,
                        "frames_requested": args.frames, "width": args.width, "height": args.height,
                        "steps": args.steps, "peak_vram_mib": vram.peak, "llm_on_gpu": vram.llm_seen,
                        "video": str(video) if rec.get("ok") else "", "at": time.strftime("%Y-%m-%d %H:%M:%S")})
            if rec.get("ok"):
                rec["sheet"] = contact_sheet(video)
            results.append(rec)
            fmt = lambda v, d=1: "—" if v is None else f"{v:.{d}f}"  # noqa: E731
            print(f"    ok={rec['ok']} wall={fmt(rec.get('wall_s'))}s s/step={fmt(rec.get('s_per_step'), 2)} "
                  f"vram={rec['peak_vram_mib']} {rec.get('error', '')}", flush=True)
            results_file.write_text(json.dumps(previous + results, indent=1, ensure_ascii=False), encoding="utf-8")

    print("\nconfig                 run  wall_s  s/step  peak GPU0  peak GPU1")
    for r in results:
        pk = r.get("peak_vram_mib") or {}
        print(f"{r['config']:<22} {r['run']:>3}  {r.get('wall_s') or 0:>6.1f}  {r.get('s_per_step') or 0:>6.2f}  "
              f"{pk.get(0, 0):>9}  {pk.get(1, 0):>9}  {'' if r['ok'] else 'ERRORE'}")
    print("SIGMA-CHECK " + json.dumps({"check": "bench_video", "checked": len(results), "problems": problems}))


if __name__ == "__main__":
    main()
