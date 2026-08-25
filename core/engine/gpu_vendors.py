# ==============================================================================
# core/engine/gpu_vendors.py — Che schede ci sono, e quali runtime sono davvero qui
#
# Due domande diverse, che vanno tenute separate perche' rispondono a bisogni
# diversi:
#
#   1. Che schede ha questa macchina?  → decide che prestazioni sono possibili
#   2. Quali runtime sono installati?  → decide che cosa si puo' avviare *oggi*
#
# Confonderle e' il modo piu' diretto per rompere un primo avvio. Una GPU AMD su
# Windows non implica che ci sia il runtime HIP: quello arriva con l'HIP SDK,
# che quasi nessuno ha installato. Una Intel Arc non implica oneAPI. Scegliere
# la build ROCm perche' "c'e' una AMD" da' un binario che non apre le proprie
# librerie, cioe' esattamente l'errore al primo avvio che vogliamo togliere.
#
# Vulkan e' il caso interessante: arriva con il driver grafico normale, su ogni
# scheda di questo decennio. Non e' il piu' veloce ovunque, ma e' quello che c'e'
# senza chiedere niente all'utente, e su Intel Arc e sulle Xe integrate e' la
# strada che funziona.
#
# Le sonde non asseriscono. La sonda CPU di questo progetto porta gia' scritto
# perche': "una capacita' riportata per assunzione e' peggio di nessuna
# capacita'". Qui vale identico — c'era un ramo che su Windows dichiarava
# DirectML senza guardare niente.
# ==============================================================================
from __future__ import annotations

import ctypes
import os
import platform
import subprocess
from typing import Dict, List

from core.logger import get_logger

log = get_logger(__name__)

#: Identificatori PCI dei costruttori, come li riporta il kernel Linux.
_PCI_VENDOR = {
    0x10DE: "nvidia",
    0x1002: "amd",
    0x1022: "amd",
    0x8086: "intel",
}


# ==============================================================================
# CHE SCHEDE CI SONO
# ==============================================================================

def gpu_vendors() -> List[str]:
    """I costruttori delle GPU presenti, misurati e non dedotti."""
    sistema = platform.system()
    if sistema == "Windows":
        trovati = _vendor_windows()
    elif sistema == "Linux":
        trovati = _vendor_linux()
    elif sistema == "Darwin":
        trovati = _vendor_darwin()
    else:
        trovati = []

    # Torch sa di schede che l'enumerazione di sistema puo' non distinguere.
    for nome in _vendor_torch():
        if nome not in trovati:
            trovati.append(nome)
    return trovati


def _vendor_windows() -> List[str]:
    """Gli adattatori video come li elenca Windows."""
    script = ("Get-CimInstance Win32_VideoController | "
              "Select-Object -ExpandProperty Name")
    try:
        esito = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as exc:
        log.debug("[GpuVendors] Enumerazione Windows fallita: %s", exc)
        return []

    trovati = []
    for riga in (esito.stdout or "").splitlines():
        nome = riga.strip().lower()
        if not nome:
            continue
        if "nvidia" in nome or "geforce" in nome or "quadro" in nome or "rtx" in nome:
            costruttore = "nvidia"
        elif "amd" in nome or "radeon" in nome or "firepro" in nome:
            costruttore = "amd"
        elif "intel" in nome or "arc(tm)" in nome or "iris" in nome or "uhd graphics" in nome:
            costruttore = "intel"
        else:
            continue
        if costruttore not in trovati:
            trovati.append(costruttore)
    return trovati


def _vendor_linux() -> List[str]:
    """Il vendor PCI di ogni scheda, letto da /sys."""
    trovati = []
    base = "/sys/class/drm"
    if not os.path.isdir(base):
        return trovati
    try:
        for voce in sorted(os.listdir(base)):
            percorso = os.path.join(base, voce, "device", "vendor")
            if not os.path.isfile(percorso):
                continue
            try:
                with open(percorso, "r", encoding="utf-8") as fh:
                    identificatore = int(fh.read().strip(), 16)
            except (OSError, ValueError):
                continue
            costruttore = _PCI_VENDOR.get(identificatore)
            if costruttore and costruttore not in trovati:
                trovati.append(costruttore)
    except OSError as exc:
        log.debug("[GpuVendors] Lettura /sys/class/drm fallita: %s", exc)
    return trovati


