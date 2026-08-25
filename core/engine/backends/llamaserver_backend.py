# ==============================================================================
# core/engine/backends/llamaserver_backend.py — llama.cpp come processo, non come ruota
#
# Stesso motore dell'altro backend, procurato in un modo che regge ovunque. La
# differenza non e' di prestazioni ma di installabilita': le ruote di
# llama-cpp-python sono compilate con AVX2 e FMA cablati, e su un processore che
# non li ha si fermano con STATUS_ILLEGAL_INSTRUCTION appena provano a usarli.
# I binari ufficiali sono costruiti con GGML_CPU_ALL_VARIANTS e GGML_BACKEND_DL:
# quattordici varianti CPU nello stesso archivio, scelte a runtime. Un download
# copre ogni x86-64 dal 2011 a oggi, senza compilatore.
#
# Il modello sta in un processo separato che espone un'API HTTP compatibile
# OpenAI — la stessa che Sigma Studio gia' parla dall'altro lato, in
# provider_server.py. Tre conseguenze che valgono da sole:
#
#   - un'istruzione illegale, un OOM del driver o un bug del kernel uccidono il
#     processo del modello, non il server. Oggi si portano via tutto.
#   - `-np N --cont-batching` serve piu' conversazioni sullo stesso modello
#     caricato una volta. Il percorso in-process le serializza su un lock, e
#     chi arriva secondo legge "Motore occupato da un'altra richiesta".
#   - `--jinja` prende il template di chat dal GGUF invece di indovinarlo.
#
# Il piano di caricamento non viene ricalcolato: arriva da core/engine/
# gguf_planner.py, lo stesso che usa l'altro backend, e qui viene solo tradotto
# in argomenti da riga di comando.
# ==============================================================================
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Generator, List, Optional, Tuple

from core.engine import gguf_planner
from core.engine.backends.base import InferenceBackend
from core.engine.model_inspector import ModelFacts
from core.engine.sampling import SamplingParams
from core.logger import get_logger

log = get_logger(__name__)

#: Quanto aspettare che il server risponda dopo l'avvio. Su una scheda piccola
#: con un modello sul disco lento il caricamento e' lento davvero.
_AVVIO_TIMEOUT_S = 300
_AVVIO_INTERVALLO_S = 0.4

#: Quanto aspettare la chiusura ordinata prima di forzarla.
_CHIUSURA_TIMEOUT_S = 10


# ==============================================================================
# TRADUZIONE DEL PIANO
# ==============================================================================
# Ogni chiave che il pianificatore produce ha un flag. La corrispondenza sta in
# un posto solo, ed e' verificata da un test contro l'--help del binario: un
# flag inventato o rinominato altrimenti si scopre al primo avvio di qualcuno.

#: piano -> (flag, come renderlo). None significa "non passare l'argomento".
def plan_to_args(settings: Dict[str, Any]) -> List[str]:
    """Gli argomenti di llama-server che realizzano questo piano."""
    argomenti: List[str] = []

    def aggiungi(flag: str, valore: Any) -> None:
        if valore is not None:
            argomenti.extend([flag, str(valore)])

    aggiungi("-ngl", settings.get("n_gpu_layers"))
    aggiungi("-c", settings.get("n_ctx"))
    aggiungi("-b", settings.get("n_batch"))
    aggiungi("-t", settings.get("n_threads"))
    aggiungi("-tb", settings.get("n_threads_batch"))

    split = settings.get("tensor_split")
    if split:
        # Il pianificatore la calcola come frazioni per scheda.
        if isinstance(split, (list, tuple)):
            split = ",".join(str(x) for x in split)
        aggiungi("-ts", split)

    # Flash attention: il binario vuole on/off/auto, non un booleano.
    flash = settings.get("flash_attn")
    if flash is not None:
        aggiungi("-fa", "on" if flash else "off")

    # La cache KV quantizzata vale per chiave e valore insieme: il pianificatore
    # decide se conviene misurando, qui si applica soltanto.
    kv = settings.get("kv_quant")
    if kv and kv != "f16":
        aggiungi("-ctk", kv)
        aggiungi("-ctv", kv)

    if settings.get("use_mmap") is False:
        argomenti.append("--no-mmap")
    if settings.get("use_mlock"):
        argomenti.append("--mlock")

    return argomenti


