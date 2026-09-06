# ==============================================================================
# core/harness/node_runner.py — Un nodo di pipeline eseguito dall'harness
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Far lavorare un nodo del designer visuale come lavora l'agente sviluppatore.

Il designer di pipeline produceva nodi che non eseguivano niente: al posto
della risposta di un modello metteva una stringa segnaposto — «Esecuzione nodo
X per l'obiettivo Y» — e la passava al nodo successivo come se fosse un
risultato. Una pipeline intera poteva quindi «completarsi» senza che nessun
modello avesse mai risposto.

Qui i nodi vengono eseguiti davvero, e attraverso lo stesso percorso
dell'agente sviluppatore: tool, ledger, cancello di completamento. Cio' che
cambia da nodo a nodo e' il ruolo, e il ruolo decide tutto il resto — prompt,
tool ammessi, modello preferito, budget di turni — perche' e' gia' un dato nel
registro dei ruoli.

**Due tipi di nodo, non uno.** Non ogni nodo deve poter toccare i file: un nodo
che riassume, traduce o riformula non ha bisogno di strumenti, e dargliene
significherebbe solo offrirgli modi di sbagliare. Il ruolo dichiarato distingue
i due casi:

* un ruolo del registro (`architect`, `coder`, `tester`...) produce un **nodo
  agente**: cicla, usa i tool, registra cio' che fa nel ledger e non puo'
  dichiarare finito senza prove;
* un ruolo sconosciuto o `custom` produce un **nodo di prompt**: una sola
  generazione, nessun tool, il testo che ne esce e' il risultato.

