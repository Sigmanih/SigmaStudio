"""Confronto riproducibile: stesso checkpoint Sigma, worker diretto e proxy Rust."""
from __future__ import annotations

import argparse
from contextlib import ExitStack
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import statistics
import subprocess
import tempfile
import time
import threading
import urllib.error
import urllib.request

from core.logger import get_logger

log = get_logger(__name__)


def porta_libera() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def attesa(url: str, processo: subprocess.Popen, timeout: float = 180) -> None:
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if processo.poll() is not None:
            raise RuntimeError(f"Processo terminato prima di essere pronto: {processo.returncode}")
        try:
            with urllib.request.urlopen(url + "/health", timeout=1) as risposta:
                if risposta.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise TimeoutError(f"Servizio non pronto entro {timeout}s: {url}")


def misura(url: str, corpo: dict, token: str = "", timeout: float = 180, on_content=None) -> dict:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Sigma-Token"] = token
    richiesta = urllib.request.Request(url + "/v1/chat/completions",
                                       data=json.dumps(corpo).encode(), headers=headers)
    inizio = time.perf_counter()
    primo = None
    fine_contenuto = None
    contenuto = []
    usage = {}
    timings = {}
    telemetria = {}
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
        for linea in risposta:
            if not linea.startswith(b"data:"):
                continue
            dato = linea[5:].strip()
            if dato == b"[DONE]":
                continue
            evento = json.loads(dato)
            if "error" in evento:
                raise RuntimeError(str(evento["error"]))
            usage = evento.get("usage") or usage
            timings = evento.get("timings") or timings
            telemetria = evento.get("sigma_telemetry") or telemetria
            for scelta in evento.get("choices", []):
                delta = scelta.get("delta") or {}
                testo = delta.get("content") or delta.get("reasoning_content") or ""
                if testo:
                    adesso = time.perf_counter()
                    if primo is None and on_content:
                        on_content()
                    primo = primo or adesso
                    fine_contenuto = adesso
                    contenuto.append(testo)
    durata = time.perf_counter() - inizio
    if primo is None:
        raise RuntimeError("Il modello non ha prodotto contenuto")
    numero = usage.get("completion_tokens")
    if numero is None:
        numero = timings.get("predicted_n")
    testo = "".join(contenuto)
    return {
        "ttft_ms": (primo - inizio) * 1000,
        "elapsed_ms": durata * 1000,
        "completion_tokens": numero,
        "e2e_tokens_per_second": numero / durata if numero else None,
        "worker_decode_tokens_per_second": timings.get("predicted_per_second"),
        "content_span_ms": (fine_contenuto - primo) * 1000,
        "output_sha256": hashlib.sha256(testo.encode()).hexdigest(),
        "output": testo,
        "proxy_telemetry": telemetria,
        "usage":usage,"timings":timings,
    }


def confronta(worker_url: str, rust_url: str, token: str, model: str,
              ripetizioni: int = 3, max_tokens: int = 64) -> dict:
    if not 1 <= ripetizioni <= 20 or not 1 <= max_tokens <= 4096:
        raise ValueError("Ripetizioni o budget token fuori intervallo")
    corpo = {
        "model": model,
        "messages": [{"role": "user", "content": "Scrivi in italiano cinque consigli concreti per ottimizzare un programma Python."}],
        "temperature": 0, "seed": 123, "max_tokens": max_tokens,
        "stream": True, "stream_options": {"include_usage": True},
        "cache_prompt": False, "chat_template_kwargs": {"enable_thinking": False},
    }
    percorsi = {"sigma_direct": (worker_url, ""), "sigma_rust": (rust_url, token)}
    for url, chiave in percorsi.values():
        misura(url, {**corpo, "max_tokens": 8}, chiave)
    risultati = {nome: [] for nome in percorsi}
    for giro in range(ripetizioni):
        ordine = list(percorsi) if giro % 2 == 0 else list(reversed(percorsi))
        for nome in ordine:
            log.info("Confronto Sigma: giro %s/%s, %s", giro + 1, ripetizioni, nome)
            url, chiave = percorsi[nome]
            risultati[nome].append(misura(url, corpo, chiave))
    mediane = {}
    for nome, prove in risultati.items():
        mediane[nome] = {}
        for metrica in ("ttft_ms", "elapsed_ms", "e2e_tokens_per_second", "worker_decode_tokens_per_second"):
            valori = [prova[metrica] for prova in prove if prova[metrica] is not None]
            mediane[nome][metrica] = statistics.median(valori) if valori else None
    return {"model": model, "repetitions": ripetizioni, "request": corpo,
            "cache_prompt": False, "order": "alternating", "medians": mediane,
            "outputs_match": all(a["output_sha256"] == b["output_sha256"] for a, b in
                                 zip(risultati["sigma_direct"], risultati["sigma_rust"])),
            "runs": risultati}


def confronta_coda(rust_url: str, token: str, model: str) -> dict:
    corpo = {"model": model, "messages": [{"role": "user", "content": "Elenca dieci consigli per ottimizzare Python."}],
             "temperature": 0, "seed": 123, "stream": True, "cache_prompt": False,
             "stream_options": {"include_usage": True}, "chat_template_kwargs": {"enable_thinking": False}}
    primo = threading.Event()
    with ThreadPoolExecutor(max_workers=3) as executor:
        running = executor.submit(misura, rust_url, {**corpo, "max_tokens": 64, "priority": "normal"},
                                  token, 180, primo.set)
        if not primo.wait(30):
            raise TimeoutError("Il lavoro iniziale non ha prodotto token")
        low = executor.submit(misura, rust_url, {**corpo, "max_tokens": 64, "priority": "low"}, token)
        # Il primo lavoro tiene il worker occupato mentre le altre richieste si accodano.
        time.sleep(0.1)
        high = executor.submit(misura, rust_url, {**corpo, "max_tokens": 8, "priority": "critical"}, token)
        running.result(timeout=180)
        low_result, high_result = low.result(timeout=180), high.result(timeout=180)
    return {"critical_ttft_ms": high_result["ttft_ms"], "low_ttft_ms": low_result["ttft_ms"],
            "critical_queue_wait_ms": high_result["proxy_telemetry"].get("inference_queue_wait_ms"),
            "low_queue_wait_ms": low_result["proxy_telemetry"].get("inference_queue_wait_ms"),
            "critical": high_result, "low": low_result}


