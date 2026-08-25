# ==============================================================================
# core/engine/runtime_probe.py — Il runtime GGUF gira davvero su questa CPU?
#
# Segnalazione reale, al primo avvio dopo un download:
#
#     SigmaEngine non ha potuto caricare sigmanih--sigma-alpaca-3b-gguf
#     Fase: load
#     Causa: OSError: [WinError -1073741795] Windows Error 0xc000001d
#
# 0xC000001D e' STATUS_ILLEGAL_INSTRUCTION. Non e' memoria, non e' il modello,
# non e' il contesto: e' la CPU che incontra un'istruzione che non conosce. Le
# ruote precompilate di llama-cpp-python sono costruite con AVX2 e FMA, e su un
# processore che non li ha il primo kernel vettoriale eseguito fa saltare tutto.
# Il messaggio che l'utente ha ricevuto consigliava di ridurre il contesto:
# nessuna quantita' di contesto in meno cambia le istruzioni che la CPU ha.
#
# Due ragioni per fare la verifica in un sottoprocesso invece che in linea:
#
#   - su Windows l'istruzione illegale arriva a ctypes come OSError e si puo'
#     intercettare, ma su Linux e macOS e' SIGILL e uccide il processo. In
#     linea, il primo utente con una CPU vecchia non vedrebbe un errore: gli
#     morirebbe il server.
#   - l'esito dipende solo dalla coppia (ruota installata, CPU), quindi si
#     misura una volta e si tiene in cache: il costo di un sottoprocesso si
#     paga al primo caricamento e mai piu'.
# ==============================================================================
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import threading
from typing import Any, Dict, Optional

from core import paths
from core.logger import get_logger

log = get_logger(__name__)

#: NTSTATUS STATUS_ILLEGAL_INSTRUCTION, come lo riporta Windows e come lo
#: rigira Python (lo stesso valore letto a 32 bit con segno).
_WIN_ILLEGAL_INSTRUCTION = 0xC000001D
_WIN_ILLEGAL_INSTRUCTION_SIGNED = -1073741795

#: Sui sistemi POSIX un processo ucciso da SIGILL torna con -4.
_POSIX_SIGILL = -4

_TIMEOUT_SECONDI = 60

_LOCK = threading.Lock()
_cache_processo: Optional[Dict[str, Any]] = None


def _file_cache() -> "os.PathLike[str]":
    return paths.var_dir() / "gguf_runtime_probe.json"


def _impronta() -> str:
    """Cosa deve cambiare perche' l'esito possa cambiare.

    La versione della ruota, l'interprete, la macchina e il binario installato.
    Non il modello: una CPU che non ha AVX2 non ce l'ha per nessun modello.
    Includere il binario fa si' che un upgrade da build CPU a build CUDA
    invalidi la cache e la verifica venga ripetuta.
    """
    try:
        import llama_cpp
        versione = getattr(llama_cpp, "__version__", "?")
    except Exception:
        versione = "assente"

    try:
        from core.engine.llama_runtime import installed_server
        server = str(installed_server() or "nessuno")
    except Exception:
        server = "errore"

    return "|".join((
        versione,
        f"{sys.version_info.major}.{sys.version_info.minor}",
        platform.machine().lower(),
        platform.system(),
        server,
    ))



# ==============================================================================
# ISTRUZIONE ILLEGALE
# ==============================================================================

def is_illegal_instruction(exc: BaseException = None, returncode: int = None,
                           testo: str = "") -> bool:
    """Riconosce l'istruzione illegale da un'eccezione, un exit code o un testo."""
    if exc is not None:
        codice = getattr(exc, "winerror", None)
        if codice in (_WIN_ILLEGAL_INSTRUCTION, _WIN_ILLEGAL_INSTRUCTION_SIGNED):
            return True
        testo = f"{testo} {exc}"

    if returncode is not None:
        if returncode in (_POSIX_SIGILL, _WIN_ILLEGAL_INSTRUCTION,
                          _WIN_ILLEGAL_INSTRUCTION_SIGNED):
            return True
        # Windows riporta il NTSTATUS come exit code senza segno.
        if returncode & 0xFFFFFFFF == _WIN_ILLEGAL_INSTRUCTION:
            return True

    basso = (testo or "").lower()
    return ("0xc000001d" in basso
            or "1073741795" in basso
            or "illegal instruction" in basso
            or "istruzione non consentita" in basso)


