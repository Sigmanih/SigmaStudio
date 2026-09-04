# ==============================================================================
# core/harness/role_registry.py — I ruoli come dato, non come codice
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Le definizioni dei ruoli, leggibili e modificabili senza toccare Python.

Un ruolo e' la personalizzazione di un agente: prompt, campionamento, tool
ammessi, server MCP, modello preferito, budget di turni. Finche' viveva in un
dizionario Python, ogni consumatore se lo ricostruiva a modo suo: il Developer
Studio aveva i suoi cinque, la tab Pipelines i suoi nodi, il provider server
nessuno. Come dato invece e' uno solo — la tab Pipelines lo modifica, l'harness
lo esegue, lo scheduler lo pianifica, il provider lo espone.

**Come si compone.** I cinque ruoli di sviluppo restano nel codice come base:
un'installazione senza file di configurazione deve funzionare, e un file
cancellato per sbaglio non deve lasciare il sistema senza ruoli. Sopra di essi
si sovrappone `config/roles.json`, che puo' ridefinire un singolo campo di un
ruolo esistente o aggiungerne di nuovi. La sovrapposizione e' per campo, non
per ruolo intero: cambiare il modello del Coder non deve costringere a
ricopiarne il prompt.

**Cosa non fa.** Non decide quale modello caricare ne' quando: dice soltanto
quale preferisce il ruolo. La residenza dei modelli e' un problema del motore,
e tenerli separati e' cio' che permette a un ruolo di funzionare anche su una
macchina dove quel modello non c'e'.
"""

import json
import threading
from dataclasses import asdict, fields, replace
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.paths import roles_config_file
from core.harness.roles import DEV_ROLES, DevRole

log = get_logger("role_registry")

#: Campi che un file di configurazione puo' ridefinire. Volutamente esplicito:
#: un campo sconosciuto in un JSON scritto a mano e' quasi sempre un errore di
#: battitura, e accettarlo in silenzio significherebbe applicare un'impostazione
#: che l'utente crede attiva e non lo e'.
CAMPI_MODIFICABILI = {
    "name", "icon", "system_prompt", "temperature", "top_p", "top_k",
    "max_tokens", "max_turns", "tools", "focus_areas", "model", "mcp",
}

#: Campi che sono tuple nel dataclass e liste nel JSON.
CAMPI_SEQUENZA = {"tools", "focus_areas", "mcp"}

_lock = threading.RLock()
_cache: Optional[Dict[str, DevRole]] = None
_firma: Optional[tuple] = None


# ---------------------------------------------------------------------------
# Conversione
# ---------------------------------------------------------------------------

def role_to_dict(role: DevRole) -> Dict[str, Any]:
    """La forma serializzabile di un ruolo, con le tuple rese liste."""
    grezzo = asdict(role)
    for campo in CAMPI_SEQUENZA:
        if campo in grezzo and grezzo[campo] is not None:
            grezzo[campo] = list(grezzo[campo])
    return grezzo


def _applica(base: DevRole, patch: Dict[str, Any]) -> DevRole:
    """Il ruolo con i campi ridefiniti dal file, e nient'altro."""
    modifiche: Dict[str, Any] = {}
    nomi_validi = {f.name for f in fields(DevRole)}
    for chiave, valore in (patch or {}).items():
        if chiave in ("id",):
            continue
        if chiave not in CAMPI_MODIFICABILI or chiave not in nomi_validi:
            log.warning(
                "[Roles] campo '%s' ignorato per il ruolo '%s': non modificabile",
                chiave, base.id,
            )
            continue
        if chiave in CAMPI_SEQUENZA:
            valore = tuple(valore or ())
        modifiche[chiave] = valore
    if not modifiche:
        return base
    return replace(base, **modifiche)


def _da_zero(rid: str, patch: Dict[str, Any]) -> Optional[DevRole]:
    """Un ruolo che il codice non conosce, definito interamente dal file."""
    prompt = str(patch.get("system_prompt") or "").strip()
    if not prompt:
        log.warning("[Roles] ruolo '%s' scartato: manca system_prompt", rid)
        return None
    base = DevRole(
        id=rid,
        name=str(patch.get("name") or rid.title()),
        icon=str(patch.get("icon") or "🤖"),
        system_prompt=prompt,
    )
    return _applica(base, patch)


# ---------------------------------------------------------------------------
# Lettura
# ---------------------------------------------------------------------------

def _firma_file() -> tuple:
    try:
        st = roles_config_file().stat()
        return (int(st.st_mtime_ns), st.st_size)
    except OSError:
        return (0, 0)


