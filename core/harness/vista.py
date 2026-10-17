# ==============================================================================
# core/harness/vista.py — Gli occhi dell'agente: guardare un'immagine dal disco
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Far guardare un'immagine a un modello di visione e riportarne il testo.

Il modello che guida il Developer Studio legge solo testo: `read_file` su un
JPG restituisce dimensione ed estensione, e niente di quello che c'e' disegnato.
Il primo progetto che ne aveva bisogno — trasporre un manga vignetta per
vignetta — e' finito con l'agente che, non potendo vedere le pagine, ha scritto
a mano titoli di scena e personaggi dentro uno script, e il controllo di
completamento li ha promossi perche' contava i dialoghi, non la loro verita'.

Qui la vista e' un secondo modello, Qwen3-VL, servito da un llama-server suo.
Non lo si carica nel processo del modello di chat per due ragioni: il modello
di chat e' quasi sempre solo testo, e un server separato si spegne da solo
quando nessuno guarda, restituendo la memoria. Se il giudice delle clip ha gia'
un Qwen3-VL acceso lo si usa quello: due copie dello stesso 8B non entrano in
una scheda da 8 GB.

La risposta e' testo e torna all'agente come qualunque osservazione. Il prompt
chiede di distinguere cio' che si vede da cio' che si suppone: una
descrizione inventata qui diventerebbe un fatto per tutto il resto del run.
"""
from __future__ import annotations

import base64
import io
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from core import paths
from core.logger import get_logger

log = get_logger("harness_vista")

#: Porta propria, accanto a quella del giudice delle clip (8096).
PORTA = 8097
#: Il giudice delle clip, se acceso, serve lo stesso modello.
PORTA_GIUDICE = 8096
IS_WINDOWS = sys.platform.startswith("win")
#: Dopo dieci minuti senza domande il server si spegne: l'8B occupa ~6,5 GB.
INATTIVITA_S = 600
#: Il lato lungo massimo dell'immagine inviata. Una pagina di manga a 1600 px
#: si legge ancora nei balloon piccoli; oltre, i token visivi crescono senza
#: che la trascrizione migliori, e su CPU ogni token costa.
LATO_MASSIMO = 1600
#: Sotto questo lato lungo l'immagine si ingrandisce: le scan da 600 px hanno
#: balloon di 40 px che il proiettore visivo riduce a poche patch illeggibili.
LATO_MINIMO = 1000
#: Massimo di testo prodotto per sguardo: una pagina densa ne richiede ~1500.
MAX_TOKENS = 2048
#: Quante volte la stessa riga puo' tornare prima di considerarla un loop.
RIPETIZIONI_MAX = 3
#: Solo le righe lunghe contano: in un JSON `"chi": "fuori campo",` si ripete
#: legittimamente, e contarla troncava a meta' il 15% delle letture di un manga.
RIGA_MINIMA = 40

ESTENSIONI = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}

#: In ordine di preferenza. L'8B prima del 30B-A3B: e' quello che entra in una
#: GPU secondaria e l'unico che sta nei 8 GB di un Raspberry Pi.
MODELLI: Tuple[Tuple[str, str, str], ...] = (
    ("Qwen--Qwen3-VL-8B-Instruct-GGUF", "Qwen3VL-8B-Instruct-Q4_K_M.gguf",
     "mmproj-Qwen3VL-8B-Instruct-F16.gguf"),
    ("Qwen--Qwen3-VL-30B-A3B-Instruct-GGUF", "Qwen3VL-30B-A3B-Instruct-Q4_K_M.gguf",
     "mmproj-Qwen3VL-30B-A3B-Instruct-F16.gguf"),
)

# Il prompt e' in italiano perche' la risposta torna a un agente che lavora in
# italiano, e tradurre una trascrizione la altererebbe. La regola sul non
# inventare e' esplicita perche' senza il modello «completa» i balloon tagliati.
PROMPT_BASE = """Stai guardando un'immagine per conto di un agente che non puo' vederla.
Regole:
- Descrivi SOLO cio' che e' visibile. Non inventare nomi, trama o contesto.
- Trascrivi parola per parola ogni testo leggibile, senza correggerlo ne' tradurlo.
- Se un testo e' illeggibile o tagliato scrivi [illeggibile] o [tagliato], non indovinare.
- Se qualcosa e' incerto dillo con "forse".
Rispondi in italiano."""

PROMPT_DESCRIZIONE = """Descrivi l'immagine in modo strutturato:
1. Tipo di immagine e composizione (se e' una pagina di fumetto: quante vignette e in che disposizione).
2. Per ogni zona o vignetta, nell'ordine di lettura: personaggi (aspetto, espressione, posa), azione, ambiente, inquadratura.
3. Tutto il testo presente, nell'ordine di lettura, indicando dove si trova e, se si capisce dal balloon, chi parla."""


class VistaError(RuntimeError):
    """L'immagine non si e' potuta guardare."""


def _esito(ok: bool, **extra: Any) -> Dict[str, Any]:
    return {"tool": "view_image", "success": ok, **extra}


def file_modello() -> Optional[Tuple[Path, Path]]:
    """Il primo Qwen3-VL installato, coi pesi e il proiettore visivo."""
    for cartella, modello, mmproj in MODELLI:
        base = paths.models_dir() / cartella
        if (base / modello).is_file() and (base / mmproj).is_file():
            return base / modello, base / mmproj
    return None


def _inventario_gpu() -> List[Dict[str, Any]]:
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.total,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    gpus = []
    for riga in out.strip().splitlines():
        parti = [p.strip() for p in riga.split(",")]
        if len(parti) == 3 and parti[0].isdigit():
            try:
                gpus.append({"index": int(parti[0]), "vram_gb": float(parti[1]) / 1024,
                             "free_gb": float(parti[2]) / 1024})
            except ValueError:
                continue
    return gpus


def dispositivo() -> str:
    """Dove gira la vista: `SIGMA_VISTA_DEVICE` vince, poi la GPU piu' piccola se sono due.

    La GPU 0 e' quella del modello di chat: metterci accanto l'8B lo farebbe
    scaricare (o fallire per memoria). Con una sola scheda si va su CPU, piu'
    lenta ma senza toccare il modello che sta ragionando.
    """
    scelto = os.environ.get("SIGMA_VISTA_DEVICE", "auto").strip().lower()
    if scelto and scelto != "auto":
        return scelto
    gpus = _inventario_gpu()
    if len(gpus) >= 2:
        piccola = min(gpus, key=lambda g: (g["vram_gb"], -g["index"]))
        # Conta la memoria LIBERA: il modello di chat da 27B si divide fra le
        # due schede e occupa anche la piccola, dove l'8B non entrerebbe piu'.
        if piccola["free_gb"] >= 7.0:
            return f"gpu:{piccola['index']}"
    libere = [g for g in gpus if g["free_gb"] >= 7.0]
    if libere:
        return f"gpu:{max(libere, key=lambda g: g['free_gb'])['index']}"
    return "cpu"


class Occhio:
    """Il llama-server di visione: acceso alla prima domanda, spento quando inattivo."""

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None
        self._url = ""
        self._lock = threading.Lock()
        self._ultimo_uso = 0.0
        self._sorvegliante: Optional[threading.Thread] = None
        self._lease: Optional[str] = None

    def _libera_gpu(self) -> Optional[str]:
        """Prende la GPU piccola per la vista quando l'LLM della chat le occupa tutte.

        Collaudo Mx0: col 27B diviso fra le due schede ogni `view_image` girava
        sulla CPU, due o tre minuti a sguardo, mentre su GPU ne bastano dieci
        secondi. Fra un turno e l'altro dell'agente l'LLM non sta generando: lo
        si scarica, si riserva la scheda con un lease e, alla prossima domanda,
        l'LLM si ricarica sulle altre. Il lease si libera quando la vista si spegne.
        """
        gpus = _inventario_gpu()
        if len(gpus) < 2:
            return None
        piccola = min(gpus, key=lambda g: (g["vram_gb"], -g["index"]))
        if piccola["vram_gb"] < 7.0:
            return None
        try:
            from core.engine.gpu_lease import leases
            self._lease = leases.acquire("vista", [piccola["index"]], "modello di visione (view_image)")
        except Exception as exc:
            log.info("[Vista] GPU %s non riservata: %s", piccola["index"], exc)
            return None
        try:
            from core.engine.unified_runtime import sigma_engine
            if getattr(sigma_engine, "loaded_model_name", None):
                lock = getattr(sigma_engine, "_generation_lock", None)
                if lock is None or lock.acquire(timeout=120):
                    try:
                        sigma_engine.unload()
                    finally:
                        if lock is not None:
                            lock.release()
        except Exception as exc:
            log.warning("[Vista] LLM della chat non scaricato: %s", exc)
        scadenza = time.monotonic() + 30
        while time.monotonic() < scadenza:
            libera = next((g for g in _inventario_gpu() if g["index"] == piccola["index"]), None)
            if libera and libera["free_gb"] >= 7.0:
                return f"gpu:{piccola['index']}"
            time.sleep(1)
        self._rilascia_gpu()
        return None

    def _rilascia_gpu(self) -> None:
        lease, self._lease = self._lease, None
        if lease:
            try:
                from core.engine.gpu_lease import leases
                leases.release(lease)
            except Exception as exc:
                log.debug("[Vista] lease non rilasciato: %s", exc)

    @staticmethod
    def _vivo(url: str) -> bool:
        try:
            return requests.get(f"{url}/health", timeout=2).status_code == 200
        except requests.RequestException:
            return False

    @staticmethod
    def _serve_qwen3vl(url: str) -> bool:
        """Se su quella porta c'e' davvero un Qwen3-VL, e non un altro servizio."""
        try:
            dati = requests.get(f"{url}/v1/models", timeout=2).json()
        except (requests.RequestException, ValueError):
            return False
        nomi = " ".join(str(m.get("id", "")) for m in (dati.get("data") or [])).lower()
        return "qwen3vl" in nomi or "qwen3-vl" in nomi

    def _avvia(self) -> None:
        from core.engine.backends.llamaserver_backend import _assign_kill_on_close
        from core.engine.llama_runtime import installed_server

        server = installed_server()
        if server is None:
            raise VistaError("llama-server non installato (Model Hub -> runtime GGUF)")
        files = file_modello()
        if files is None:
            raise VistaError(
                "nessun modello di visione installato: serve Qwen3-VL-8B-Instruct GGUF "
                "col suo mmproj (Video Studio -> Motori -> Qwen3-VL)")
        modello, mmproj = files
        device = dispositivo()
        if device == "cpu" and not os.environ.get("SIGMA_VISTA_DEVICE"):
            device = self._libera_gpu() or "cpu"
        cmd = [str(server), "-m", str(modello), "--mmproj", str(mmproj),
               "--host", "127.0.0.1", "--port", str(PORTA),
               "-c", "8192", "-np", "1", "--temp", "0", "--no-webui",
               # Sotto i 1024 token visivi Qwen-VL sbaglia le coordinate dei
               # riquadri (llama.cpp #16842): servono per trovare le vignette.
               "--image-min-tokens", "1024"]
        env = dict(os.environ)
        if device.startswith("gpu:"):
            # Il processo vede solo la sua scheda: vedendole entrambe l'allocatore
            # CUDA fallisce quando l'altra e' occupata da un render.
            env["CUDA_VISIBLE_DEVICES"] = device.split(":", 1)[1]
            cmd += ["--device", "CUDA0", "-ngl", "99"]
            if "A3B" in modello.name:
                cmd += ["--cpu-moe"]
        else:
            # Senza --no-mmproj-offload il proiettore finirebbe comunque sulla GPU 0.
            cmd += ["--device", "none", "-ngl", "0", "--no-mmproj-offload"]

        log_path = paths.var_dir() / "logs" / "sigma_vista.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        flags = subprocess.CREATE_NO_WINDOW if IS_WINDOWS else 0
        with open(log_path, "ab") as out:
            # cwd nella cartella del server: senza, ggml non trova le DLL dei backend GPU.
            self._proc = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT,
                                          creationflags=flags, cwd=str(server.parent), env=env)
        _assign_kill_on_close(self._proc)
        url = f"http://127.0.0.1:{PORTA}"
        scadenza = time.monotonic() + 300
        while time.monotonic() < scadenza:
            if self._proc.poll() is not None:
                self._proc = None
                raise VistaError(f"il server di visione e' terminato all'avvio; vedi {log_path}")
            if self._vivo(url):
                self._url = url
                self._ultimo_uso = time.monotonic()
                log.info("[Vista] %s pronto su %s", modello.name, device)
                return
            time.sleep(1)
        self.ferma()
        raise VistaError("il server di visione non risponde dopo 5 minuti")

    def ferma(self) -> None:
        proc, self._proc = self._proc, None
        self._url = ""
        self._rilascia_gpu()
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                proc.kill()

    def _assicura(self) -> str:
        if self._proc and self._proc.poll() is None and self._url and self._vivo(self._url):
            return self._url
        giudice = f"http://127.0.0.1:{PORTA_GIUDICE}"
        if self._vivo(giudice) and self._serve_qwen3vl(giudice):
            return giudice
        propria = f"http://127.0.0.1:{PORTA}"
        if self._vivo(propria) and self._serve_qwen3vl(propria):
            # Lasciato da un'istanza precedente di Sigma: e' lo stesso modello.
            return propria
        self.ferma()
        self._avvia()
        if not self._sorvegliante or not self._sorvegliante.is_alive():
            self._sorvegliante = threading.Thread(
                target=self._spegni_se_inattivo, name="vista-inattivita", daemon=True)
            self._sorvegliante.start()
        return self._url

    def _spegni_se_inattivo(self) -> None:
        while self._proc is not None:
            time.sleep(30)
            if self._lock.acquire(blocking=False):
                try:
                    if self._proc and time.monotonic() - self._ultimo_uso > INATTIVITA_S:
                        log.info("[Vista] inattivo: server di visione spento")
                        self.ferma()
                finally:
                    self._lock.release()

    def chiedi(self, domanda: str, max_tokens: int = MAX_TOKENS) -> str:
        """Una domanda di solo testo allo stesso modello, che non ragiona prima di rispondere.

        Il 27B della chat ragiona sempre (il suo template ignora enable_thinking):
        per rileggere le voci di un capitolo spendeva i token nel ragionamento e
        non arrivava al JSON. L'8B instruct risponde subito, gia' acceso in VRAM.
        """
        corpo = {"messages": [{"role": "user", "content": domanda}], "temperature": 0, "seed": 1234,
                 "cache_prompt": False, "max_tokens": max_tokens, "repeat_penalty": 1.05, "repeat_last_n": 256}
        with self._lock:
            url = self._assicura()
            try:
                resp = requests.post(f"{url}/v1/chat/completions", json=corpo, timeout=900)
            except requests.ConnectionError:
                self.ferma()
                self._avvia()
                resp = requests.post(f"{self._url}/v1/chat/completions", json=corpo, timeout=900)
            self._ultimo_uso = time.monotonic()
            if self._lease:
                from core.engine.gpu_lease import leases
                leases.renew(self._lease)
        resp.raise_for_status()
        testo = resp.json()["choices"][0]["message"]["content"] or ""
        return re.sub(r"<think>.*?</think>", "", testo, flags=re.S).strip()

    def guarda(self, immagine_jpeg: bytes, domanda: str) -> Tuple[str, str]:
        """Manda l'immagine e la domanda; restituisce la risposta e il modello usato."""
        contenuto = [
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + base64.b64encode(immagine_jpeg).decode()}},
            {"type": "text", "text": domanda},
        ]
        # A temperatura zero l'8B, elencando i testi di una pagina, ricomincia
        # l'elenco all'infinito: una penalita' lieve lo interrompe senza
        # alterare le trascrizioni, e `tronca_ripetizioni` fa il resto.
        corpo = {"messages": [{"role": "user", "content": contenuto}], "temperature": 0,
                 "seed": 1234, "cache_prompt": False, "max_tokens": MAX_TOKENS,
                 "repeat_penalty": 1.05, "repeat_last_n": 256}
        with self._lock:
            url = self._assicura()
            try:
                resp = requests.post(f"{url}/v1/chat/completions", json=corpo, timeout=900)
            except requests.ConnectionError:
                # Il server del giudice puo' spegnersi da solo fra due domande:
                # si riparte col proprio e si ritenta una volta.
                log.warning("[Vista] server caduto durante la richiesta: riavvio")
                self.ferma()
                self._avvia()
                url = self._url
                resp = requests.post(f"{url}/v1/chat/completions", json=corpo, timeout=900)
            self._ultimo_uso = time.monotonic()
            if self._lease:
                from core.engine.gpu_lease import leases
                leases.renew(self._lease)
        resp.raise_for_status()
        dati = resp.json()
        testo = dati["choices"][0]["message"]["content"] or ""
        testo = re.sub(r"<think>.*?</think>", "", testo, flags=re.S).strip()
        return tronca_ripetizioni(testo), Path(str(dati.get("model") or "")).name


