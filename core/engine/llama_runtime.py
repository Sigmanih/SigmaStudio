# ==============================================================================
# core/engine/llama_runtime.py — Il runtime GGUF che gira ovunque
#
# Sigma Studio ha installato finora `llama-cpp-python`, prendendo ruote
# precompilate da un indice di terze parti. Quella strada ha quattro punti di
# rottura, e tre si sono gia' manifestati:
#
#   1. Le ruote sono compilate con flag fissi (AVX2, FMA). Su un processore che
#      non li ha, il primo kernel vettoriale eseguito fa saltare tutto con
#      STATUS_ILLEGAL_INSTRUCTION. E' la segnalazione arrivata da un utente al
#      primo avvio della chat.
#   2. Esistono per una manciata di versioni di Python. Su 3.13 il codice gia'
#      avvisa che dovra' ripiegare sulla compilazione da sorgente.
#   3. Compilare da sorgente richiede un compilatore: MSVC su Windows, che
#      nessuno ha per caso, e minuti di build su una scheda piccola.
#   4. L'indice e' mantenuto da una persona sola: se smette di pubblicare per
#      una versione, l'installazione fallisce e non c'e' alternativa.
#
# I binari ufficiali di ggml-org/llama.cpp non hanno nessuno di questi
# problemi. Le build CPU sono prodotte con:
#
#     -DGGML_NATIVE=OFF -DGGML_CPU_ALL_VARIANTS=ON -DGGML_BACKEND_DL=ON
#
# cioe' nessuna istruzione cablata, tutte le varianti CPU compilate, e la
# selezione fatta a runtime in base a quello che il processore dichiara. Un
# solo archivio copre ogni x86-64 in circolazione. Non serve un compilatore,
# non dipendono dalla versione di Python, e coprono molti piu' acceleratori di
# quanti ne raggiungiamo oggi: Vulkan (che su Windows apre le GPU AMD e Intel),
# ROCm, SYCL, OpenVINO, CUDA, oltre a macOS arm64 e Android.
#
# Questo modulo sceglie l'archivio giusto per la macchina e lo installa. Non
# decide da solo di scaricare: la scelta e' separata dal download, perche' la
# prima si puo' verificare in un test e il secondo no.
# ==============================================================================
from __future__ import annotations

import json
import os
import platform
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

RELEASES_API = "https://api.github.com/repos/ggml-org/llama.cpp/releases"

#: Nome dell'eseguibile che serve a noi: espone un'API HTTP compatibile OpenAI,
#: cioe' quella che Sigma Studio gia' parla.
SERVER_EXE = "llama-server.exe" if os.name == "nt" else "llama-server"


def runtime_dir() -> Path:
    """Dove vivono i runtime scaricati. In store/: si riscarica, non si perde."""
    return paths.store_dir() / "engine_runtime"


# ==============================================================================
# SCELTA DELL'ARCHIVIO
# ==============================================================================
# Gli archivi si chiamano llama-<build>-bin-<sistema>-<variante>-<arch>.<ext>.
# La scelta e' una funzione pura di (sistema, architettura, acceleratore), cosi'
# si puo' verificare senza rete: e' la parte che sbagliata manda in crash la
# macchina di qualcun altro.

#: In ordine di preferenza per ogni combinazione. Il primo che esiste vince.
#: La variante CPU e' sempre in coda ed e' sempre presente: e' la garanzia che
#: un'installazione riesca comunque, su qualunque hardware.
_PREFERENZE: Dict[str, List[str]] = {
    "windows-x64-cuda":   ["win-cuda-{cuda}-x64", "win-vulkan-x64", "win-cpu-x64"],
    "windows-x64-rocm":   ["win-rocm-{rocm}-x64", "win-vulkan-x64", "win-cpu-x64"],
    "windows-x64-vulkan": ["win-vulkan-x64", "win-cpu-x64"],
    "windows-x64-cpu":    ["win-cpu-x64"],
    "windows-arm64-cpu":  ["win-cpu-arm64"],

    "linux-x64-cuda":     ["ubuntu-x64"],
    "linux-x64-rocm":     ["ubuntu-rocm-{rocm}-x64", "ubuntu-vulkan-x64", "ubuntu-x64"],
    "linux-x64-vulkan":   ["ubuntu-vulkan-x64", "ubuntu-x64"],
    "linux-x64-cpu":      ["ubuntu-x64"],
    "linux-arm64-vulkan": ["ubuntu-vulkan-arm64", "ubuntu-arm64"],
    "linux-arm64-cpu":    ["ubuntu-arm64"],

    "darwin-arm64-metal": ["macos-arm64"],
    "darwin-arm64-cpu":   ["macos-arm64"],
    "darwin-x64-cpu":     ["macos-x64"],
}