# ==============================================================================
# CARATTERISTICHE DELLA CPU
# ==============================================================================

def cpu_features() -> Dict[str, Any]:
    """Che cosa questa CPU sa fare, in vocabolario llama.cpp."""
    try:
        from core.engine.hardware_probe import UniversalHardwareProbe
        cpu = UniversalHardwareProbe.probe_cpu()
        simd = cpu.get("simd_features") or []
        modello = cpu.get("model") or platform.processor()
    except Exception as exc:
        log.debug("[RuntimeProbe] Sonda CPU non disponibile: %s", exc)
        simd, modello = [], platform.processor()

    return {
        "modello": modello or platform.machine(),
        "arch": platform.machine().lower(),
        "simd": simd,
        "ha_avx2": "AVX2" in simd,
        "ha_avx": "AVX" in simd,
        "ha_fma": "FMA" in simd,
    }


# ==============================================================================
# VERIFICA
# ==============================================================================

#: Inizializza il backend e lo spegne. Basta a far eseguire i kernel di
#: dispatch: se la ruota e' costruita per istruzioni che mancano, salta qui.
_SCRIPT = (
    "import llama_cpp, sys;"
    "llama_cpp.llama_backend_init();"
    "llama_cpp.llama_backend_free();"
    "sys.stdout.write('ok')"
)


def _verifica_binario() -> Optional[Dict[str, Any]]:
    """Verifica che il llama-server ufficiale parta su questa macchina.

    Il binario e' il runtime principale: i binari ufficiali hanno 14 varianti
    CPU e scelgono a runtime, quindi non soffrono di STATUS_ILLEGAL_INSTRUCTION.
    La verifica usa --version, che esce subito senza caricare un modello.
    Restituisce None se il binario non e' installato.
    """
    try:
        from core.engine.llama_runtime import installed_server
        server = installed_server()
    except Exception:
        return None

    if server is None:
        return None

    try:
        from core.engine.llama_runtime import runtime_env
        esito = subprocess.run(
            [str(server), "--version"],
            capture_output=True, text=True, timeout=30,
            env=runtime_env(),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "motivo": "timeout",
                "dettaglio": f"llama-server --version non ha risposto entro 30s.",
                "runtime": "binario"}
    except OSError as exc:
        if is_illegal_instruction(exc=exc):
            return {"ok": False, "motivo": "istruzione_illegale",
                    "dettaglio": str(exc), "runtime": "binario"}
        return {"ok": False, "motivo": "non_avviabile",
                "dettaglio": str(exc), "runtime": "binario"}

    if esito.returncode == 0:
        return {"ok": True, "motivo": "", "dettaglio": "",
                "runtime": "binario", "versione": (esito.stdout or "").strip()[:200]}

    uscita = (esito.stdout or "") + (esito.stderr or "")
    if is_illegal_instruction(returncode=esito.returncode, testo=uscita):
        return {"ok": False, "motivo": "istruzione_illegale",
                "dettaglio": uscita.strip()[:400], "runtime": "binario"}

    return {"ok": False, "motivo": "errore",
            "dettaglio": uscita.strip()[:400], "runtime": "binario",
            "returncode": esito.returncode}


