"""Server MCP per la ricerca semantica del codice sorgente.

Implementa una ricerca basata su TF-IDF + cosine similarity (fallback puro,
senza dipendenze esterne) che permette di trovare codice per significato
es. 'gestione errori di rete' anziché solo testo esatto.

L'indice persiste in var/semantic_index/ ed è ricreabile.
"""

import json
import math
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from core.logger import get_logger
from core.mcp.base_server import BaseMCPServer
from core.harness.workspace import resolve_root

logger = get_logger(__name__)

INDEX_SUBDIR = Path("var") / "semantic_index"
INDEX_FILENAME = "index.json"

# Estensioni da indicizzare
CODE_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".css", ".html", ".md", ".json", ".yaml", ".yml", ".toml", ".cfg", ".ini"}

# Directory da escludere dall'indicizzazione
EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".cache", "store", "config", "var"}

#: Quanti file si guardano cercando quelli nuovi, e per quanto tempo: `index_status`
#: non puo' costare quanto una indicizzazione, e deve dirlo quando si ferma.
#: Un secondo, non due: misurato il 23 settembre 2026, `index_status` su questo
#: repository costa 4,2 secondi in tutto (3 di caricamento dell'indice piu' la
#: passeggiata) - ed e' un tool che si chiama per sapere come sta l'indice, non
#: per aspettare. La passeggiata dichiara comunque di essere parziale.
SCANSIONE_MASSIMA = 6000
SECONDI_DI_SCANSIONE = 1.0


def _candidati(base: Path) -> Iterator[Path]:
    """I file che l'indice puo' contenere, secondo i suoi criteri.

    Sta fuori da `_build_index` perche' serve anche a chi cerca i file *nuovi*:
    due passeggiate con due filtri diversi darebbero due idee diverse di cosa
    merita di stare nell'indice.
    """
    for file in base.rglob("*"):
        try:
            rel = file.relative_to(base)
        except ValueError:
            continue
        # L'indice non indicizza se stesso: `index.json` e' un `.json` dentro la
        # radice, quindi senza questa riga entrava nel proprio indice, si
        # contava come «file nuovo» a ogni controllo e si dichiarava sempre
        # indietro - un allarme che suona sempre non e' un allarme.
        if rel.parts[:len(INDEX_SUBDIR.parts)] == INDEX_SUBDIR.parts:
            continue
        parts = rel.parts
        if any(p in EXCLUDE_DIRS or p.startswith(".") for p in parts[:-1]):
            continue
        if not file.is_file():
            continue
        if file.suffix.lower() not in CODE_EXTENSIONS:
            continue
        try:
            if file.stat().st_size > 500 * 1024:
                continue
        except OSError:
            continue
        yield file



def _tokenize(text: str) -> List[str]:
    """Tokenizza il testo in parole minuscole, rimuovendo punteggiatura."""
    # Estrae parole alfanumeriche di lunghezza >= 2
    tokens = re.findall(r"[a-zA-Z0-9_]{2,}", text.lower())
    return tokens


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Calcola la Term Frequency (frequenza relativa)."""
    counter = Counter(tokens)
    total = len(tokens) if tokens else 1
    return {term: count / total for term, count in counter.items()}


def _compute_idf(documents_tokens: List[List[str]]) -> Dict[str, float]:
    """Calcola l'Inverse Document Frequency."""
    n_docs = len(documents_tokens)
    if n_docs == 0:
        return {}
    
    doc_freq = Counter()
    for tokens in documents_tokens:
        unique_terms = set(tokens)
        for term in unique_terms:
            doc_freq[term] += 1
    
    # IDF con smoothing: log((N + 1) / (df + 1)) + 1
    idf = {}
    for term, df in doc_freq.items():
        idf[term] = math.log((n_docs + 1) / (df + 1)) + 1.0
    return idf