def _chiave(sistema: str, arch: str, compute: str) -> str:
    sistema = (sistema or "").lower()
    if sistema.startswith("win"):
        sistema = "windows"
    elif sistema == "darwin":
        sistema = "darwin"
    else:
        sistema = "linux"

    arch = (arch or "").lower()
    arch = "arm64" if arch in ("arm64", "aarch64") else "x64"

    compute = (compute or "cpu").lower()
    if compute not in ("cuda", "rocm", "vulkan", "metal"):
        compute = "cpu"

    return f"{sistema}-{arch}-{compute}"


def candidate_variants(sistema: str = None, arch: str = None, compute: str = "cpu",
                       cuda_version: str = None, rocm_version: str = None) -> List[str]:
    """Le varianti da provare per questa macchina, dalla migliore alla piu' sicura.

    L'ultima e' sempre una build CPU: su qualunque hardware, un'installazione
    deve poter riuscire. E' il requisito che rende Sigma Studio installabile
    ovunque, non solo dove c'e' l'acceleratore giusto.
    """
    sistema = sistema or platform.system()
    arch = arch or platform.machine()
    chiave = _chiave(sistema, arch, compute)

    varianti = _PREFERENZE.get(chiave)
    if varianti is None:
        # Combinazione non prevista: si ripiega sulla CPU dello stesso sistema.
        varianti = _PREFERENZE.get(_chiave(sistema, arch, "cpu"), [])

    risolte = []
    for variante in varianti:
        if "{cuda}" in variante:
            if not cuda_version:
                continue
            variante = variante.replace("{cuda}", cuda_version)
        if "{rocm}" in variante:
            if not rocm_version:
                continue
            variante = variante.replace("{rocm}", rocm_version)
        if variante not in risolte:
            risolte.append(variante)
    return risolte


def _estensione(variante: str) -> str:
    return ".zip" if variante.startswith("win-") else ".tar.gz"


def asset_name(build: str, variante: str) -> str:
    return f"llama-{build}-bin-{variante}{_estensione(variante)}"


def _cuda_disponibili(assets: List[str], build: str, sistema: str) -> List[str]:
    """Le versioni CUDA per cui esiste un archivio, dalla piu' recente."""
    prefisso = f"llama-{build}-bin-{'win' if sistema == 'windows' else 'ubuntu'}-cuda-"
    versioni = []
    for nome in assets:
        if not nome.startswith(prefisso):
            continue
        resto = nome[len(prefisso):].split("-")[0]
        try:
            versioni.append(tuple(int(x) for x in resto.split(".")))
        except ValueError:
            continue
    return [".".join(str(x) for x in v) for v in sorted(set(versioni), reverse=True)]


def _cuda_compatibile(nostra: Optional[str], disponibili: List[str]) -> Optional[str]:
    """La build CUDA da usare, o None se nessuna e' adatta.

    Il criterio e' la versione *maggiore*: il runtime CUDA e' compatibile in
    avanti nei minori, non fra maggiori. Installare una build cuda-12 su un
    sistema con CUDA 13 non da' un errore chiaro, da' un caricamento che
    fallisce all'apertura della libreria. Meglio nessuna build CUDA e ripiegare
    su Vulkan o CPU, che funzionano.
    """
    if not disponibili:
        return None
    if not nostra:
        return None

    try:
        maggiore, minore = (int(x) for x in nostra.split(".")[:2])
    except ValueError:
        return None

    stesso_maggiore = []
    for versione in disponibili:
        v_mag, v_min = (int(x) for x in versione.split(".")[:2])
        if v_mag == maggiore:
            stesso_maggiore.append((v_min, versione))
    if not stesso_maggiore:
        return None

    # La piu' alta che non supera la nostra; se il driver e' piu' vecchio di
    # ogni build pubblicata, la piu' bassa fra quelle dello stesso maggiore.
    non_superiori = [v for v in stesso_maggiore if v[0] <= minore]
    scelta = max(non_superiori) if non_superiori else min(stesso_maggiore)
    return scelta[1]