occhio = Occhio()


def tronca_ripetizioni(testo: str, massimo: int = RIPETIZIONI_MAX) -> str:
    """Taglia la risposta alla prima riga che torna piu' di `massimo` volte.

    Un elenco ripetuto non e' solo rumore: riempie il budget dell'osservazione
    e fa sembrare all'agente che la pagina contenga dieci volte gli stessi testi.
    """
    viste: Dict[str, int] = {}
    tenute: List[str] = []
    for riga in testo.splitlines():
        chiave = re.sub(r"\s+", " ", riga).strip().lower()
        if len(chiave) >= RIGA_MINIMA:
            viste[chiave] = viste.get(chiave, 0) + 1
            if viste[chiave] > massimo:
                tenute.append("[il modello ha cominciato a ripetersi: risposta interrotta qui]")
                break
        tenute.append(riga)
    return "\n".join(tenute).strip()


def risolvi_percorso(path: str, radice: Optional[str] = None) -> Path:
    """Il file da guardare: assoluto, dal workspace del run o dalla radice del progetto.

    La radice del progetto serve perche' un run in worktree non ha `data/`
    (non versionata), ed e' proprio li' che stanno le immagini dell'utente.
    """
    grezzo = str(path or "").strip().strip('"').strip("'")
    if not grezzo:
        raise VistaError("manca 'path': il file immagine da guardare")
    candidato = Path(grezzo).expanduser()
    basi = [Path(radice)] if radice else [Path.cwd()]
    tentativi = [candidato] if candidato.is_absolute() else [
        *(b / candidato for b in basi), paths.project_root() / candidato]
    for p in tentativi:
        if p.is_file():
            if p.suffix.lower() not in ESTENSIONI:
                raise VistaError(
                    f"{p.name} non e' un'immagine ({', '.join(sorted(ESTENSIONI))})")
            return p.resolve()
    # L'agente indovina spesso l'estensione (005.png per 005.jpg): con i nomi
    # simili nella stessa cartella si corregge da solo invece di cercare con glob.
    simili = []
    for p in tentativi:
        if p.parent.is_dir():
            simili = sorted(q.name for q in p.parent.glob(f"{p.stem}.*") if q.suffix.lower() in ESTENSIONI)
            if simili:
                break
    if simili:
        raise VistaError(f"immagine non trovata: {grezzo}; nella stessa cartella c'e': {', '.join(simili[:5])}")
    raise VistaError(f"immagine non trovata: {grezzo}")