def _arresta(processo: subprocess.Popen) -> None:
    if processo.poll() is None:
        processo.terminate()
        try:
            processo.wait(timeout=10)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait(timeout=10)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-file", type=Path, required=True)
    parser.add_argument("--kernel-binary", type=Path, required=True)
    parser.add_argument("--worker-binary", type=Path)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--ram-bytes", type=int)
    parser.add_argument("--queue-check", action="store_true")
    parser.add_argument("--feature-check",action="store_true")
    parser.add_argument("--parallel-slots",type=int,default=1,choices=range(1,5))
    args = parser.parse_args()
    problemi = 0
    try:
        with socket.socket() as controllo:
            controllo.settimeout(0.5)
            if controllo.connect_ex(("127.0.0.1", 8000)) == 0:
                raise RuntimeError("Server di sviluppo attivo sulla porta 8000: confronto sospeso")
        if not args.model_file.is_file() or not args.kernel_binary.is_file():
            raise FileNotFoundError("Modello o binario kernel assente")
        from core.engine.llama_runtime import installed_server, runtime_env
        worker = args.worker_binary or installed_server()
        if not worker or not worker.is_file():
            raise FileNotFoundError("Runtime llama-server assente")
        with ExitStack() as stack:
            temporanea = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix="sigma-comparison-")))
            porta_worker, porta_rust = porta_libera(), porta_libera()
            worker_url, rust_url = f"http://127.0.0.1:{porta_worker}", f"http://127.0.0.1:{porta_rust}"
            token = secrets.token_hex(32)
            worker_log = stack.enter_context(tempfile.TemporaryFile())
            rust_log = stack.enter_context(tempfile.TemporaryFile())
            nascosto = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            processo = subprocess.Popen([str(worker), "--model", str(args.model_file.resolve()),
                                        "--host", "127.0.0.1", "--port", str(porta_worker),
                                        "-ngl", "99", "-c", str(2048*args.parallel_slots), "-np", str(args.parallel_slots), "--jinja",
                                        "--slot-save-path",str(temporanea)],
                                       env=runtime_env(), stdout=worker_log, stderr=subprocess.STDOUT,
                                       creationflags=nascosto)
            stack.callback(_arresta, processo)
            try:
                attesa(worker_url, processo)
                ambiente = {**os.environ, "PORT": str(porta_rust), "SIGMA_BIND_ADDR": "127.0.0.1",
                            "SIGMA_ENGINE_TOKEN": token, "SIGMA_ENGINE_TOKEN_FILE": str(temporanea / "token"),
                            "SIGMA_WORKSPACE_ROOT": str(temporanea), "SIGMA_TIER_DISK_DIR": str(temporanea),
                            "SIGMA_UPSTREAM_COMPUTE_URL": worker_url,
                            "SIGMA_RUST_PIPE_NAME": rf"\\.\pipe\sigma_bench_{porta_rust}"}
                if args.ram_bytes is not None:
                    ambiente["SIGMA_RAM_BYTES"] = str(args.ram_bytes)
                kernel = subprocess.Popen([str(args.kernel_binary.resolve())], env=ambiente,
                                          stdout=rust_log, stderr=subprocess.STDOUT, creationflags=nascosto)
                stack.callback(_arresta, kernel)
                attesa(rust_url, kernel, timeout=30)
                report = confronta(worker_url, rust_url, token, args.model_file.stem,
                                   args.repetitions, args.max_tokens)
                report["model_file"] = str(args.model_file.resolve())
                report["model_bytes"] = args.model_file.stat().st_size
                report["worker_binary"] = str(worker)
                report["kernel_binary"] = str(args.kernel_binary.resolve())
                report["ram_bytes_override"] = args.ram_bytes
                if args.queue_check:
                    report["priority_queue"] = confronta_coda(rust_url, token, args.model_file.stem)
                if args.feature_check:
                    from tools.benchmarks.kernel_feature_checks import check_features
                    report["features"]=check_features(worker_url,rust_url,token,temporanea,args.model_file,args.parallel_slots)
                print(json.dumps(report, ensure_ascii=False))
            except Exception:
                for nome, uscita in (("worker", worker_log), ("kernel", rust_log)):
                    uscita.seek(0, 2)
                    uscita.seek(max(0, uscita.tell() - 5000))
                    log.error("Ultima uscita %s: %s", nome, uscita.read().decode(errors="replace"))
                raise
    except Exception as exc:
        problemi = 1
        log.error("Confronto non completato: %s: %s", type(exc).__name__, exc)
    print("SIGMA-CHECK " + json.dumps({"check": "sigma_inference_comparison",
                                      "checked": args.repetitions * 2 + (3 if args.queue_check else 0) + len(report.get("features",{})) if not problemi else 0,
                                      "problems": problemi}))
    return problemi


if __name__ == "__main__":
    raise SystemExit(main())
