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


def runtime_env() -> Dict[str, str]:
    """Ambiente di esecuzione con i percorsi DLL dei runtime di calcolo iniettati.

    Su Windows le librerie di calcolo (CUDA in torch/lib o CUDA toolkit, oneAPI
    per SYCL, ROCm/HIP, Vulkan SDK) vivono in cartelle dedicate. Senza iniettarle
    nel PATH del sottoprocesso, Windows non risolve le dipendenze di
    ggml-cuda.dll o ggml-sycl.dll e llama.cpp ripiega silenziosamente sul
    backend CPU.
    """
    env = os.environ.copy()
    extra_paths = []

    # 1. Cartella del runtime stesso (dove vivono le DLL di llama.cpp)
    srv = installed_server()
    if srv:
        extra_paths.append(str(srv.parent))

    # 2. PyTorch lib (porta cudart64_*.dll, cublas64_*.dll, c10_cuda, hip, etc.)
    try:
        import torch
        tlib = os.path.join(os.path.dirname(torch.__file__), "lib")
        if os.path.isdir(tlib):
            extra_paths.append(tlib)
    except Exception:
        pass

    # 3. CUDA_PATH / CUDA toolkit
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path and os.path.isdir(cuda_path):
        cbin = os.path.join(cuda_path, "bin")
        if os.path.isdir(cbin):
            extra_paths.append(cbin)

    # 4. HIP / ROCm
    hip_path = os.environ.get("HIP_PATH")
    if hip_path and os.path.isdir(hip_path):
        hbin = os.path.join(hip_path, "bin")
        if os.path.isdir(hbin):
            extra_paths.append(hbin)

    # 5. oneAPI (Intel SYCL)
    oneapi_root = os.environ.get("ONEAPI_ROOT") or os.environ.get("CMPLR_ROOT")
    if oneapi_root and os.path.isdir(oneapi_root):
        for sub in ("bin", "compiler/latest/windows/bin", "mkl/latest/bin"):
            p = os.path.join(oneapi_root, sub)
            if os.path.isdir(p):
                extra_paths.append(p)

    # 6. Vulkan SDK
    vulkan_sdk = os.environ.get("VULKAN_SDK")
    if vulkan_sdk and os.path.isdir(vulkan_sdk):
        vbin = os.path.join(vulkan_sdk, "bin")
        if os.path.isdir(vbin):
            extra_paths.append(vbin)

    if extra_paths:
        current_path = env.get("PATH", "")
        nuovi = [p for p in extra_paths if p not in current_path]
        if nuovi:
            env["PATH"] = os.pathsep.join(nuovi) + os.pathsep + current_path

    return env


def setup_dll_directories() -> None:
    """Registra le directory DLL nel processo Python corrente (Windows)."""
    if os.name != "nt" or not hasattr(os, "add_dll_directory"):
        return
    env = runtime_env()
    for p in env.get("PATH", "").split(os.pathsep):
        if p and os.path.isdir(p):
            try:
                os.add_dll_directory(p)
            except Exception:
                pass



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
    "windows-x64-sycl":   ["win-sycl-x64", "win-vulkan-x64", "win-cpu-x64"],
    "windows-x64-vulkan": ["win-vulkan-x64", "win-cpu-x64"],
    "windows-x64-cpu":    ["win-cpu-x64"],
    "windows-arm64-cpu":  ["win-cpu-arm64"],

    "linux-x64-cuda":     ["ubuntu-x64"],
    "linux-x64-rocm":     ["ubuntu-rocm-{rocm}-x64", "ubuntu-vulkan-x64", "ubuntu-x64"],
    "linux-x64-sycl":     ["ubuntu-sycl-fp16-x64", "ubuntu-sycl-fp32-x64",
                           "ubuntu-vulkan-x64", "ubuntu-x64"],
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
    if compute not in ("cuda", "rocm", "vulkan", "metal", "sycl"):
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

def _versione_cuda(acceleratori=None) -> Optional[str]:
    """La versione CUDA nel formato degli archivi (es. "12.4").

    Guarda prima le librerie CUDA effettivamente presenti nell'ambiente
    attivo (es. torch/lib o CUDA toolkit) e solo dopo ripiega sul driver.
    """
    # 1. Ispeziona prima le DLL del runtime CUDA presenti nel PATH / torch
    try:
        import torch
        versione = getattr(torch, "version", None)
        grezza = getattr(versione, "cuda", None) if versione else None
        if grezza:
            parti = str(grezza).split(".")
            v = f"{parti[0]}.{parti[1]}" if len(parti) >= 2 else str(grezza)
            # Normalizza per gli archivi pubblicati
            if v.startswith("12."):
                return "12.4"
            if v.startswith("13."):
                return "13.3"
            if v.startswith("11."):
                return "11.8"
            return v
    except Exception:
        pass

    try:
        env = runtime_env()
        for p in env.get("PATH", "").split(os.pathsep):
            if p and os.path.isdir(p):
                try:
                    for f in os.listdir(p):
                        fl = f.lower()
                        if fl.startswith("cudart64_") and fl.endswith(".dll"):
                            if "12" in fl:
                                return "12.4"
                            elif "13" in fl:
                                return "13.3"
                            elif "11" in fl:
                                return "11.8"
                except Exception:
                    continue
    except Exception:
        pass

    # 2. Driver nvidia-smi
    try:
        from sigma_launcher import _nvidia_smi_cuda_version
        nv = _nvidia_smi_cuda_version()
        if nv:
            return f"{nv[0]}.{nv[1]}"
    except Exception:
        pass

    return None