def load_roles(force: bool = False) -> Dict[str, DevRole]:
    """Tutti i ruoli: quelli del codice, sovrascritti da quelli del file.

    Memorizzato e riletto solo quando il file cambia: viene chiamato a ogni
    creazione di RoleEngine, e rileggere il disco ogni volta sarebbe un costo
    per un dato che cambia una volta al mese.
    """
    global _cache, _firma
    firma = _firma_file()
    with _lock:
        if not force and _cache is not None and _firma == firma:
            return dict(_cache)

    ruoli: Dict[str, DevRole] = dict(DEV_ROLES)
    percorso = roles_config_file()
    if percorso.is_file():
        try:
            documento = json.loads(percorso.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            # Un file rotto non deve lasciare il sistema senza ruoli: si
            # continua con i predefiniti e lo si dice forte.
            log.error("[Roles] '%s' illeggibile (%s): uso i ruoli predefiniti",
                      percorso, exc)
            documento = {}

        definizioni = documento.get("roles") if isinstance(documento, dict) else documento
        if isinstance(definizioni, list):
            definizioni = {str(v.get("id")): v for v in definizioni if isinstance(v, dict)}
        if isinstance(definizioni, dict):
            for rid, patch in definizioni.items():
                rid = str(rid).strip()
                if not rid or not isinstance(patch, dict):
                    continue
                if rid in ruoli:
                    ruoli[rid] = _applica(ruoli[rid], patch)
                else:
                    nuovo = _da_zero(rid, patch)
                    if nuovo is not None:
                        ruoli[rid] = nuovo
            log.info("[Roles] %d ruoli attivi (%d predefiniti + file)",
                     len(ruoli), len(DEV_ROLES))

    with _lock:
        _cache = dict(ruoli)
        _firma = firma
    return dict(ruoli)


def get_role(role_id: str) -> Optional[DevRole]:
    return load_roles().get(str(role_id or "").strip())


def list_roles() -> List[Dict[str, Any]]:
    """I ruoli in forma serializzabile, per la UI e per il provider."""
    return [role_to_dict(r) for r in load_roles().values()]


# ---------------------------------------------------------------------------
# Scrittura
# ---------------------------------------------------------------------------

def save_role(role_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Scrive la personalizzazione di un ruolo. Ritorna il ruolo risultante.

    Sul file finisce solo cio' che differisce dal predefinito: un file che
    ricopia i cinque prompt integrali diventerebbe la copia da aggiornare a
    mano ogni volta che il codice cambia — lo stesso difetto delle due copie
    del Developer Studio, in piccolo.
    """
    rid = str(role_id or "").strip()
    if not rid:
        raise ValueError("role_id mancante")

    percorso = roles_config_file()
    documento: Dict[str, Any] = {"roles": {}}
    if percorso.is_file():
        try:
            letto = json.loads(percorso.read_text(encoding="utf-8"))
            if isinstance(letto, dict) and isinstance(letto.get("roles"), dict):
                documento = letto
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("[Roles] '%s' non rileggibile (%s): riparto pulito",
                        percorso, exc)

    corrente = dict(documento["roles"].get(rid) or {})
    for chiave, valore in (patch or {}).items():
        if chiave == "id":
            continue
        if chiave not in CAMPI_MODIFICABILI:
            raise ValueError(f"Campo non modificabile: '{chiave}'")
        corrente[chiave] = list(valore) if chiave in CAMPI_SEQUENZA else valore
    documento["roles"][rid] = corrente

    percorso.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = percorso.with_suffix(".json.tmp")
    temporaneo.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporaneo.replace(percorso)

    risultante = load_roles(force=True).get(rid)
    if risultante is None:
        raise ValueError(f"Ruolo '{rid}' non valido dopo la scrittura")
    return role_to_dict(risultante)


def delete_role(role_id: str) -> bool:
    """Rimuove la personalizzazione di un ruolo, tornando al predefinito.

    Un ruolo che esiste solo nel file sparisce; uno predefinito torna com'era
    nel codice. In entrambi i casi il sistema resta con dei ruoli validi.
    """
    rid = str(role_id or "").strip()
    percorso = roles_config_file()
    if not rid or not percorso.is_file():
        return False
    try:
        documento = json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(documento, dict) or rid not in (documento.get("roles") or {}):
        return False
    documento["roles"].pop(rid, None)
    percorso.write_text(
        json.dumps(documento, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    load_roles(force=True)
    return True


def invalidate() -> None:
    """Dimentica la copia in memoria: la prossima lettura torna al disco."""
    global _cache, _firma
    with _lock:
        _cache = None
        _firma = None
