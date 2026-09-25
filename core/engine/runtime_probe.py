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
from typing import Any, Dict, Optional, Sequence

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


# ==============================================================================
# LA GPU CHE SMETTE DI RISPONDERE
# ==============================================================================
#
# Segnalazione reale, 25 settembre 2026, caricando sigmanih--Qwen3.8-27B:
#
#     llama-server e' terminato (codice 3221226505).
#     ... E CUDA error: unspecified launch failure
#     ... in function ggml_backend_cuda_buffer_set_tensor
#     ... cudaMemcpyAsync((char *) tensor->data + offset, data, size,
#                          cudaMemcpyHostToDevice, stream)
#
# Il messaggio che l'utente ha ricevuto in coda consigliava di ridurre il
# contesto o di forzare una quantizzazione piu' aggressiva. E' lo stesso
# consiglio sbagliato che questo file e' nato per togliere di mezzo nel caso
# dell'istruzione illegale, e sbaglia allo stesso modo: il guasto e' una copia
# di memoria host->device, quindi avviene **prima** che esistano un contesto e
# una cache KV. Ridurre il contesto non tocca una cudaMemcpyAsync.
#
# Cio' che si puo' fare davvero e' togliere carico alla scheda: e' quello che fa
# `LlamaServerBackend.load` con la scala di ripieghi, e il motivo per cui la
# lista dei tentativi finisce in questo messaggio.

#: Il codice con cui Windows chiude il processo quando la scheda video cede
#: sotto di lui: STATUS_STACK_BUFFER_OVERRUN, che nell'uso reale arriva dai
#: processi CUDA che crashano — non da uno stack davvero corrotto. A 32 bit con
#: segno e' -1073740791.
_WIN_CUDA_CRASH = 3221226505

#: Le firme che llama.cpp lascia nell'uscita quando e' la GPU a cedere.
_FIRME_CUDA = ("cuda error", "cudaerror", "ggml_backend_cuda", "cudamemcpy",
               "cublas", "cuda driver")


def is_cuda_failure(returncode: Optional[int] = None, testo: str = "") -> bool:
    """Se il processo e' morto perche' la scheda video ha smesso di rispondere.

    Decide il **testo**: le firme che llama.cpp scrive quando e' la GPU a
    cedere. Il codice d'uscita da solo non basta — 0xC0000409 e' anche l'esito
    di uno stack davvero corrotto, e consigliare di abbassare l'offload a chi ha
    un altro guasto e' il modo di far perdere una serata. Vale pero' quando il
    testo non c'e': un processo morto **senza dire niente**, con quel codice, e'
    una scheda che si e' portata via il driver prima di poterlo raccontare.
    """
    uscita = str(testo or "").lower()
    if any(firma in uscita for firma in _FIRME_CUDA):
        return True
    return (not uscita.strip()
            and returncode in (_WIN_CUDA_CRASH, _WIN_CUDA_CRASH - 2 ** 32))


def cuda_failure_report(dettaglio: str = "",
                        riduzioni: Sequence[str] = ()) -> str:
    """Cosa dire a chi ha visto la GPU cedere durante il caricamento.

    **Non e' il contesto.** Il guasto avviene mentre i pesi vengono copiati
    nella scheda — `ggml_backend_cuda_buffer_set_tensor`, una `cudaMemcpyAsync`
    — cioe' prima che una cache KV esista. Il consiglio «riduci il contesto»
    manda dalla parte sbagliata esattamente come faceva davanti all'istruzione
    illegale, e per la stessa ragione: nessuna quantita' di contesto cambia
    cio' che e' successo alla scheda.

    La lista `riduzioni` sono i tentativi automatici gia' fatti: chi legge deve
    sapere cosa e' stato provato al posto suo, o li rifara' a mano.
    """
    provate = "\n".join(f"- {voce}" for voce in riduzioni) or (
        "- nessuna riduzione registrata da questo percorso")
    estratto = str(dettaglio or "").strip()
    if len(estratto) > 600:
        estratto = "(...)\n" + estratto[-600:]

    return (
        "**La scheda video ha smesso di rispondere mentre i pesi venivano "
        "copiati in VRAM.**\n\n"
        "Il guasto arriva da `ggml_backend_cuda_buffer_set_tensor`, cioe' dal "
        "trasferimento dei pesi: e' **prima** che il contesto e la cache KV "
        "esistano, quindi ridurre il contesto o cambiare quantizzazione non "
        "cambia niente.\n\n"
        "**Le tre cause possibili, in ordine di frequenza**\n"
        "1. La VRAM non basta per il piano di offload: la scheda dichiara piu' "
        "memoria libera di quella che ha davvero, perche' un altro programma la "
        "occupa o il driver la frammenta.\n"
        "2. Il driver o la scheda sono instabili sotto carico: reset del driver "
        "(TDR), overclock, alimentazione insufficiente.\n"
        "3. La build CUDA installata non combacia con il driver.\n\n"
        "**Cosa e' stato gia' provato**\n"
        f"{provate}\n\n"
        "**Cosa fare adesso**\n"
        "- Nel pannello del motore abbassa **Layer sulla GPU**, o mettilo a 0: "
        "il modello si carica comunque, piu' lentamente.\n"
        "- Chiudi gli altri programmi che usano la scheda e riprova: la VRAM "
        "che il piano contava era occupata.\n"
        "- Se il guasto si ripete a ogni tentativo, aggiorna o reinstalla il "
        "driver: un TDR lascia la scheda in uno stato da cui non si esce senza "
        "un reset.\n\n"
        "**Uscita di llama.cpp**\n"
        "```\n" + estratto + "\n```"
    )