def describe_machine() -> Dict[str, Any]:
    """Sistema, architettura e acceleratore, nel vocabolario di questo modulo.

    L'acceleratore lo decide core/engine/gpu_vendors, che guarda due cose
    separate: quali schede ci sono e quali runtime si aprono davvero. Sceglierlo
    dalle sole schede farebbe scaricare una build ROCm su una macchina senza HIP
    SDK, o una SYCL senza oneAPI: un binario che non apre le proprie librerie,
    cioe' l'errore al primo avvio che tutto questo lavoro serve a togliere.
    """
    try:
        from core.engine.gpu_vendors import preferred_compute
        compute = preferred_compute()
    except Exception as exc:
        log.warning("[LlamaRuntime] Rilevamento acceleratore fallito (%s): uso la CPU.", exc)
        compute = "cpu"

    cuda_version = _versione_cuda(None) if compute == "cuda" else None

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
        if not cartella.is_dir() or cartella.name.startswith("."):
            continue
        for candidato in cartella.rglob(SERVER_EXE):
            if candidato.is_file():
                return candidato
    return None


def installed_build_info() -> Optional[Dict[str, Any]]:
    """Che tipo di build e' installata: CUDA, Vulkan, SYCL o solo CPU.

    Ispeziona le DLL presenti nella cartella del runtime. E' l'unico modo di
    sapere se la macchina sta usando le GPU che ha: un llama-server.exe che
    esiste non dice niente su quali backend ha a disposizione.
    """
    server = installed_server()
    if server is None:
        return None

    cartella = server.parent
    nomi = {f.name.lower() for f in cartella.iterdir() if f.is_file()}

    acceleratori = []
    if any(n.startswith("ggml-cuda") for n in nomi):
        acceleratori.append("cuda")
    if any(n.startswith("ggml-vulkan") or n == "vulkan-1.dll" for n in nomi):
        acceleratori.append("vulkan")
    if any(n.startswith("ggml-sycl") for n in nomi):
        acceleratori.append("sycl")
    if any(n.startswith("ggml-rocm") or n.startswith("ggml-hip") for n in nomi):
        acceleratori.append("rocm")
    if any(n.startswith("ggml-metal") for n in nomi):
        acceleratori.append("metal")

    # Le varianti CPU (sse42, haswell, zen4...) sono sempre presenti nelle build
    # ufficiali, anche in quelle accelerate.
    varianti_cpu = [n for n in nomi if n.startswith("ggml-cpu-")]

    tipo = acceleratori[0] if acceleratori else "cpu"
    return {
        "server": str(server),
        "cartella": str(cartella),
        "tipo": tipo,
        "acceleratori": acceleratori,
        "varianti_cpu": len(varianti_cpu),
        "build": cartella.name,
    }


def needs_upgrade() -> Optional[str]:
    """Se la build installata non e' quella ottimale per questa macchina o non puo' caricare le DLL.

    Una build CPU-only o con dipendenze CUDA non corrispondenti costringe
    llama.cpp a ripiegare sulla CPU.
    """
    info = installed_build_info()
    if info is None:
        return "Nessun runtime installato."

    macchina = describe_machine()
    compute = macchina.get("compute", "cpu")

    if compute == "cpu":
        return None  # La build CPU e' corretta per una macchina senza GPU.

    if compute not in info.get("acceleratori", []):
        return (
            f"La build installata e' '{info['tipo']}' ma questa macchina ha "
            f"'{compute}'. Le GPU non vengono usate. Serve la build con "
            f"supporto {compute}."
        )

    # Verifica se le DLL dell'acceleratore riescono effettivamente a caricarsi
    if compute == "cuda":
        cartella = info.get("cartella")
        if cartella:
            dll_path = os.path.join(cartella, "ggml-cuda.dll")
            if os.path.isfile(dll_path):
                setup_dll_directories()
                try:
                    import ctypes
                    ctypes.CDLL(dll_path)
                except Exception as exc:
                    return f"ggml-cuda.dll non carica le proprie dipendenze ({exc}). Richiesto cambio build."

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
            macchina: Dict[str, Any] = None,
            force: bool = False) -> Dict[str, Any]:
    """Scarica e installa il runtime giusto per questa macchina.

    `macchina` permette di forzare la scelta — serve per provare la variante
    CPU su una macchina che ne prenderebbe una accelerata, e per riprovare
    quando l'acceleratore rilevato non ha dato un runtime funzionante.
    `force=True` riscarica anche se il runtime e' gia' presente.
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
    server_esistente = destinazione / SERVER_EXE
    if not server_esistente.exists():
        server_esistente = next(destinazione.rglob(SERVER_EXE), None)

    if not force and server_esistente and server_esistente.is_file():
        info = installed_build_info()
        compute_richiesto = (macchina.get("compute") or "cpu").lower()
        
        # Se la build installata soddisfa l'acceleratore richiesto, siamo a posto.
        ha_acceleratore = (
            compute_richiesto == "cpu"
            or (info and compute_richiesto in info.get("acceleratori", []))
        )
        if ha_acceleratore:
            avvisa(f"Runtime gia' presente e ottimale ({info.get('tipo', 'cpu') if info else 'ok'}).")
            return {"success": True, "build": release["build"],
                    "server": str(server_esistente), "gia_presente": True,
                    "asset": nome, "macchina": macchina}
        else:
            avvisa(f"Runtime presente ({info.get('tipo') if info else 'non ottimale'}) ma e' richiesto '{compute_richiesto}': aggiorno...")
            shutil.rmtree(destinazione, ignore_errors=True)

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