def _porta_libera() -> int:
    """Una porta che il sistema dichiara libera adesso.

    Chiederla al sistema invece di fissarla evita il conflitto con un altro
    Sigma Studio, con un llama-server avviato a mano, o con qualunque cosa
    occupi la porta che avremmo scelto noi.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ==============================================================================
# IL BACKEND
# ==============================================================================

class LlamaServerBackend(InferenceBackend):
    """Esegue i GGUF con il binario ufficiale di llama.cpp, in un processo suo."""

    name = "llama_server"
    supported_formats = ("gguf",)

    def __init__(self) -> None:
        self._processo: Optional[subprocess.Popen] = None
        self._porta: Optional[int] = None
        self._facts: Optional[ModelFacts] = None
        self._settings: Dict[str, Any] = {}
        self._lock = threading.Lock()
        #: Se lo stream sta consegnando il ragionamento invece della risposta.
        self._in_ragionamento = False

    # --------------------------------------------------------- capabilities

    @classmethod
    def availability(cls) -> Tuple[bool, str]:
        from core.engine.llama_runtime import installed_server

        server = installed_server()
        if server is None:
            return (False, "Runtime GGUF non installato: scaricalo dal Model Hub "
                           "oppure con `python sigma_launcher.py --install`.")
        return (True, f"llama-server: {server}")

    @classmethod
    def score(cls, facts: ModelFacts, hardware: Dict[str, Any]) -> int:
        """Preferito all'esecuzione in-processo quando il binario ha la GPU giusta.

        Non perche' generi piu' in fretta — e' lo stesso motore — ma perche' un
        crash del modello non si porta via il server, e perche' serve piu'
        conversazioni sullo stesso modello caricato una volta. A parita' di
        token al secondo, sono due proprieta' che si pagano volentieri.

        Ma una build CPU-only su una macchina con GPU vince sull'in-process che
        ha CUDA compilato dentro, e il risultato e' che le GPU non vengono
        usate. Il punteggio si abbassa quando la build non ha l'acceleratore
        giusto.
        """
        try:
            from core.engine.llama_runtime import installed_build_info
            info = installed_build_info()
        except Exception:
            info = None

        if info is None:
            return 110

        # La build ha un acceleratore? Se si', vince.
        if info.get("acceleratori"):
            return 110

        # La build e' solo CPU. Se la macchina ha una GPU e l'in-process ha
        # CUDA, lasciamo vincere l'in-process finche' la build non viene
        # aggiornata.
        accelerators = hardware.get("accelerators", [])
        ha_gpu = any(
            a.get("type") in ("NVIDIA_CUDA", "AMD_ROCM", "APPLE_MPS")
            for a in accelerators
        )
        if ha_gpu:
            return 80  # Sotto il punteggio implicito (100) dell'in-process.

        return 110


    # -------------------------------------------------------------- runtime

    @property
    def is_loaded(self) -> bool:
        return self._processo is not None and self._processo.poll() is None

    def load(self, facts: ModelFacts, hardware: Dict[str, Any],
             context_tokens: int = 8192, **options) -> Dict[str, Any]:
        from core.engine.llama_runtime import installed_server

        server = installed_server()
        if server is None:
            return {"success": False, "stage": "availability",
                    "error": self.availability()[1]}

        modello = self._file_gguf(facts)
        if modello is None:
            return {"success": False, "stage": "discovery",
                    "error": f"Nessun file .gguf trovato in {facts.path}"}

        settings = gguf_planner._plan_settings(facts, hardware, context_tokens)
        from core.engine.load_overrides import apply_to
        settings = apply_to(settings, facts.name)

        self.unload()

        porta = _porta_libera()
        comando = [
            str(server),
            "-m", modello,
            "--host", "127.0.0.1",
            "--port", str(porta),
            # Il template di chat viene dal GGUF: indovinarlo e' la fonte
            # principale di risposte formattate male.
            "--jinja",
            # Piu' conversazioni sullo stesso modello caricato una volta.
            "-np", str(int(settings.get("parallel_slots") or 4)),
            "-cb",
            *plan_to_args(settings),
        ]

        log.info("[LlamaServer] Avvio: %s", " ".join(comando[1:]))
        t0 = time.perf_counter()
        from core.engine.llama_runtime import runtime_env
        try:
            self._processo = subprocess.Popen(
                comando,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                cwd=str(server.parent),
                env=runtime_env(),
            )
        except OSError as exc:
            self._processo = None
            return {"success": False, "stage": "load",
                    "error": f"Impossibile avviare llama-server: {exc}"}

        self._porta = porta
        pronto, motivo = self._attendi_pronto()
        if not pronto:
            uscita = self._raccogli_uscita()
            self.unload()
            return {"success": False, "stage": "load", "error": motivo,
                    "stderr": uscita, "settings": settings}

        self._facts = facts
        self._settings = dict(settings, load_seconds=round(time.perf_counter() - t0, 2),
                              port=porta)
        log.info("[LlamaServer] '%s' pronto in %.1fs su :%d",
                 facts.name, time.perf_counter() - t0, porta)
        return {"success": True, "settings": self._settings, "model_name": facts.name}

    def unload(self) -> Dict[str, Any]:
        with self._lock:
            processo, self._processo = self._processo, None
        if processo is None:
            return {"success": True, "already_unloaded": True}

        if processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(timeout=_CHIUSURA_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                log.warning("[LlamaServer] Chiusura ordinata scaduta, forzo.")
                processo.kill()
                processo.wait(timeout=5)

        self._porta = None
        self._facts = None
        self._settings = {}
        return {"success": True}

    # ------------------------------------------------------------ streaming

    def generate_stream(
        self,
        prompt: str,
        system_prompt: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        messages: Optional[list] = None,
        params: Optional[SamplingParams] = None,
        cancel: Any = None,
    ) -> Generator[Dict[str, Any], None, None]:
        if not self.is_loaded:
            yield {"token": "\n\n❌ **Nessun modello caricato nel runtime GGUF**",
                   "token_index": 0, "done": True}
            return

        params = params or SamplingParams(temperature=temperature, max_tokens=max_tokens)
        corpo = self._corpo_richiesta(prompt, system_prompt, messages, params)
        self._in_ragionamento = False

        t_start = time.perf_counter()
        primo_token_a = None
        contatore = 0

        try:
            for pezzo in self._stream_http("/v1/chat/completions", corpo):
                if cancel is not None and getattr(cancel, "is_cancelled", lambda: False)():
                    log.info("[LlamaServer] Generazione annullata dal chiamante.")
                    break

                testo = pezzo.get("content") or ""
                if not testo:
                    continue

                contatore += 1
                adesso = time.perf_counter()
                if primo_token_a is None:
                    primo_token_a = adesso
                    yield {"token": testo, "token_index": contatore,
                           "ttft_ms": round((adesso - t_start) * 1000, 1), "done": False}
                else:
                    yield {"token": testo, "token_index": contatore,
                           "speed_tok_s": round(
                               (contatore - 1) / max(adesso - primo_token_a, 1e-3), 1),
                           "done": False}

            if self._in_ragionamento:
                # Un troncamento a meta' ragionamento lascerebbe un <think>
                # aperto, e chi lo interpreta a valle nasconderebbe tutto il
                # resto della conversazione.
                self._in_ragionamento = False
                contatore += 1
                yield {"token": "</think>", "token_index": contatore, "done": False}

            adesso = time.perf_counter()
            yield {
                "token": "", "token_index": contatore + 1, "done": True,
                "speed_tok_s": round(
                    max(contatore - 1, 0) / max(adesso - (primo_token_a or adesso), 1e-3), 1),
                "total_tokens": contatore,
            }
        except Exception as exc:
            log.error("[LlamaServer] Generazione fallita: %s", exc, exc_info=True)
            yield {"token": f"\n\n❌ **Errore llama-server**: {type(exc).__name__}: {exc}",
                   "token_index": contatore + 1, "done": True}

    # --------------------------------------------------------- osservazione

    def describe_placement(self) -> Dict[str, Any]:
        offloaded = self._settings.get("n_gpu_layers", 0)
        totale = getattr(self._facts, "num_hidden_layers", 0) or 0
        return {
            "mode": "llama_server",
            "layers_total": totale,
            "layers_on_gpu": offloaded,
            "layers_on_cpu": max(totale - offloaded, 0) if offloaded >= 0 else 0,
            "tensor_split": self._settings.get("tensor_split"),
            "fully_offloaded": offloaded < 0 or (totale and offloaded >= totale),
            "kv_cache_type": self._settings.get("kv_quant") or "f16",
            "prefill_batch": self._settings.get("n_batch"),
            "port": self._settings.get("port"),
        }

    def telemetry(self) -> Dict[str, Any]:
        return dict(self._settings)

    def benchmark(self, prompt_tokens: int = 128, decode_tokens: int = 24) -> Dict[str, Any]:
        """Prefill e decode separati, misurati dal server stesso.

        llama-server riporta i propri tempi in `timings`, distinti fra lettura
        del prompt e generazione: sono le stesse due fasi che il percorso
        in-process cronometra a mano, misurate da chi le esegue invece che
        dall'esterno.
        """
        if not self.is_loaded:
            return {"success": False, "error": "Nessun modello caricato.",
                    "backend": self.name}

        seme = "Il rapporto tecnico descrive " * 40
        corpo = {
            "prompt": seme[:prompt_tokens * 4],
            "n_predict": decode_tokens,
            "stream": False,
            "cache_prompt": False,
        }
        try:
            risposta = self._post("/completion", corpo, timeout=180)
        except Exception as exc:
            return {"success": False, "error": str(exc), "backend": self.name}

        timings = risposta.get("timings") or {}
        return {
            "success": True,
            "backend": self.name,
            "prefill_tok_s": round(timings.get("prompt_per_second") or 0.0, 2),
            "decode_tok_s": round(timings.get("predicted_per_second") or 0.0, 2),
            "prefill_ms": round(timings.get("prompt_ms") or 0.0, 1),
            "decode_ms": round(timings.get("predicted_ms") or 0.0, 1),
            "prompt_tokens": timings.get("prompt_n"),
            "decode_tokens": timings.get("predicted_n"),
        }

    # ------------------------------------------------------------- interni

    def _file_gguf(self, facts: ModelFacts) -> Optional[str]:
        """Il .gguf da caricare, con la stessa logica dell'altro backend."""
        from core.engine.backends.llamacpp_backend import LlamaCppBackend

        return LlamaCppBackend()._resolve_gguf_file(facts)

    def _url(self, percorso: str) -> str:
        return f"http://127.0.0.1:{self._porta}{percorso}"

    def _attendi_pronto(self) -> Tuple[bool, str]:
        """Aspetta che il server risponda, o che il processo muoia dicendo perche'."""
        scadenza = time.time() + _AVVIO_TIMEOUT_S
        while time.time() < scadenza:
            if self._processo is None or self._processo.poll() is not None:
                uscita = self._raccogli_uscita()
                from core.engine.runtime_probe import (
                    illegal_instruction_report, is_illegal_instruction)
                codice = self._processo.poll() if self._processo else None
                if is_illegal_instruction(returncode=codice, testo=uscita):
                    return (False, illegal_instruction_report())
                return (False, f"llama-server e' terminato (codice {codice}).\n{uscita[-800:]}")

            try:
                with urllib.request.urlopen(self._url("/health"), timeout=2) as risposta:
                    if risposta.status == 200:
                        return (True, "")
            except Exception:
                pass
            time.sleep(_AVVIO_INTERVALLO_S)

        return (False, f"llama-server non ha risposto entro {_AVVIO_TIMEOUT_S}s.")

    def _raccogli_uscita(self) -> str:
        if self._processo is None or self._processo.stdout is None:
            return ""
        try:
            if self._processo.poll() is not None:
                return self._processo.stdout.read() or ""
        except Exception:
            pass
        return ""

    def _corpo_richiesta(self, prompt: str, system_prompt: str,
                         messages: Optional[list], params: SamplingParams) -> Dict[str, Any]:
        if messages:
            conversazione = list(messages)
        else:
            conversazione = []
            if system_prompt:
                conversazione.append({"role": "system", "content": system_prompt})
            conversazione.append({"role": "user", "content": prompt})

        corpo: Dict[str, Any] = {
            "messages": conversazione,
            "stream": True,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "top_k": params.top_k,
            "max_tokens": params.max_tokens,
        }
        if params.min_p:
            corpo["min_p"] = params.min_p
        if params.repeat_penalty:
            corpo["repeat_penalty"] = params.repeat_penalty
        if params.seed is not None:
            corpo["seed"] = params.seed
        if params.stop:
            corpo["stop"] = list(params.stop)

        # La grammatica viaggia come testo GBNF apposta: SamplingParams la
        # porta senza compilarla, e llama-server la vuole esattamente cosi'.
        grammatica = getattr(params, "grammar", None)
        if grammatica:
            corpo["grammar"] = grammatica
        return corpo

    def _post(self, percorso: str, corpo: Dict[str, Any], timeout: int = 60) -> Dict[str, Any]:
        richiesta = urllib.request.Request(
            self._url(percorso),
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:
            return json.loads(risposta.read().decode("utf-8"))

    def _stream_http(self, percorso: str, corpo: Dict[str, Any]
                     ) -> Generator[Dict[str, Any], None, None]:
        """Legge lo stream SSE del server e restituisce i pezzi di contenuto."""
        richiesta = urllib.request.Request(
            self._url(percorso),
            data=json.dumps(corpo).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "text/event-stream"},
        )
        with urllib.request.urlopen(richiesta, timeout=_AVVIO_TIMEOUT_S) as risposta:
            for riga_grezza in risposta:
                riga = riga_grezza.decode("utf-8", errors="replace").strip()
                if not riga.startswith("data:"):
                    continue
                carico = riga[5:].strip()
                if carico == "[DONE]":
                    return
                try:
                    evento = json.loads(carico)
                except ValueError:
                    continue
                scelte = evento.get("choices") or []
                if not scelte:
                    continue
                delta = scelte[0].get("delta") or {}

                # I modelli di ragionamento mandano il pensiero su un canale
                # separato: llama-server con --jinja mette il ragionamento in
                # `reasoning_content` e la risposta in `content`. Leggendo solo
                # il secondo, un Qwen3 sembra non produrre nulla per tutta la
                # fase di ragionamento — che su una domanda breve puo' essere
                # tutta la generazione.
                #
                # Si ricostruiscono i tag <think>, che e' la forma in cui il
                # percorso in-process consegna la stessa cosa e che il resto
                # dell'applicazione — il parser delle risposte, il canale
                # "thought" della chat, l'agente del Developer Studio — sa gia'
                # riconoscere. Due backend che consegnano la stessa cosa in due
                # forme diverse sarebbero una divergenza in piu' da inseguire.
                ragionamento = delta.get("reasoning_content")
                if ragionamento:
                    if not self._in_ragionamento:
                        self._in_ragionamento = True
                        yield {"content": "<think>"}
                    yield {"content": ragionamento}
                    continue

                contenuto = delta.get("content")
                if contenuto:
                    if self._in_ragionamento:
                        self._in_ragionamento = False
                        yield {"content": "</think>"}
                    yield {"content": contenuto}