def _regione(region: Any, larghezza: int, altezza: int) -> Optional[Tuple[int, int, int, int]]:
    """[x0, y0, x1, y1] in pixel, oppure in frazioni 0..1 della pagina.

    Le frazioni esistono perche' il modello non conosce le dimensioni in pixel
    finche' non le chiede, e «la meta' in basso» e' [0, 0.5, 1, 1].
    """
    if region in (None, "", []):
        return None
    if isinstance(region, str):
        region = [v for v in re.split(r"[,\s]+", region.strip("[]() ")) if v]
    if not isinstance(region, (list, tuple)) or len(region) != 4:
        raise VistaError("'region' deve essere [x0, y0, x1, y1] (pixel o frazioni 0-1)")
    try:
        valori = [float(v) for v in region]
    except (TypeError, ValueError):
        raise VistaError("'region' contiene valori non numerici") from None
    if all(0.0 <= v <= 1.0 for v in valori):
        valori = [valori[0] * larghezza, valori[1] * altezza,
                  valori[2] * larghezza, valori[3] * altezza]
    x0, y0, x1, y1 = (int(round(v)) for v in valori)
    x0, x1 = sorted((max(0, min(x0, larghezza)), max(0, min(x1, larghezza))))
    y0, y1 = sorted((max(0, min(y0, altezza)), max(0, min(y1, altezza))))
    if x1 - x0 < 8 or y1 - y0 < 8:
        raise VistaError(f"'region' troppo piccola ({x1 - x0}x{y1 - y0} px)")
    return x0, y0, x1, y1


