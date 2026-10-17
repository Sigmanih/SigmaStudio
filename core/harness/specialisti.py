# ==============================================================================
# core/harness/specialisti.py — Consultare la procedura di un ruolo specialistico
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Far leggere all'agente generico la procedura di uno specialista.

La chat in Dev Mode esegue sempre l'agente generico, col prompt da
ingegnere del software. I ruoli dei moduli — l'adattatore di fumetti, il
produttore video, l'ingegnere EDA — esistono, hanno tool e procedura, ma la
loro procedura non arrivava mai al modello: nel progetto Mx0 l'agente aveva
tutti i tool giusti e li ha usati nell'ordine sbagliato, creando due
personaggi inventati ("l'eroe", "l'avversario") prima ancora di cercare i
nomi nelle battute appena lette.

Con `consult_role` l'agente legge la procedura dello specialista quando il
lavoro e' di quel dominio, e la segue con i tool che ha gia'. E' una lettura:
non cambia permessi ne' prompt di sistema, che restano il prefisso fisso del run.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from core.logger import get_logger

log = get_logger("harness_specialisti")

#: I ruoli di base dello sviluppo software: li conosce gia' il prompt generico.
RUOLI_DI_BASE = frozenset({"architect", "coder", "reviewer", "tester", "devops"})


def _esito(ok: bool, **extra: Any) -> Dict[str, Any]:
    return {"tool": "consult_role", "success": ok, **extra}


def specialisti() -> List[Dict[str, str]]:
    """I ruoli oltre a quelli di base, con una riga che dice a cosa servono."""
    from core.harness.roles import DEV_ROLES
    out = []
    for rid, ruolo in DEV_ROLES.items():
        if rid in RUOLI_DI_BASE:
            continue
        focus = ", ".join(list(getattr(ruolo, "focus_areas", ()) or ())[:2])
        out.append({"id": rid, "name": str(getattr(ruolo, "name", rid)), "focus": focus})
    return sorted(out, key=lambda r: r["id"])


def sezione_prompt() -> str:
    """L'elenco degli specialisti per il prompt, con l'istruzione di consultarli."""
    voci = specialisti()
    if not voci:
        return ""
    righe = [f"- `{r['id']}` — {r['name']}" + (f": {r['focus']}" if r["focus"] else "") for r in voci]
    return ("## SPECIALISTI\n"
            "Per un lavoro che non e' codice (un video, un fumetto da trasporre, un circuito) c'e' uno "
            "specialista con la sua procedura. PRIMA di cominciare chiama `consult_role` con il suo id e "
            "segui la procedura che ti restituisce, passo per passo: dice in che ordine usare i tool e "
            "cosa verificare. Non improvvisare la sequenza.\n"
            + "\n".join(righe))


def consult_role(role: str = "") -> Dict[str, Any]:
    """Procedura, tool e priorita' di un ruolo specialistico."""
    from core.harness.roles import DEV_ROLES
    rid = str(role or "").strip().lower()
    ruolo = DEV_ROLES.get(rid)
    if ruolo is None:
        disponibili = ", ".join(r["id"] for r in specialisti())
        return _esito(False, error=f"Ruolo sconosciuto: '{role}'. Specialisti disponibili: {disponibili}")
    return _esito(True, role=rid, name=str(getattr(ruolo, "name", rid)),
                  procedure=str(getattr(ruolo, "system_prompt", "") or "").strip(),
                  tools=list(getattr(ruolo, "tools", ()) or ()),
                  focus=list(getattr(ruolo, "focus_areas", ()) or ()))


def descrivi(result: Dict[str, Any]) -> str:
    """L'osservazione: la procedura come testo, non come JSON da decifrare."""
    if not result.get("success"):
        return f"Tool 'consult_role' fallito: {result.get('error')}\n"
    return (f"Procedura dello specialista `{result['role']}` ({result['name']}). Seguila passo per passo "
            f"con i tuoi tool.\n\n{result['procedure']}\n\nTool previsti da questa procedura: "
            + ", ".join(result.get("tools") or []) + "\n")


ESECUTORI = {"consult_role": consult_role}


def esegui(tool_name: str, args: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """Il punto d'ingresso che `loop.py` chiama. None se il tool non e' questo."""
    funzione = ESECUTORI.get(str(tool_name or "").strip().lower())
    if funzione is None:
        return None
    args = dict(args or {})
    for sinonimo in ("role_id", "id", "name", "ruolo", "specialist"):
        if sinonimo in args and "role" not in args:
            args["role"] = args.pop(sinonimo)
    try:
        return funzione(**args)
    except TypeError as exc:
        return _esito(False, error=f"Argomenti sbagliati per 'consult_role': {exc}. Accettato: role.")