**Un solo ledger per pipeline.** Come per l'orchestratore: e' cio' che
distingue una squadra da una fila di estranei. Il nodo che verifica vede i file
che il nodo che implementa ha scritto, e nessuno rilegge quello che un altro ha
gia' letto.
"""

from typing import Any, Callable, Dict, Generator, List, Optional

from core.logger import get_logger

log = get_logger("pipeline_node")

#: Ruoli che non stanno nel registro e non devono esserci cercati: sono il modo
#: del designer di dire "nessun ruolo particolare".
RUOLI_GENERICI = frozenset({"", "custom", "generico", "generalist", "none"})

#: Quanto testo di un nodo a monte entra nel prompt di quello a valle. Oltre,
#: non e' contesto: e' la finestra di chi deve ancora lavorare, spesa per
#: rileggere cio' che e' gia' stato deciso.
MAX_CHARS_PER_UPSTREAM = 4000


def concrete_model(nome: Optional[str]) -> Optional[str]:
    """Il nome di un modello, o None se e' solo un modo di dire "scegli tu".

    Il designer manda "sigmaengine" quando l'utente non ha scelto niente, e il
    motore lo riceveva come se fosse il nome di un checkpoint: cercava un
    modello chiamato cosi', non lo trovava, e il nodo falliva con «Nessun
    modello con pesi». Gli alias generici sono gli stessi che riconoscono i
    ruoli — la stessa distinzione fra una scelta e la sua assenza.
    """
    from core.harness.roles import GENERIC_MODEL_ALIASES

    pulito = str(nome or "").strip()
    return pulito if pulito.lower() not in GENERIC_MODEL_ALIASES else None


def node_role(node: Dict[str, Any]) -> str:
    """Il ruolo dichiarato da un nodo, normalizzato."""
    config = node.get("config") or {}
    return str(config.get("role") or "").strip().lower()


def is_agent_node(node: Dict[str, Any]) -> bool:
    """Se questo nodo deve girare con i tool, o e' solo una generazione.

    La domanda si risolve nel registro dei ruoli e non in un elenco scritto
    qui: aggiungere un ruolo al registro deve bastare a renderlo eseguibile in
    una pipeline, senza toccare questo file.
    """
    ruolo = node_role(node)
    if not ruolo or ruolo in RUOLI_GENERICI:
        return False
    try:
        from core.harness.role_registry import get_role
        return get_role(ruolo) is not None
    except Exception as exc:
        log.debug("[Nodo] registro dei ruoli non leggibile: %s", exc)
        return False


def build_node_prompt(
    node: Dict[str, Any],
    goal: str,
    upstream_outputs: Optional[Dict[str, str]] = None,
) -> str:
    """Il messaggio che il nodo riceve: obiettivo, istruzioni sue, cio' che arriva da monte.

    L'ordine conta. L'obiettivo apre — e' la cosa che il nodo non deve perdere
    di vista — e i risultati di monte chiudono, perche' sono la parte che
    cambia a ogni esecuzione e vanno letti come "ecco cosa hai davanti", non
    come premessa.
    """
    config = node.get("config") or {}
    pezzi: List[str] = []

    if goal:
        pezzi.append(f"OBIETTIVO DELLA PIPELINE:\n{goal}")

    istruzioni = str(config.get("prompt") or "").strip()
    if istruzioni:
        pezzi.append(f"IL TUO COMPITO IN QUESTO NODO:\n{istruzioni}")
    else:
        etichetta = node.get("label") or node.get("id") or "questo nodo"
        pezzi.append(f"IL TUO COMPITO IN QUESTO NODO: {etichetta}")

    for nodo_id, testo in (upstream_outputs or {}).items():
        testo = str(testo or "").strip()
        if not testo:
            continue
        if len(testo) > MAX_CHARS_PER_UPSTREAM:
            testo = testo[:MAX_CHARS_PER_UPSTREAM] + "\n[...troncato]"
        pezzi.append(f"RISULTATO DEL NODO '{nodo_id}':\n{testo}")

    return "\n\n".join(pezzi)


def run_node(
    node: Dict[str, Any],
    goal: str,
    upstream_outputs: Optional[Dict[str, str]] = None,
    ledger: Optional[Any] = None,
    workspace_root: Optional[str] = None,
    session_id: Optional[str] = None,
    model_override: Optional[str] = None,
    should_cancel: Optional[Callable[[], bool]] = None,
) -> Generator[Dict[str, Any], None, None]:
    """Esegue un nodo e ne emette gli eventi; l'ultimo porta il testo prodotto.

    Gli eventi hanno la forma dell'harness (`token`, `tool_start`,
    `tool_result`, `status`...) piu' un `node_output` finale con il testo
    completo, che e' cio' che il runner passa ai nodi a valle.
    """
    nodo_id = str(node.get("id") or "nodo")
    etichetta = str(node.get("label") or nodo_id)
    config = node.get("config") or {}
    prompt = build_node_prompt(node, goal, upstream_outputs)

    if is_agent_node(node):
        yield from _run_agent_node(
            node, nodo_id, etichetta, prompt, ledger, workspace_root,
            session_id, model_override, should_cancel,
        )
        return

    yield from _run_prompt_node(
        nodo_id, etichetta, config, prompt, model_override, should_cancel
    )


def _run_agent_node(
    node, nodo_id, etichetta, prompt, ledger, workspace_root,
    session_id, model_override, should_cancel,
) -> Generator[Dict[str, Any], None, None]:
    """Un nodo con un ruolo del registro: cicla, usa i tool, lascia traccia."""
    from core.harness.roles import RoleEngine

    ruolo = node_role(node)
    engine = RoleEngine()
    testo: List[str] = []

    yield {"type": "status", "node_id": nodo_id,
           "text": f"Nodo '{etichetta}': ruolo {ruolo}, con strumenti"}

    try:
        for evento in engine.generate_with_role(
            ruolo, prompt,
            model_name=concrete_model(model_override),
            should_cancel=should_cancel,
            workspace_root=workspace_root,
            ledger=ledger,
            session_id=session_id,
        ):
            evento.setdefault("node_id", nodo_id)
            if evento.get("type") == "token":
                testo.append(evento.get("token", ""))
            yield evento
    except Exception as exc:
        log.exception("[Nodo %s] esecuzione fallita: %s", nodo_id, exc)
        yield {"type": "node_failed", "node_id": nodo_id, "error": str(exc)}
        return

    yield {"type": "node_output", "node_id": nodo_id, "output": "".join(testo)}


def _run_prompt_node(
    nodo_id, etichetta, config, prompt, model_override, should_cancel
) -> Generator[Dict[str, Any], None, None]:
    """Un nodo senza ruolo: una generazione sola, nessuno strumento.

    Non passa dal ciclo dell'agente di proposito. Quel ciclo porta con se' il
    protocollo delle tool call, il ledger e il cancello di completamento: a un
    nodo che deve riassumere un testo non servono, e il prompt di sistema che
    li spiega sarebbe piu' lungo del compito.
    """
    from core.harness.providers import stream_dev_generation

    sistema = str(config.get("system_prompt") or "").strip() or (
        "Sei un nodo di una pipeline di lavoro. Esegui esattamente il compito "
        "che ti viene assegnato e rispondi con il risultato, senza premesse. "
        "Rispondi in italiano."
    )
    testo: List[str] = []

    yield {"type": "status", "node_id": nodo_id,
           "text": f"Nodo '{etichetta}': generazione senza strumenti"}

    try:
        for chunk in stream_dev_generation(
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": prompt},
            ],
            prompt=prompt,
            system_prompt=sistema,
            provider=config.get("provider"),
            model_name=concrete_model(model_override) or concrete_model(config.get("model")),
            temperature=float(config.get("temperature") or 0.7),
            max_tokens=int(config.get("max_tokens") or 4096),
            cancel_check=should_cancel,
        ):
            if chunk.get("error"):
                messaggio = chunk.get("message") or "errore di generazione"
                yield {"type": "node_failed", "node_id": nodo_id, "error": messaggio}
                return
            token = chunk.get("token")
            if token:
                testo.append(token)
                yield {"type": "token", "node_id": nodo_id, "token": token}
    except Exception as exc:
        log.exception("[Nodo %s] generazione fallita: %s", nodo_id, exc)
        yield {"type": "node_failed", "node_id": nodo_id, "error": str(exc)}
        return

    yield {"type": "node_output", "node_id": nodo_id, "output": "".join(testo)}