def prepara(percorso: Path, region: Any = None) -> Tuple[bytes, Dict[str, Any]]:
    """L'immagine in JPEG, ritagliata e ridotta, con le sue dimensioni originali."""
    try:
        from PIL import Image
    except ImportError:
        # Pillow non e' una dipendenza del kernel: senza, si manda il file com'e'.
        if region not in (None, "", []):
            raise VistaError("ritagliare una regione richiede Pillow, non installato") from None
        return percorso.read_bytes(), {}
    try:
        with Image.open(percorso) as img:
            img = img.convert("RGB")
            larghezza, altezza = img.size
            info: Dict[str, Any] = {"width": larghezza, "height": altezza}
            box = _regione(region, larghezza, altezza)
            if box:
                img = img.crop(box)
                info["region"] = list(box)
            lato = max(img.size)
            scala = 1.0
            if lato > LATO_MASSIMO:
                scala = LATO_MASSIMO / lato
            elif lato < LATO_MINIMO:
                scala = min(2.0, LATO_MASSIMO / lato)
            if scala != 1.0:
                img = img.resize((max(1, int(img.width * scala)), max(1, int(img.height * scala))),
                                 Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=90)
            return buf.getvalue(), info
    except VistaError:
        raise
    except Exception as exc:
        raise VistaError(f"immagine non leggibile ({percorso.name}): {exc}") from exc