def _esegui_verifica() -> Dict[str, Any]:
    # Il binario ufficiale e' il runtime principale: se c'e' e funziona,
    # la verifica e' fatta. Se non c'e', si prova la ruota Python.
    binario = _verifica_binario()
    if binario is not None:
        return binario

    # Ripiego sulla ruota llama-cpp-python.
    try:
        esito = subprocess.run(
            [sys.executable, "-c", _SCRIPT],
            capture_output=True, text=True, timeout=_TIMEOUT_SECONDI,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "motivo": "timeout",
                "dettaglio": f"Il runtime GGUF non ha risposto entro {_TIMEOUT_SECONDI}s.",
                "runtime": "ruota"}
    except Exception as exc:
        return {"ok": False, "motivo": "non_avviabile", "dettaglio": str(exc),
                "runtime": "ruota"}

    uscita = (esito.stdout or "") + (esito.stderr or "")

    if esito.returncode == 0 and "ok" in (esito.stdout or ""):
        return {"ok": True, "motivo": "", "dettaglio": "", "runtime": "ruota"}

    if is_illegal_instruction(returncode=esito.returncode, testo=uscita):
        return {"ok": False, "motivo": "istruzione_illegale",
                "dettaglio": uscita.strip()[:400], "returncode": esito.returncode,
                "runtime": "ruota"}

    if "no module named" in uscita.lower():
        return {"ok": False, "motivo": "assente", "dettaglio": uscita.strip()[:400],
                "runtime": "ruota"}

    return {"ok": False, "motivo": "errore",
            "dettaglio": uscita.strip()[:400], "returncode": esito.returncode,
            "runtime": "ruota"}



def check_runtime(refresh: bool = False) -> Dict[str, Any]:
    """Esito della verifica, misurato una volta per coppia (ruota, macchina)."""
    global _cache_processo
    impronta = _impronta()

    with _LOCK:
        if not refresh and _cache_processo and _cache_processo.get("impronta") == impronta:
            return _cache_processo

        percorso = _file_cache()
        if not refresh and percorso.exists():
            try:
                salvato = json.loads(percorso.read_text(encoding="utf-8"))
                if salvato.get("impronta") == impronta:
                    _cache_processo = salvato
                    return salvato
            except (OSError, ValueError):
                pass

        esito = _esegui_verifica()
        esito["impronta"] = impronta
        esito["cpu"] = cpu_features()

        if not esito["ok"]:
            log.warning("[RuntimeProbe] Runtime GGUF non utilizzabile (%s): %s",
                        esito["motivo"], esito.get("dettaglio", "")[:200])

        try:
            paths.ensure(percorso.parent)
            percorso.write_text(json.dumps(esito, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
        except OSError as exc:
            log.debug("[RuntimeProbe] Cache non scrivibile: %s", exc)

        _cache_processo = esito
        return esito


# ==============================================================================
# COSA DIRE ALL'UTENTE
# ==============================================================================

def illegal_instruction_report(cpu: Dict[str, Any] = None) -> str:
    """Il messaggio per chi ha una CPU che la ruota installata non rispetta."""
    cpu = cpu or cpu_features()
    simd = ", ".join(cpu.get("simd") or []) or "nessuna estensione rilevata"

    if cpu.get("arch") in ("arm64", "aarch64"):
        rimedio = (
            "Su questa architettura llama-cpp-python va compilato sul posto:\n"
            "```\n"
            "pip install --force-reinstall --no-binary llama-cpp-python llama-cpp-python\n"
            "```"
        )
    else:
        rimedio = (
            "Serve una build senza quelle istruzioni. Reinstalla il runtime "
            "compilandolo per questa CPU:\n"
            "```\n"
            'set CMAKE_ARGS=-DGGML_AVX2=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF\n'
            "pip install --force-reinstall --no-binary llama-cpp-python llama-cpp-python\n"
            "```\n"
            "(su Linux e macOS: `CMAKE_ARGS=\"-DGGML_AVX2=OFF -DGGML_FMA=OFF "
            '-DGGML_F16C=OFF" pip install ...`)'
        )

    return (
        "Il runtime GGUF installato e' stato compilato per istruzioni che questo "
        "processore non ha, e si ferma appena prova a usarle.\n\n"
        f"**Processore**: {cpu.get('modello', '?')}\n"
        f"**Estensioni disponibili**: {simd}\n\n"
        "Non e' un problema di memoria ne' del modello: ridurre il contesto o "
        "cambiare quantizzazione non cambia le istruzioni che la CPU ha.\n\n"
        f"{rimedio}\n\n"
        "In alternativa, usa un provider Cloud da **Impostazioni AI**, oppure "
        "Ollama, che porta il proprio runtime."
    )