def select_asset(assets: List[str], build: str, **macchina) -> Optional[str]:
    """Il primo archivio disponibile fra quelli buoni per questa macchina.

    Per CUDA la versione non viene indovinata da una lista fissa: si guarda
    quali build esistono davvero in questa release e si sceglie quella dello
    stesso maggiore. Una lista fissa invecchia insieme alle release, e il
    giorno in cui llama.cpp smette di pubblicare cuda-12.4 farebbe ripiegare
    ogni macchina NVIDIA sulla CPU.
    """
    disponibili = set(assets)

    if (macchina.get("compute") or "").lower() == "cuda":
        sistema = _chiave(macchina.get("sistema"), macchina.get("arch"), "cuda").split("-")[0]
        versione = _cuda_compatibile(
            macchina.get("cuda_version"), _cuda_disponibili(assets, build, sistema))
        if versione:
            macchina = dict(macchina, cuda_version=versione)
        else:
            # Nessuna build CUDA adatta: si scende ai ripieghi della stessa
            # macchina senza fingere che una build di un altro maggiore vada.
            macchina = dict(macchina, cuda_version=None)

    for variante in candidate_variants(**macchina):
        nome = asset_name(build, variante)
        if nome in disponibili:
            return nome
    return None


# ==============================================================================
# RILEVAMENTO DELLA MACCHINA
# ==============================================================================

def _versione_cuda(acceleratori) -> Optional[str]:
    """La versione CUDA nel formato degli archivi (es. "12.4").

    Serve a scegliere fra le build cuda pubblicate. Se non si riesce a
    stabilirla, la lista delle preferenze salta la voce che la richiede e
    ripiega su una build che esiste comunque.
    """
    try:
        import torch
        versione = getattr(torch, "version", None)
        grezza = getattr(versione, "cuda", None) if versione else None
        if grezza:
            parti = str(grezza).split(".")
            return f"{parti[0]}.{parti[1]}" if len(parti) >= 2 else str(grezza)
    except Exception:
        pass
    return None


def describe_machine() -> Dict[str, Any]:
    """Sistema, architettura e acceleratore, nel vocabolario di questo modulo."""
    compute = "cpu"
    cuda_version = None

    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        sonda = UniversalHardwareProbe.probe_accelerators()
        # La sonda descrive il tipo per esteso — "NVIDIA_CUDA", "AMD_ROCM",
        # "APPLE_METAL" — quindi si cerca dentro la stringa invece di
        # confrontarla: un uguale qui riportava "cpu" su una macchina con due
        # schede NVIDIA, e avrebbe fatto scaricare la build sbagliata.
        tipi = " ".join(str(a.get("type", "")).lower() for a in (sonda or []))
        if "cuda" in tipi or "nvidia" in tipi:
            compute = "cuda"
            cuda_version = _versione_cuda(sonda)
        elif "rocm" in tipi or "hip" in tipi:
            compute = "rocm"
        elif "metal" in tipi or "mps" in tipi:
            compute = "metal"
        elif "vulkan" in tipi or "directml" in tipi or "intel" in tipi:
            compute = "vulkan"
    except Exception as exc:
        log.debug("[LlamaRuntime] Sonda acceleratori non disponibile: %s", exc)

    if compute == "cpu" and platform.system() == "Darwin":
        if platform.machine().lower() in ("arm64", "aarch64"):
            compute = "metal"

    return {
        "sistema": platform.system(),
        "arch": platform.machine(),
        "compute": compute,
        "cuda_version": cuda_version,
    }


# ==============================================================================
# INSTALLAZIONE
# ==============================================================================