def view_image(path: str = "", question: str = "", region: Any = None,
               radice: Optional[str] = None) -> Dict[str, Any]:
    """Guarda un'immagine dal disco e riporta cosa contiene, testo compreso."""
    t0 = time.monotonic()
    try:
        percorso = risolvi_percorso(path, radice)
        dati, info = prepara(percorso, region)
        richiesta = (question or "").strip() or PROMPT_DESCRIZIONE
        risposta, modello = occhio.guarda(dati, f"{PROMPT_BASE}\n\n{richiesta}")
    except VistaError as exc:
        return _esito(False, path=str(path), error=str(exc))
    except requests.RequestException as exc:
        log.warning("[Vista] richiesta fallita per %s: %s", path, exc)
        return _esito(False, path=str(path), error=f"server di visione non raggiungibile: {exc}")
    if not risposta:
        return _esito(False, path=str(percorso), error="il modello di visione non ha risposto nulla")
    return _esito(True, path=str(percorso).replace("\\", "/"), description=risposta,
                  model=modello, seconds=round(time.monotonic() - t0, 1), **info)


def descrivi(result: Dict[str, Any]) -> str:
    """L'osservazione per l'agente: la descrizione, senza l'involucro JSON."""
    if not result.get("success"):
        return f"Tool 'view_image' fallito: {result.get('error')}\n"
    dove = result.get("path", "")
    if result.get("region"):
        dove += f" (regione {result['region']} di {result.get('width')}x{result.get('height')} px)"
    elif result.get("width"):
        dove += f" ({result.get('width')}x{result.get('height')} px)"
    return (
        f"Tool 'view_image' su {dove}, visto da {result.get('model') or 'Qwen3-VL'} "
        f"in {result.get('seconds')} s:\n{result.get('description', '')}\n"
        "[E' la lettura di un modello di visione: puo' sbagliare un testo piccolo. "
        "Per un dettaglio ritaglia con 'region' e riguarda.]\n"
    )


