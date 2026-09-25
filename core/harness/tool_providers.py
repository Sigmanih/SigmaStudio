# ==============================================================================
# core/harness/tool_providers.py — I tool dei moduli, visti dal kernel
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Il punto in cui un modulo aggancia i propri tool, e il kernel non lo nomina.

Prima di questo file il kernel conosceva i tool di due moduli: li dichiarava in
`tool_schema.py`, li classificava in `policy.py`, li concedeva in `roles.py` e li
smistava in `loop.py` importando i moduli per eseguirli. Significava che il
kernel non stava in piedi senza due moduli opzionali, e che un modulo
disinstallato lasciava dietro di se' ventisette dichiarazioni che nessuno poteva
soddisfare.

**Il verso e' uno solo.** Un modulo chiama `register()`, il kernel chiede
`dispatch()`. Nessun nome di tool compare in questo file, e il kernel non ha modo
di sapere chi si e' registrato: e' esattamente cio' che serve perche' un modulo si
possa installare senza toccare il kernel.

**Cosa dichiara un provider.** Gli schemi (cio' che il modello vede), un solo
esecutore, la classe di sicurezza di ogni tool (se tocca o no i file), gli alias
con cui un modello puo' chiamarli e i ruoli che il modulo porta con se'. Sono le
cinque cose che prima stavano scritte in cinque file del kernel.

**Cosa non fa.** Non conosce i nomi: non sa quali tool abbiano i moduli
installati, non sa quanti provider ci sono, non sa cosa significhi "pista".
Chiede, e riceve.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import (Any, Callable, Dict, FrozenSet, List, Optional, Tuple)

from core.harness import policy, tool_schema
from core.logger import get_logger

log = get_logger("tool_providers")


class ProviderError(RuntimeError):
    """Il provider non e' registrabile: un errore adesso, non un tool fantasma dopo."""


@dataclass(frozen=True)
class ToolProvider:
    """I tool di un modulo, con cio' che serve al kernel per eseguirli."""

    #: Identificativo del provider: l'id del modulo, cosi' che il log dica chi e'.
    id: str
    #: Nome leggibile, per i messaggi.
    label: str
    #: Gli schemi JSON che il modello vede, nella forma di `tool_schema._f`.
    schemas: Tuple[Dict[str, Any], ...]
    #: Nome del tool e argomenti: None se il nome non e' suo.
    execute: Callable[[str, Dict[str, Any]], Optional[Dict[str, Any]]]
    #: Tool che guardano il progetto senza toccarlo.
    read_only: FrozenSet[str] = frozenset()
    #: Tool che scrivono sui file del progetto.
    write: FrozenSet[str] = frozenset()
    #: Nome con cui un modello puo' chiamare un tool, compreso il proprio.
    aliases: Dict[str, str] = field(default_factory=dict)
    #: Definizioni `DevRole` che il modulo porta con se'.
    roles: Tuple[Any, ...] = ()

    def tools(self) -> FrozenSet[str]:
        return frozenset(self.read_only | self.write)

    def names(self) -> FrozenSet[str]:
        """I nomi che questo provider possiede, alias compresi."""
        return frozenset(s["function"]["name"] for s in self.schemas
                         if (s or {}).get("function"))


#: Id del provider -> provider.
_provider: Dict[str, ToolProvider] = {}
#: Nome del tool -> id del provider che lo possiede.
_proprietario: Dict[str, str] = {}


def _nomi(provider: ToolProvider) -> List[str]:
    return [s["function"]["name"] for s in provider.schemas
            if (s or {}).get("function") and s["function"].get("name")]


def _controlla(provider: ToolProvider) -> List[str]:
    """Verifica che il provider sia coerente, e restituisce i suoi nomi.

    I controlli sono severi perche' un errore qui e' invisibile dopo: uno schema
    senza esecutore si dichiara al modello e fallisce alla prima chiamata, un
    tool non classificato passa o viene rifiutato secondo il posto in cui lo si
    guarda, e un nome gia' di un altro provider decide quale implementazione
    gira in base all'ordine di installazione.
    """
    if not str(provider.id or "").strip():
        raise ProviderError("Il provider non ha un id.")
    if not callable(provider.execute):
        raise ProviderError(f"Il provider '{provider.id}' non ha un esecutore.")
    nomi = _nomi(provider)
    if not nomi:
        raise ProviderError(f"Il provider '{provider.id}' non dichiara nessun tool.")
    if len(set(nomi)) != len(nomi):
        ripetuti = sorted({n for n in nomi if nomi.count(n) > 1})
        raise ProviderError(f"Il provider '{provider.id}' dichiara due volte: "
                            f"{', '.join(ripetuti)}.")
    dichiarati = set(nomi)
    miei = {n for n, p in _proprietario.items() if p == provider.id}
    fuori = dichiarati & (tool_schema.declared_tools() - miei)
    if fuori:
        raise ProviderError(
            f"Il provider '{provider.id}' dichiara tool che il kernel ha gia' "
            f"nel catalogo: {', '.join(sorted(fuori))}.")
    non_classificati = dichiarati - set(provider.read_only) - set(provider.write)
    if non_classificati:
        raise ProviderError(
            f"Il provider '{provider.id}' non dice quali tool scrivono: "
            f"{', '.join(sorted(non_classificati))}.")
    ignoti = set(provider.aliases.values()) - dichiarati
    if ignoti:
        raise ProviderError(
            f"Il provider '{provider.id}' ha alias che puntano a tool "
            f"inesistenti: {', '.join(sorted(ignoti))}.")
    return nomi



def register(provider: ToolProvider) -> List[str]:
    """Aggancia i tool di un modulo al kernel. Restituisce i nomi registrati.

    Registrare due volte lo stesso provider e' un aggiornamento, non un errore:
    un modulo si puo' ricaricare, e la seconda registrazione deve sostituire la
    prima invece di lasciare due schemi con lo stesso nome.
    """
    _controlla(provider)
    if provider.id in _provider:
        unregister(provider.id)
    nomi = tool_schema.register_schemas(provider.schemas)
    mancanti = set(provider.names()) - set(nomi)
    if mancanti:
        # A meta' strada si torna indietro: un provider registrato a meta'
        # dichiara al modello tool che nessuno esegue.
        tool_schema.deregister_schemas(nomi)
        raise ProviderError(
            f"Il provider '{provider.id}' non e' stato registrato: schemi "
            f"rifiutati {', '.join(sorted(mancanti))}.")
    _provider[provider.id] = provider
    for nome in nomi:
        _proprietario[nome] = provider.id
    policy.registra_provider(read_only=provider.read_only, write=provider.write,
                             alias=provider.aliases, label=provider.label)
    for ruolo in provider.roles or ():
        from core.harness import roles as ruoli
        ruoli.register_role(ruolo)
    log.info("[Providers] '%s' registrato: %d tool, %d ruoli.",
             provider.id, len(nomi), len(provider.roles or ()))
    return nomi


def unregister(provider_id: str) -> bool:
    """Stacca un provider e tutto cio' che aveva dichiarato."""
    provider = _provider.pop(str(provider_id), None)
    if provider is None:
        return False
    nomi = [n for n, p in _proprietario.items() if p == provider.id]
    for nome in nomi:
        _proprietario.pop(nome, None)
    tool_schema.deregister_schemas(nomi)
    log.info("[Providers] '%s' rimosso: %d tool.", provider.id, len(nomi))
    return True


def clear() -> None:
    """Stacca tutti i provider. Serve alle prove, per partire da zero.

    Si tolgono i tool: un tool senza proprietario si dichiarerebbe al modello
    senza che nessuno lo possa eseguire.
    """
    for provider_id in list(_provider):
        unregister(provider_id)


def providers() -> Tuple[ToolProvider, ...]:
    return tuple(_provider.values())


def owner(tool_name: str) -> Optional[str]:
    """Chi possiede questo tool, o None se non e' di nessun provider."""
    return _proprietario.get(str(tool_name or "").strip().lower())


def schemas() -> List[Dict[str, Any]]:
    """Tutti gli schemi dei provider registrati, in ordine di registrazione."""
    return [schema for provider in _provider.values()
            for schema in provider.schemas]


def write_tools() -> set:
    return {n for p in _provider.values() for n in p.write}


def read_tools() -> set:
    return {n for p in _provider.values() for n in p.read_only}


def dispatch(tool_name: str,
             args: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Esegue un tool di un provider. None se nessun provider lo possiede.

    Un provider che solleva non interrompe il turno: l'errore torna al modello
    nella stessa forma di un tool fallito, perche' per il ciclo e' la stessa
    cosa — un tentativo che non ha prodotto niente — e una traccia di stack al
    posto di un risultato costerebbe il run.
    """
    nome = str(tool_name or "").strip().lower()
    proprietario = _proprietario.get(nome)
    if proprietario is None:
        return None
    provider = _provider.get(proprietario)
    if provider is None:      # pragma: no cover - `unregister` mantiene la coerenza
        return {"tool": nome, "success": False,
                "error": f"Provider '{proprietario}' non piu' registrato."}
    try:
        esito = provider.execute(nome, dict(args or {}))
    except Exception as exc:
        log.exception("[Providers] '%s' di '%s' fallito", nome, proprietario)
        return {"tool": nome, "success": False,
                "error": f"{type(exc).__name__}: {exc}"}
    if esito is None:
        # Il provider possiede il nome ma non lo esegue: e' un suo difetto, e
        # dirlo e' meglio che lasciar cadere la chiamata nel vuoto.
        return {"tool": nome, "success": False,
                "error": (f"Il provider '{proprietario}' possiede '{nome}' ma "
                          "non lo ha eseguito.")}
    return esito