def latest_build(timeout: int = 15) -> Optional[Dict[str, Any]]:
    """L'ultima release che contiene davvero dei binari.

    La release marcata "latest" e' un puntatore che contiene solo un file di
    testo: i binari stanno nelle build numerate (bNNNNN), quindi si scorre
    finche' non se ne trova una con degli archivi dentro.
    """
    richiesta = urllib.request.Request(
        f"{RELEASES_API}?per_page=10",
        headers={"User-Agent": "SigmaStudio", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            releases = json.loads(risposta.read().decode("utf-8"))
    except Exception as exc:
        log.warning("[LlamaRuntime] Elenco release non raggiungibile: %s", exc)
        return None

    for release in releases:
        archivi = [a for a in release.get("assets", [])
                   if a.get("name", "").startswith("llama-")
                   and a.get("name", "").endswith((".zip", ".tar.gz"))]
        if archivi:
            return {
                "build": release.get("tag_name", ""),
                "assets": {a["name"]: a["browser_download_url"] for a in archivi},
            }
    return None


def installed_server() -> Optional[Path]:
    """Il llama-server installato piu' recente, se ce n'e' uno."""
    radice = runtime_dir()
    if not radice.is_dir():
        return None
    for cartella in sorted(radice.iterdir(), reverse=True):
        if not cartella.is_dir():
            continue
        for candidato in cartella.rglob(SERVER_EXE):
            if candidato.is_file():
                return candidato
    return None


def _estrai(archivio: Path, destinazione: Path) -> None:
    destinazione.mkdir(parents=True, exist_ok=True)
    if archivio.suffix == ".zip":
        with zipfile.ZipFile(archivio) as zf:
            zf.extractall(destinazione)
    else:
        with tarfile.open(archivio, "r:gz") as tf:
            tf.extractall(destinazione)


def install(progress=None, timeout: int = 600,
            macchina: Dict[str, Any] = None) -> Dict[str, Any]:
    """Scarica e installa il runtime giusto per questa macchina.

    `macchina` permette di forzare la scelta — serve per provare la variante
    CPU su una macchina che ne prenderebbe una accelerata, e per riprovare
    quando l'acceleratore rilevato non ha dato un runtime funzionante.
    """
    def avvisa(testo: str) -> None:
        log.info("[LlamaRuntime] %s", testo)
        if progress:
            progress(testo)

    release = latest_build()
    if release is None:
        return {"success": False, "error": "Nessuna release di llama.cpp raggiungibile."}

    macchina = macchina or describe_machine()
    nome = select_asset(list(release["assets"]), release["build"], **macchina)
    if nome is None:
        return {
            "success": False,
            "error": (f"Nessun archivio disponibile per {macchina['sistema']} "
                      f"{macchina['arch']} ({macchina['compute']})."),
            "macchina": macchina,
        }

    avvisa(f"Runtime scelto per questa macchina: {nome}")

    destinazione = runtime_dir() / release["build"]
    if (destinazione / SERVER_EXE).exists() or any(destinazione.rglob(SERVER_EXE)):
        avvisa("Runtime gia' presente.")
        return {"success": True, "build": release["build"],
                "server": str(installed_server()), "gia_presente": True}

    paths.ensure(runtime_dir())
    temporaneo = runtime_dir() / f".{nome}"
    try:
        avvisa(f"Scarico {nome}...")
        richiesta = urllib.request.Request(
            release["assets"][nome], headers={"User-Agent": "SigmaStudio"})
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta, \
                open(temporaneo, "wb") as uscita:
            shutil.copyfileobj(risposta, uscita)

        avvisa("Estraggo...")
        _estrai(temporaneo, destinazione)
    except Exception as exc:
        shutil.rmtree(destinazione, ignore_errors=True)
        return {"success": False, "error": f"Installazione fallita: {exc}"}
    finally:
        temporaneo.unlink(missing_ok=True)

    server = installed_server()
    if server is None:
        shutil.rmtree(destinazione, ignore_errors=True)
        return {"success": False,
                "error": f"L'archivio {nome} non conteneva {SERVER_EXE}."}

    if os.name != "nt":
        try:
            server.chmod(server.stat().st_mode | 0o111)
        except OSError:
            pass

    avvisa(f"Runtime pronto: {server}")
    return {"success": True, "build": release["build"], "asset": nome,
            "server": str(server), "macchina": macchina}