ESECUTORI = {"view_image": view_image}


def esegui(tool_name: str, args: Dict[str, Any],
           radice: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Il punto d'ingresso che `loop.py` chiama. None se il tool non e' di visione."""
    funzione = ESECUTORI.get(str(tool_name or "").strip().lower())
    if funzione is None:
        return None
    args = dict(args or {})
    # Sinonimi dei parametri: il modello usa i nomi che vede altrove.
    for sinonimo in ("file", "file_path", "image", "percorso"):
        if sinonimo in args and "path" not in args:
            args["path"] = args.pop(sinonimo)
    for sinonimo in ("prompt", "query", "domanda"):
        if sinonimo in args and "question" not in args:
            args["question"] = args.pop(sinonimo)
    for sinonimo in ("crop", "box", "bbox", "regione"):
        if sinonimo in args and "region" not in args:
            args["region"] = args.pop(sinonimo)
    args.pop("radice", None)
    try:
        return funzione(**args, radice=radice)
    except TypeError as exc:
        return _esito(False, error=(
            f"Argomenti sbagliati per 'view_image': {exc}. "
            "Accettati: path (obbligatorio), question, region [x0,y0,x1,y1]."))
    except Exception as exc:
        log.exception("[Vista] '%s' fallito", tool_name)
        return _esito(False, error=str(exc))