def _vendor_darwin() -> List[str]:
    if platform.machine().lower() in ("arm64", "aarch64"):
        return ["apple"]
    return []


def _vendor_torch() -> List[str]:
    trovati = []
    try:
        import torch
    except Exception:
        return trovati

    try:
        if getattr(torch.version, "hip", None):
            trovati.append("amd")
        elif torch.cuda.is_available():
            trovati.append("nvidia")
    except Exception:
        pass
    try:
        # Le GPU Intel arrivano a torch come dispositivi XPU.
        if hasattr(torch, "xpu") and torch.xpu.is_available():
            trovati.append("intel")
    except Exception:
        pass
    try:
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            trovati.append("apple")
    except Exception:
        pass
    return trovati


# ==============================================================================
# QUALI RUNTIME SONO INSTALLATI
# ==============================================================================
# Si prova a caricare la libreria condivisa. E' l'unica verifica che risponde
# alla domanda giusta: non "esiste il file da qualche parte" ma "il caricatore
# dinamico la trova e la apre", che e' esattamente cio' che fara' llama.cpp.

_LIBRERIE = {
    "cuda":   ("nvcuda.dll", "libcuda.so.1", "libcuda.so"),
    "vulkan": ("vulkan-1.dll", "libvulkan.so.1", "libvulkan.so", "libvulkan.dylib"),
    "hip":    ("amdhip64_6.dll", "amdhip64.dll", "libamdhip64.so.6", "libamdhip64.so"),
    "sycl":   ("sycl8.dll", "sycl7.dll", "libsycl.so.8", "libsycl.so"),
    "metal":  (),
}


def _libreria_apribile(nomi) -> bool:
    for nome in nomi:
        try:
            ctypes.CDLL(nome)
            return True
        except OSError:
            continue
    return False


def available_runtimes() -> Dict[str, bool]:
    """Quali runtime di calcolo questa macchina puo' aprire adesso."""
    esiti = {}
    for nome, librerie in _LIBRERIE.items():
        if nome == "metal":
            esiti[nome] = (platform.system() == "Darwin"
                           and platform.machine().lower() in ("arm64", "aarch64"))
            continue
        esiti[nome] = _libreria_apribile(librerie)
    return esiti


# ==============================================================================
# LA SCELTA
# ==============================================================================

def preferred_compute() -> str:
    """L'acceleratore da usare: il piu' veloce fra quelli che partono davvero.

    L'ordine per costruttore mette per primo il percorso nativo e subito dopo
    Vulkan, che arriva con il driver grafico. La regola che conta e' l'altra:
    una voce entra in gioco solo se il suo runtime si apre. Preferire ROCm
    perche' c'e' una scheda AMD, su una macchina senza HIP SDK, produce un
    binario che non apre le proprie librerie — cioe' l'errore al primo avvio.
    """
    runtimes = available_runtimes()
    costruttori = gpu_vendors()

    ordine_per_costruttore = {
        "nvidia": ["cuda", "vulkan"],
        "amd":    ["hip", "vulkan"],
        "intel":  ["sycl", "vulkan"],
        "apple":  ["metal"],
    }

    # I costruttori si scorrono per capacita', non nell'ordine in cui il sistema
    # li elenca. Su questa stessa macchina l'ordine di scoperta e' ['amd',
    # 'nvidia'] — una Radeon integrata nell'APU piu' due schede NVIDIA discrete
    # — e seguirlo faceva scegliere ROCm su una grafica integrata invece che
    # CUDA su due RTX. La combinazione APU AMD piu' scheda NVIDIA e' fra le piu'
    # comuni in circolazione, quindi non e' un caso limite.
    PRIORITA = ("apple", "nvidia", "amd", "intel")

    for costruttore in PRIORITA:
        if costruttore not in costruttori:
            continue
        for candidato in ordine_per_costruttore.get(costruttore, []):
            if runtimes.get(candidato):
                return {"hip": "rocm"}.get(candidato, candidato)

    # Nessuna scheda utilizzabile: Vulkan puo' esserci comunque (driver
    # integrato), altrimenti la CPU, che c'e' sempre.
    if runtimes.get("vulkan"):
        return "vulkan"
    return "cpu"


def describe() -> Dict[str, object]:
    """Il quadro completo, per la diagnostica e per l'API di sistema."""
    runtimes = available_runtimes()
    return {
        "gpu": gpu_vendors(),
        "runtimes": runtimes,
        "scelto": preferred_compute(),
    }