def _tfidf_vector(tf: Dict[str, float], idf: Dict[str, float]) -> Dict[str, float]:
    """Calcola il vettore TF-IDF."""
    return {term: tf_val * idf.get(term, 0.0) for term, tf_val in tf.items()}


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Calcola la similarità di cosine tra due vettori sparse."""
    if not vec_a or not vec_b:
        return 0.0
    
    # Calcola il prodotto scalare (solo termini comuni)
    common_terms = set(vec_a.keys()) & set(vec_b.keys())
    dot_product = sum(vec_a[term] * vec_b[term] for term in common_terms)
    
    # Norme
    norm_a = math.sqrt(sum(v ** 2 for v in vec_a.values()))
    norm_b = math.sqrt(sum(v ** 2 for v in vec_b.values()))
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return dot_product / (norm_a * norm_b)


class SemanticMCPServer(BaseMCPServer):
    """Server MCP per la ricerca semantica del codice."""

    def __init__(self) -> None:
        super().__init__(
            name="Semantic Code Search",
            version="1.0.0",
            description="Ricerca semantica del codice sorgente",
        )
        self._index: Optional[Dict[str, Any]] = None
        self._load_index()
        
        # Registra i tool con handler
        self.register_tool(
            name="semantic_search",
            description="Cerca nel codice sorgente per significato (non solo testo esatto). "
                       "Esempio: 'gestione errori di rete' o 'validazione input'. "
                       "Restituisce file, righe e snippet ordinati per rilevanza.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "La query semantica in linguaggio naturale"},
                    "top_k": {"type": "integer", "description": "Numero massimo di risultati (default: 10)", "default": 10},
                    "force_fallback": {"type": "boolean", "description": "Forza il fallback TF-IDF anche se sentence-transformers è disponibile", "default": False}
                },
                "required": ["query"]
            },
            handler=lambda query, top_k=10, force_fallback=False: self._semantic_search(query, top_k, force_fallback)
        )
        
        self.register_tool(
            name="index_codebase",
            description="Costruisce o aggiorna l'indice semantico del codice sorgente. "
                       "Scansiona tutti i file di codice nel workspace e crea un indice TF-IDF.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=lambda: self._build_index()
        )
        
        self.register_tool(
            name="index_status",
            description="Mostra lo stato dell'indice semantico: se esiste, quando è stato creato, quanti file contiene, e quanti file sono cambiati, nuovi o spariti da allora. Se dice che l'indice è indietro, esegui index_codebase.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            handler=lambda: self._index_status()
        )

        self.register_tool(
            name="explain_code",
            description="Spiega il ruolo di un simbolo (funzione, classe, modulo) o file nel contesto del progetto. "
                       "Usa l'indice semantico per trovare il simbolo e restituisce snippet, percorso e contesto.",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Nome del simbolo (funzione, classe, modulo) da spiegare"},
                    "path_hint": {"type": "string", "description": "Opzionale: percorso parziale per restringere la ricerca"}
                },
                "required": ["symbol"]
            },
            handler=lambda symbol, path_hint=None: self._explain_code(symbol, path_hint)
        )

    def _index_status(self) -> Dict[str, Any]:
        """Stato dell'indice, con quanto e' indietro rispetto al disco.

        Un indice senza la nozione di «vecchio» e' una mappa che si dichiara
        sempre buona: chi cerca ci crede e lavora sul codice di ieri senza
        saperlo. Qui si contano le tre cose che rendono vecchia una mappa - un
        file cambiato, un file sparito, un file mai visto - e si dice cosa fare.
        """
        if not self._index:
            return {
                "exists": False,
                "message": "Indice non costruito. Usa index_codebase per crearlo.",
            }
        fresco = self._freschezza(con_scansione=True)
        esito: Dict[str, Any] = {
            "exists": True,
            "created_at": self._index.get("created_at", ""),
            "total_documents": self._index.get("total_documents", 0),
            **fresco,
        }
        if not fresco["aggiornato"]:
            esito["message"] = (
                "L'indice e' indietro rispetto al disco (%d cambiati, %d nuovi, "
                "%d spariti su %d esaminati). Esegui index_codebase prima di "
                "fidarti dei risultati della ricerca."
                % (fresco["modificati"], fresco["nuovi"], fresco["spariti"],
                   fresco["esaminati"]))
        return esito

    def _quando_costruito(self) -> float:
        """Quando l'indice e' stato costruito.

        Il numero c'e' per gli indici nuovi; per quelli costruiti prima si usa la
        data del file, perche' senza una data un indice vecchio risulterebbe
        eternamente fresco - che e' il difetto, non un caso limite.
        """
        costruito = (self._index or {}).get("built_at")
        if isinstance(costruito, (int, float)) and costruito > 0:
            return float(costruito)
        try:
            return self._index_file().stat().st_mtime
        except OSError:
            return 0.0

    def _freschezza(self, con_scansione: bool = True) -> Dict[str, Any]:
        """Quanto l'indice e' indietro: cambiati, nuovi, spariti.

        Le prime due voci costano uno `stat` per documento. La terza costa una
        passeggiata sull'albero, quindi ha un tetto di file e di tempo e
        **dichiara** se l'ha toccato: un controllo parziale che si presenta come
        completo e' peggio di un controllo mancante.
        """
        documenti = list((self._index or {}).get("documents") or [])
        base = Path(resolve_root())
        costruito = self._quando_costruito()

        modificati = 0
        spariti = 0
        percorsi_indicizzati = set()
        for doc in documenti:
            rel = str(doc.get("path") or "")
            percorsi_indicizzati.add(rel)
            intero = base / rel
            try:
                quando = intero.stat().st_mtime
            except OSError:
                spariti += 1
                continue
            if costruito and quando > costruito:
                modificati += 1

        nuovi = 0
        esaminati = 0
        scansione_parziale = False
        if con_scansione:
            scadenza = time.monotonic() + SECONDI_DI_SCANSIONE
            for file in _candidati(base):
                esaminati += 1
                if esaminati > SCANSIONE_MASSIMA or time.monotonic() > scadenza:
                    scansione_parziale = True
                    break
                try:
                    rel = str(file.relative_to(base)).replace("\\", "/")
                except ValueError:
                    continue
                if rel not in percorsi_indicizzati and rel.replace("/", "\\") not in percorsi_indicizzati:
                    nuovi += 1

        return {
            "aggiornato": bool(not modificati and not nuovi and not spariti),
            "modificati": modificati,
            "nuovi": nuovi,
            "spariti": spariti,
            "esaminati": esaminati,
            "scansione_parziale": scansione_parziale,
            "costruito_il": costruito,
        }

    def _segna_vecchi(self, risultati: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Marca i risultati che vengono da un file cambiato dopo l'indice.

        Solo dove serve: un risultato fresco resta esattamente com'era, e quello
        vecchio se lo porta scritto addosso. Costa uno `stat` per risultato, non
        per documento.
        """
        base = Path(resolve_root())
        costruito = self._quando_costruito()
        if not costruito:
            return risultati
        for voce in risultati:
            try:
                if (base / str(voce.get("file") or "")).stat().st_mtime > costruito:
                    voce["stale"] = True
            except OSError:
                voce["mancante"] = True
        return risultati

    def _explain_code(self, symbol: str, path_hint: Optional[str] = None) -> Dict[str, Any]:
        """Trova il simbolo nell'indice e restituisce contesto e snippet."""
        if not self._index or not self._index.get("documents"):
            return {"error": "Indice non disponibile. Esegui prima index_codebase."}

        docs = self._index["documents"]
        # Filtra per path_hint se specificato
        if path_hint:
            docs = [d for d in docs if path_hint.lower() in d.get("path", "").lower()]

        # Cerca il simbolo nel nome o nel contenuto
        matches = []
        for doc in docs:
            name = doc.get("name", "")
            content = doc.get("content", "")
            if symbol.lower() in name.lower() or symbol.lower() in content.lower():
                matches.append(doc)

        if not matches:
            return {"error": f"Simbolo '{symbol}' non trovato nell'indice."}

        # Prendi il primo match più rilevante (più lungo o con più occorrenze)
        best = max(matches, key=lambda d: len(d.get("content", "")))
        return {
            "symbol": symbol,
            "path": best.get("path", ""),
            "name": best.get("name", ""),
            "snippet": best.get("content", "")[:500],
            "occurrences": len(matches)
        }
    
    def _index_dir(self) -> Path:
        return Path(resolve_root()) / INDEX_SUBDIR

    def _index_file(self) -> Path:
        return self._index_dir() / INDEX_FILENAME

    def _load_index(self) -> None:
        """Carica l'indice dal disco se esiste."""
        idx_file = self._index_file()
        if idx_file.exists():
            try:
                with open(idx_file, "r", encoding="utf-8") as f:
                    self._index = json.load(f)
                logger.info("Indice semantico caricato da %s (%d documenti)", idx_file, len(self._index.get("documents", [])))
            except Exception as e:
                logger.warning("Errore nel caricamento dell'indice: %s", e)
                self._index = None
        else:
            self._index = None

    def _save_index(self) -> None:
        """Salva l'indice su disco."""
        idx_dir = self._index_dir()
        idx_file = self._index_file()
        idx_dir.mkdir(parents=True, exist_ok=True)
        with open(idx_file, "w", encoding="utf-8") as f:
            json.dump(self._index, f, ensure_ascii=False, indent=2)
        logger.info("Indice semantico salvato in %s (%d documenti)", idx_file, len(self._index.get("documents", [])))
    
    def _build_index(self) -> Dict[str, Any]:
        """Costruisce l'indice TF-IDF del codice sorgente."""
        logger.info("Costruzione indice semantico...")
        
        # Raccolta documenti
        documents: List[Dict[str, Any]] = []
        all_tokens: List[List[str]] = []

        base = Path(resolve_root())
        for file in _candidati(base):
            ext = file.suffix.lower()

            # Legge il file
            try:
                content = file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            # Tokenizza
            tokens = _tokenize(content)
            if not tokens:
                continue

            # Estrae snippet (prime 3 righe non vuote) e numero di riga del primo contenuto
            lines = [line.strip() for line in content.splitlines() if line.strip()]
            snippet = "\n".join(lines[:3])
            first_line = next((i + 1 for i, l in enumerate(content.splitlines()) if l.strip()), 1)

            # Estrae il nome del simbolo principale (classe/funzione) per explain_code
            name = file.stem
            if ext == ".py":
                m = re.search(r"^(?:class|def)\s+([A-Za-z_][A-Za-z0-9_]*)", content, re.MULTILINE)
                if m:
                    name = m.group(1)

            doc = {
                "path": str(file.relative_to(base)),
                "name": name,
                "content": content[:2000],  # contenuto troncato per explain_code
                "tokens": tokens,
                "snippet": snippet,
                "line_start": first_line,
                "size": len(content)
            }
            documents.append(doc)
            all_tokens.append(tokens)
        
        # Calcola IDF
        idf = _compute_idf(all_tokens)
        
        # Calcola vettori TF-IDF per ogni documento
        for doc in documents:
            tf = _compute_tf(doc["tokens"])
            doc["vector"] = _tfidf_vector(tf, idf)
            del doc["tokens"]  # Libera memoria
        
        self._index = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            # Il numero, non solo la data leggibile: e' quello che permette di
            # chiedersi «questo file e' cambiato dopo?».
            "built_at": time.time(),
            "documents": documents,
            "idf": idf,
            "total_documents": len(documents),
            "status": "success"
        }
        
        self._save_index()
        logger.info("Indice costruito: %d documenti", len(documents))
        return self._index
    
    def _semantic_search(self, query: str, top_k: int = 10, force_fallback: bool = False) -> List[Dict[str, Any]]:
        """Esegue la ricerca semantica."""
        if not self._index or not self._index.get("documents"):
            self._build_index()

        if not self._index or not self._index.get("documents"):
            return []
        
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        idf = self._index["idf"]
        query_tf = _compute_tf(query_tokens)
        query_vector = {term: tf_val * idf.get(term, 0.0) for term, tf_val in query_tf.items()}

        results = []

        # Se force_fallback, salta il cosine e va direttamente al fuzzy
        if not force_fallback:
            for doc in self._index["documents"]:
                score = _cosine_similarity(query_vector, doc["vector"])
                if score > 0.0:
                    results.append({
                        "file": doc["path"],
                        "line_start": doc.get("line_start", 1),
                        "score": round(score, 4),
                        "snippet": doc["snippet"]
                    })

        # Se il cosine non ha trovato nulla (o force_fallback), matching fuzzy con sinonimi
        if not results:
            logger.info("Nessun risultato con cosine similarity, provo match fuzzy sui token")
            # Mappa di sinonimi IT→EN per concetti comuni nello sviluppo software
            _sinonimi = {
                "gestione": ["handle", "manage", "process", "error", "exception"],
                "errori": ["error", "exception", "fault", "fail"],
                "errore": ["error", "exception", "fault", "fail"],
                "rete": ["network", "socket", "http", "tcp", "udp", "connection"],
                "retry": ["retry", "reconnect", "backoff", "attempt"],
                "rotte": ["route", "endpoint", "api", "path"],
                "rotta": ["route", "endpoint", "api", "path"],
                "autenticazione": ["auth", "login", "token", "session", "jwt"],
                "autorizzazione": ["auth", "permission", "role", "access"],
                "database": ["db", "sql", "query", "table", "model"],
                "cache": ["cache", "memoize", "redis", "store"],
                "configurazione": ["config", "setting", "option", "env"],
                "interfaccia": ["ui", "component", "render", "view"],
                "frontend": ["react", "jsx", "tsx", "vite", "component"],
                "backend": ["api", "route", "handler", "endpoint"],
            }
            # Costruisce l'insieme di termini da cercare: token originali + sinonimi
            search_terms = set()
            for tok in query_tokens:
                search_terms.add(tok)
                if tok in _sinonimi:
                    search_terms.update(_sinonimi[tok])
            # Cerca nei documenti: un match se almeno un termine compare nel contenuto/nome/snippet
            # Usa anche i token completi del documento (non solo i 2000 caratteri troncati)
            for doc in self._index["documents"]:
                content_lower = doc.get("content", "").lower()
                name_lower = doc.get("name", "").lower()
                snippet_lower = doc.get("snippet", "").lower()
                # Token completi del documento (se presenti nell'indice)
                doc_tokens_set = set(doc.get("tokens", [])) if isinstance(doc.get("tokens"), list) else set()
                matched_count = 0
                for term in search_terms:
                    if len(term) < 3:
                        continue
                    # Match come substring nel testo visibile O match esatto su un token del documento
                    if term in content_lower or term in name_lower or term in snippet_lower:
                        matched_count += 1
                    elif term in doc_tokens_set:
                        matched_count += 1
                # Se nessun match con i termini originali, prova con le prime 4 lettere di ogni termine
                if matched_count == 0:
                    for term in search_terms:
                        if len(term) >= 5:
                            prefix = term[:4]
                            if prefix in content_lower or prefix in name_lower or prefix in snippet_lower:
                                matched_count += 1
                                break
                if matched_count > 0:
                    # Punteggio proporzionale al numero di termini matched
                    score = min(0.05 + matched_count * 0.02, 0.3)
                    results.append({
                        "file": doc["path"],
                        "line_start": doc.get("line_start", 1),
                        "score": round(score, 4),
                        "snippet": doc["snippet"]
                    })
            # Se ancora nessun risultato, usa un fallback generico: cerca i token più lunghi della query
            if not results and len(query_tokens) > 0:
                logger.info("Fallback fuzzy fallito, provo con i token più lunghi della query")
                long_tokens = [t for t in query_tokens if len(t) >= 4]
                if long_tokens:
                    for doc in self._index["documents"]:
                        content_lower = doc.get("content", "").lower()
                        name_lower = doc.get("name", "").lower()
                        snippet_lower = doc.get("snippet", "").lower()
                        matched_count = 0
                        for term in long_tokens:
                            if term in content_lower or term in name_lower or term in snippet_lower:
                                matched_count += 1
                        if matched_count > 0:
                            score = min(0.03 + matched_count * 0.01, 0.2)
                            results.append({
                                "file": doc["path"],
                                "line_start": doc.get("line_start", 1),
                                "score": round(score, 4),
                                "snippet": doc["snippet"]
                            })
        
        # Ordina per score decrescente
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return self._segna_vecchi(results[:top_k])
