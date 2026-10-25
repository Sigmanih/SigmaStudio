# ==============================================================================
# core/developer_studio/orchestrator.py — AI Development Orchestrator
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Central orchestrator that decomposes development goals into task DAGs,
assigns roles, manages parallel/serial execution, and handles feedback loops.

The orchestrator is the brain of the Developer Studio IDE. It:
1. Receives a development goal from the user
2. Uses the Architect role to analyse and decompose it into tasks
3. Creates a branch via the DevOps role
4. Executes tasks in dependency order, using the appropriate role
5. Runs verification (Tester + Reviewer in parallel)
6. Handles feedback loops when tests fail
7. Commits and creates a PR via the DevOps role

Supports two modes:
- **Interactive**: pauses for user approval at each phase transition
- **Autonomous**: runs the full pipeline without stopping
"""

import time
import uuid
import threading
from typing import Any, Callable, Dict, Generator, List, Optional

from core.logger import get_logger
from core.harness.roles import RoleEngine, DEV_ROLES
from core.harness.context import DevContextManager
from core.harness.pipeline import TaskNode, TaskPipeline, TaskStatus
from core.harness.plan import canonical_role, descrivi_task, normalizza_piano
from core.harness import autocorrezione
from core.harness.ledger import DevSessionLedger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Execution mode
# ---------------------------------------------------------------------------

#: Quanto si attende l'approvazione di una fase prima di rinunciare.
#: Cinque minuti: abbastanza perche' l'utente legga il piano, poco
#: abbastanza da non lasciare un thread appeso per sempre se chiude la scheda.
APPROVAL_TIMEOUT_S = 300.0


class ExecutionMode:
    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"


# ---------------------------------------------------------------------------
# Workflow phases
# ---------------------------------------------------------------------------

PHASES = [
    {"id": "analyze", "name": "Analisi", "icon": "🏗️", "role": "architect"},
    {"id": "setup", "name": "Setup Git", "icon": "🔀", "role": "devops"},
    {"id": "implement", "name": "Implementazione", "icon": "⚙️", "role": "coder"},
    {"id": "verify", "name": "Verifica", "icon": "🧪", "role": "tester"},
    {"id": "deliver", "name": "Delivery", "icon": "🚀", "role": "devops"},
]


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DevOrchestrator:
    """Central orchestrator for AI-driven development workflows.

    Events are yielded as dicts with a `type` field, following the same
    pattern as the existing admin agent streaming:

    - phase_start / phase_end
    - role_switch
    - task_start / task_done / task_failed
    - pipeline_update
    - approval_required (interactive mode)
    - token / thought / status (from role generation)
    - error / cancelled / done
    """

    def __init__(self, workspace_root: Optional[str] = None,
                 model_name: Optional[str] = None,
                 session_id: Optional[str] = None):
        self.role_engine = RoleEngine()
        self.context = DevContextManager(workspace_root)
        self.pipeline: Optional[TaskPipeline] = None
        self.model_name = model_name
        self.mode = ExecutionMode.INTERACTIVE
        self.session_id = session_id
        # Un solo ledger per obiettivo, condiviso da tutti i ruoli. E' cio' che
        # rende l'orchestratore una squadra invece di cinque estranei: il
        # Tester vede i file che il Coder ha scritto, il Reviewer sa quali
        # verifiche sono gia' passate, e nessuno rilegge quello che un altro
        # ha gia' letto.
        self.ledger: Optional[DevSessionLedger] = None
        #: Quante correzioni e quante ripianificazioni restano. Vive per
        #: tutto l'obiettivo: un tetto per task non impedirebbe a dieci
        #: task di correggersi tre volte ciascuno.
        self.bilancio = autocorrezione.Bilancio()
        #: L'albero isolato dell'obiettivo, quando e' stato chiesto.
        self._worktree = None
        #: Se il lavoro va riportato nell'albero principale alla chiusura.
        #: Falso finche' qualcuno non lo approva: il silenzio non e' un si'.
        self._applica_lavoro = False
        #: Revisione per singola scrittura, propagata a ogni ruolo.
        self.review_writes = False
        #: La riga di questo obiettivo nel registro delle attivita'.
        self._voce_attivita = ""
        self._cancel_event = threading.Event()
        #: fase -> evento su cui il thread di esecuzione attende.
        self._approval_events: Dict[str, threading.Event] = {}
        #: fase -> decisione, anche se arrivata prima dell'attesa.
        self._approval_decisions: Dict[str, str] = {}
        self._approval_lock = threading.RLock()

    def cancel(self) -> None:
        """Signal cancellation from outside."""
        self._cancel_event.set()
        # Sbloccare chi attende e' parte dell'annullamento: un'attesa lasciata
        # aperta terrebbe il thread fermo fino al timeout, molto dopo che
        # l'utente ha premuto stop.
        with self._approval_lock:
            for evento in self._approval_events.values():
                evento.set()

    # -- approvazioni --------------------------------------------------------

    def approve(self, phase_id: str, decision: str = "approved") -> bool:
        """Registra la decisione dell'utente su una fase e sblocca l'attesa.

        Ritorna False se nessuno stava aspettando quella fase: e' il caso di
        un'approvazione arrivata in ritardo o per una fase gia' passata, e va
        distinta da un successo perche' la UI deve poterlo dire.
        """
        fase = str(phase_id or "").strip()
        with self._approval_lock:
            evento = self._approval_events.get(fase)
            self._approval_decisions[fase] = (
                "approved" if str(decision).lower().startswith("appr") else "rejected"
            )
            if evento is None:
                return False
            evento.set()
            return True

    def pending_approval(self) -> Optional[str]:
        """La fase in attesa di approvazione, se ce n'e' una."""
        with self._approval_lock:
            for fase, evento in self._approval_events.items():
                if not evento.is_set():
                    return fase
        return None

    def _wait_for_approval(self, phase_id: str) -> str:
        """Attende la decisione sulla fase: 'approved', 'rejected' o 'timeout'."""
        with self._approval_lock:
            gia_deciso = self._approval_decisions.pop(phase_id, None)
            if gia_deciso:
                return gia_deciso
            evento = threading.Event()
            self._approval_events[phase_id] = evento

        ottenuta = evento.wait(timeout=APPROVAL_TIMEOUT_S)

        with self._approval_lock:
            self._approval_events.pop(phase_id, None)
            decisione = self._approval_decisions.pop(phase_id, None)

        if self._cancelled():
            return "rejected"
        if not ottenuta:
            return "timeout"
        return decisione or "approved"

    def _cancelled(self) -> bool:
        return self._cancel_event.is_set()

    # -- Main entry point ----------------------------------------------------

    def execute_goal(
        self,
        goal: str,
        mode: str = ExecutionMode.INTERACTIVE,
        model_name: Optional[str] = None,
        isolate_worktree: bool = False,
        review_run: bool = False,
        review_writes: bool = False,
    ) -> Generator[Dict[str, Any], None, None]:
        """Porta un obiettivo attraverso tutte le fasi, con la squadra.

        Le tre reti di sicurezza sono le stesse del singolo agente, ma
        **l'unita' su cui valgono e' l'obiettivo, non il ruolo**. E' la
        differenza che rende il flusso di squadra diverso da cinque run
        affiancati: isolare ogni ruolo nel proprio worktree darebbe cinque
        alberi che non si vedono fra loro, e il Tester non troverebbe i file
        che il Coder ha appena scritto. Si isola una volta sola, e tutti e
        cinque lavorano li' dentro.

        `review_writes` invece resta per ruolo: e' una domanda per singola
        scrittura, e l'unita' giusta e' la scrittura.
        """
        self.mode = mode
        self._cancel_event.clear()
        self.context.set_goal(goal)
        model = model_name or self.model_name
        self.review_writes = bool(review_writes)
        # Il bilancio vale per un obiettivo. L'orchestratore vive per sessione
        # e lo stesso oggetto puo' ricevere un secondo obiettivo: senza questo
        # azzeramento partirebbe con le correzioni gia' spese dal primo.
        self.bilancio = autocorrezione.Bilancio()

        # Lo stato di lavoro nasce qui e vive per tutto l'obiettivo: se la
        # sessione era gia' nota, riparte da dove si era interrotta.
        radice = self.context.session.workspace_root
        self.ledger = None
        if self.session_id:
            try:
                from core.harness import store as session_store
                self.ledger = session_store.load_ledger(self.session_id, goal, radice)
            except Exception as exc:
                log.debug("[Orchestrator] ripresa sessione fallita: %s", exc)
        if self.ledger is None:
            self.ledger = DevSessionLedger(goal=goal, workspace_root=radice)
        else:
            self.ledger.set_goal(goal)

        # L'isolamento e' dell'obiettivo: un albero solo, condiviso dai
        # cinque ruoli. Da qui in poi `self.context.session.workspace_root`
        # punta la' dentro, e ogni ruolo lo eredita senza saperlo.
        self._worktree = None
        if isolate_worktree and self.session_id:
            from core.harness import worktree as wt

            try:
                self._worktree = wt.create_session_worktree(
                    self.context.session.workspace_root, self.session_id)
            except Exception as exc:
                log.warning("[Orchestrator] isolamento non riuscito: %s", exc)
            if self._worktree is not None:
                self.context.session.workspace_root = str(self._worktree.worktree_path)
                yield {"type": "worktree_opened",
                       "branch": self._worktree.branch_name,
                       "path": str(self._worktree.worktree_path)}
            else:
                # Dirlo. Chi ha chiesto l'isolamento e lavora senza crederebbe
                # di essere protetto, ed e' peggio che non averlo chiesto.
                yield {"type": "status",
                       "text": "⚠️ Isolamento richiesto ma non disponibile "
                               "(la cartella non e' un repository git): i ruoli "
                               "scrivono direttamente nell'albero di lavoro."}

        yield {
            "type": "orchestrator_start",
            "goal": goal,
            "mode": mode,
            "phases": PHASES,
            "isolated": self._worktree is not None,
            "review_run": bool(review_run),
        }

        # L'obiettivo nel registro: e' il livello che interessa a chi guarda.
        # I singoli run dei ruoli si registrano da soli, ma «cinque ruoli su
        # questo obiettivo» e' la riga che risponde alla domanda vera.
        from core.harness import attivita

        self._voce_attivita = attivita.apri(
            "obiettivo", goal,
            workspace_root=self.context.session.workspace_root,
            session_id=self.session_id, mode=mode,
            isolated=self._worktree is not None,
        )
        try:
            yield from self._fasi(goal, model, review_run)
        finally:
            attivita.chiudi(
                self._voce_attivita,
                "completato" if not self._cancelled() else "interrotto",
                pipeline=self.pipeline.summary() if self.pipeline else None,
            )
            # Vale anche per lo stop a meta': un generatore abbandonato non
            # esegue le proprie ultime righe, e senza questo resterebbero un
            # worktree e un branch orfani a ogni interruzione.
            yield from self._chiudi_worktree()

    def _chiudi_worktree(self) -> Generator[Dict[str, Any], None, None]:
        """Chiude l'albero dell'obiettivo, se ne e' stato aperto uno."""
        if getattr(self, "_worktree", None) is None:
            return
        from core.harness import worktree as wt

        try:
            esito = wt.release_session_worktree(self.session_id,
                                                apply_changes=self._applica_lavoro)
        except Exception as exc:
            log.warning("[Orchestrator] chiusura worktree fallita: %s", exc)
            return
        finally:
            self._worktree = None
        if esito.get("branch"):
            yield {"type": "worktree_preserved", "branch": esito["branch"],
                   "applied": bool(esito.get("applied"))}

    def _fasi(self, goal: str, model: Optional[str],
              review_run: bool) -> Generator[Dict[str, Any], None, None]:
        """Le cinque fasi in fila, con revisione e consegna alla fine."""
        # --- Phase 1: Analysis (Architect) ---
        yield from self._run_phase("analyze", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 2: Git Setup (DevOps) ---
        yield from self._run_phase("setup", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 3: Implementation (Coder) ---
        yield from self._run_phase("implement", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 4: Verification (Tester + Reviewer) ---
        yield from self._run_phase("verify", goal, model)
        if self._cancelled():
            yield {"type": "cancelled", "reason": "Interrotto dall'utente."}
            return

        # --- Phase 5: Delivery ---
        # Con l'albero isolato la consegna passa dalla strada normale del
        # software — branch, `dev`, richiesta da accettare — che e' la stessa
        # del singolo agente. Senza, resta il DevOps che esegue git a mano:
        # e' l'unico modo quando non c'e' un branch da consegnare.
        if self._worktree is not None:
            yield from self._rivedi_e_consegna(review_run)
        else:
            yield from self._run_phase("deliver", goal, model)

        # --- Final report ---
        yield from self._emit_final_report()

    def _rivedi_e_consegna(self, review_run: bool) -> Generator[Dict[str, Any], None, None]:
        """Il diff dell'obiettivo, una volta, e poi la consegna.

        Si riusano le stesse funzioni del ciclo a un agente solo. Riscriverle
        qui vorrebbe dire due revisioni che divergono, e la seconda sarebbe
        quella che nessuno guarda.
        """
        from core.harness import review
        from core.harness.loop import consegna_il_lavoro, rivedi_lavoro_del_run

        self._applica_lavoro = True
        if review_run and self.session_id:
            gate = review.gate_for(self.session_id)
            for evento in rivedi_lavoro_del_run(
                    self._worktree, gate, self.session_id, True):
                if evento.get("type") == "__decisione__":
                    self._applica_lavoro = bool(evento.get("apply"))
                    continue
                yield evento
            if not self._applica_lavoro:
                return

        consegnato = False
        for evento in consegna_il_lavoro(
                self._worktree, self.context.session.workspace_root, self.ledger):
            if evento.get("type") == "__consegnato__":
                consegnato = bool(evento.get("ok"))
                continue
            yield evento
        if consegnato:
            # Consegnato altrove: nell'albero di lavoro non ci va.
            self._applica_lavoro = False

    # -- Phase execution -----------------------------------------------------

    def _run_phase(
        self,
        phase_id: str,
        goal: str,
        model: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """Execute a single workflow phase."""
        phase_def = next((p for p in PHASES if p["id"] == phase_id), None)
        if not phase_def:
            yield {"type": "error", "error": f"Fase sconosciuta: {phase_id}"}
            return

        self.context.set_phase(phase_id)
        from core.harness import attivita

        attivita.aggiorna(
            getattr(self, "_voce_attivita", ""),
            progress=f"fase {phase_def['name']} ({phase_def['role']})",
            phase=phase_id,
            pipeline=self.pipeline.summary() if self.pipeline else None,
        )
        yield {
            "type": "phase_start",
            "phase": phase_id,
            "name": phase_def["name"],
            "icon": phase_def["icon"],
            "role": phase_def["role"],
        }

        # Interactive mode: pause for approval before each phase
        if self.mode == ExecutionMode.INTERACTIVE:
            yield {
                "type": "approval_required",
                "phase": phase_id,
                "message": f"Procedere con la fase '{phase_def['name']}'?",
                "timeout_s": APPROVAL_TIMEOUT_S,
            }
            # Qui si aspetta davvero. Prima l'evento veniva emesso e la fase
            # partiva comunque: la modalita' interattiva chiedeva il permesso e
            # non ascoltava la risposta, il che e' peggio che non chiedere —
            # l'utente crede di avere un veto che non ha.
            decisione = self._wait_for_approval(phase_id)
            if decisione == "rejected":
                yield {
                    "type": "phase_skipped",
                    "phase": phase_id,
                    "reason": "Fase rifiutata dall'utente.",
                }
                return
            if decisione == "timeout":
                # Scaduta l'attesa non si prosegue: in modalita' interattiva
                # l'assenza di risposta e' assenza di consenso, e proseguire
                # significherebbe modificare il workspace di qualcuno che non
                # sta guardando.
                self._cancel_event.set()
                yield {
                    "type": "cancelled",
                    "reason": (
                        f"Nessuna approvazione per la fase '{phase_def['name']}' "
                        f"entro {APPROVAL_TIMEOUT_S}s: esecuzione interrotta."
                    ),
                }
                return
            if self._cancelled():
                return

        # Execute phase-specific logic
        if phase_id == "analyze":
            yield from self._phase_analyze(goal, model)
        elif phase_id == "setup":
            yield from self._phase_setup(goal, model)
        elif phase_id == "implement":
            yield from self._phase_implement(goal, model)
        elif phase_id == "verify":
            yield from self._phase_verify(goal, model)
        elif phase_id == "deliver":
            yield from self._phase_deliver(goal, model)

        yield {
            "type": "phase_end",
            "phase": phase_id,
            "name": phase_def["name"],
        }

    # -- Phase implementations -----------------------------------------------

    def _phase_analyze(self, goal: str, model: Optional[str]) -> Generator:
        """Architect analyses the codebase and creates the task plan."""
        context = self.context.build_context_for_role("architect")
        prompt = (
            f"Analizza il workspace e crea un piano implementativo per questo obiettivo:\n\n"
            f"**{goal}**\n\n"
            f"Usa list_dir e read_file per esplorare la struttura. "
            f"Poi crea una pipeline di task con il tool `pipeline`."
            f"\n\nPer ogni voce del piano, prima di scriverla:\n"
            f"1) elenca i file che deve toccare;\n"
            f"2) per ogni dato che la voce da per presente, cerca CHI lo produce e\n"
            f"verifica che arrivi in ingresso a quei file (search_code e read_file\n"
            f"sui chiamanti);\n"
            f"3) se il dato non arriva, o la voce include il file che lo porta, o\n"
            f"il criterio cambia.\n"
            f"Una premessa sbagliata in un piano diventa un difetto nel codice, e\n"
            f"chi esegue non ha modo di accorgersene: il 23 settembre 2026 e\n"
            f"costata 30 turni su 30 senza una riga scritta."
        )

        architect_output = []
        for event in self.role_engine.generate_with_role(
            "architect", prompt, context, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
        ):
            yield event
            # Capture text output for context
            if event.get("type") == "token":
                architect_output.append(event.get("token", ""))
            # Capture pipeline tasks
            if event.get("type") == "pipeline_update":
                tasks = event.get("tasks", [])
                self._build_pipeline_from_architect(tasks, goal)
                self._sync_pipeline()

        full_output = "".join(architect_output)
        self.context.record_role_output("architect", full_output)

    def _phase_setup(self, goal: str, model: Optional[str]) -> Generator:
        """DevOps creates a git branch for the work."""
        # Generate branch name from goal
        branch_hint = goal.lower()[:40].replace(" ", "-")
        context = self.context.build_context_for_role("devops")
        prompt = (
            f"Crea un branch Git per lavorare su questo obiettivo:\n\n"
            f"**{goal}**\n\n"
            f"Suggerimento nome branch: feat/{branch_hint}\n"
            f"Verifica prima lo stato con git_status, poi crea il branch."
        )

        devops_output = []
        for event in self.role_engine.generate_with_role(
            "devops", prompt, context, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
        ):
            yield event
            if event.get("type") == "token":
                devops_output.append(event.get("token", ""))
            # Track branch creation
            if event.get("type") == "tool_result":
                result = event.get("result", {})
                if result.get("tool") in ("git_branch_create", "git_checkout"):
                    msg = result.get("message", "")
                    if "creato" in msg or "switchato" in msg.lower():
                        # Extract branch name
                        import re
                        m = re.search(r"'([^']+)'", msg)
                        if m:
                            self.context.set_branch(m.group(1))

        self.context.record_role_output("devops", "".join(devops_output))

    def _phase_implement(self, goal: str, model: Optional[str]) -> Generator:
        """Coder implements the plan, task by task."""
        if not self.pipeline or not self.pipeline.nodes:
            # No structured plan — run as single task
            yield from self._single_task_implement(goal, model)
            return

        # I task pronti si eseguono a blocchi di ruolo omogeneo, non
        # nell'ordine in cui l'Architect li ha elencati. Il grafo dice cosa
        # puo' partire; il raggruppamento decide in che ordine conviene, e con
        # un modello per ruolo quell'ordine vale piu' del task stesso: senza,
        # si paga un cambio di modello a ogni passo.
        totale = len(self.pipeline.nodes)
        ruolo_corrente: Optional[str] = None
        eseguiti = 0
        # Limite di sicurezza: se un task non cambiasse mai stato, il ciclo
        # non avrebbe modo di accorgersene.
        for _ in range(totale + 5):
            if self._cancelled():
                return
            blocco = self.pipeline.next_role_batch(ruolo_corrente)
            if not blocco:
                break

            if blocco[0].role != ruolo_corrente:
                ruolo_corrente = blocco[0].role
                yield {
                    "type": "role_batch",
                    "role": ruolo_corrente,
                    "tasks": len(blocco),
                }
                yield {
                    "type": "status",
                    "text": (
                        f"⚙️ {len(blocco)} task consecutivi per il ruolo "
                        f"'{ruolo_corrente}' ({eseguiti}/{totale} completati)"
                    ),
                }

            for task in blocco:
                if self._cancelled():
                    return
                yield from self._execute_task(task, model)
                eseguiti += 1
                # Un fallimento deve produrre una mossa, non un vicolo cieco.
                # La ripianificazione rifa' il grafo sotto i piedi di questo
                # ciclo: si esce dal blocco e si riparte dal nuovo insieme di
                # task pronti, altrimenti si eseguirebbero nodi che il piano
                # nuovo ha appena sostituito.
                if task.status == TaskStatus.FAILED:
                    ripianificato = False
                    for evento in self._reagisci_al_fallimento(task, goal, model):
                        if evento.get("type") == "__ripianificato__":
                            ripianificato = bool(evento.get("ok"))
                            continue
                        yield evento
                    if ripianificato:
                        ruolo_corrente = None
                        totale = len(self.pipeline.nodes)
                        break

        rimasti = [n for n in self.pipeline.nodes.values() if not n.is_terminal]
        if rimasti:
            # Non e' un errore del ciclo: sono task le cui dipendenze sono
            # fallite, e dirlo e' piu' utile che finire in silenzio.
            yield {
                "type": "status",
                "text": (
                    f"⚠️ {len(rimasti)} task non eseguibili: dipendono da task falliti."
                ),
            }

    # -- autocorrezione ------------------------------------------------------

    def _reagisci_al_fallimento(self, task, goal: str,
                                model: Optional[str]) -> Generator:
        """Guarda cos'e' andato storto e fa la mossa successiva.

        Quattro mosse, in ordine di costo: riprovare, inserire una correzione
        mirata, tornare dall'Architetto, rinunciare dicendolo. La scelta la fa
        `core.harness.autocorrezione` sui fatti del ledger — non sul racconto
        del modello, che sa sempre produrre una spiegazione plausibile.

        Emette `__ripianificato__` per il chiamante, che deve sapere se il
        grafo gli e' cambiato sotto.
        """
        istantanea = {}
        try:
            istantanea = self.ledger.snapshot() if self.ledger else {}
        except Exception as exc:
            log.debug("[Orchestrator] ledger non leggibile: %s", exc)

        diagnosi = autocorrezione.diagnostica(task, istantanea, self.bilancio)
        esito = autocorrezione.applica(self.pipeline, task, diagnosi, self.bilancio)
        self._sync_pipeline()

        yield {
            "type": "self_correction",
            "task_id": task.id,
            "title": task.title,
            **diagnosi.to_dict(),
            **esito,
            "budget": self.bilancio.to_dict(),
        }

        if diagnosi.livello != autocorrezione.RIPIANIFICA:
            yield {"type": "__ripianificato__", "ok": False}
            return

        yield {"type": "status",
               "text": f"🏗️ Il piano non regge: {diagnosi.motivo}. Torno dall'Architetto."}
        ok = False
        for evento in self._ripianifica(diagnosi, goal, model):
            if evento.get("type") == "__piano_nuovo__":
                ok = bool(evento.get("ok"))
                continue
            yield evento
        yield {"type": "__ripianificato__", "ok": ok}

    def _ripianifica(self, diagnosi, goal: str, model: Optional[str]) -> Generator:
        """Richiama l'Architetto a meta' lavoro, con in mano cio' che e' fatto.

        Il contesto che riceve e' la parte che conta: senza l'elenco di cio'
        che e' gia' stato fatto, un piano nuovo riparte da zero e il lavoro
        buono viene rifatto — o sovrascritto con qualcosa di peggio.
        """
        contesto = self.context.build_context_for_role("architect")
        prompt = autocorrezione.contesto_per_ripianificare(
            self.pipeline, diagnosi, goal)

        grezzi = None
        for evento in self.role_engine.generate_with_role(
            "architect", prompt, contesto, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
        ):
            yield evento
            if evento.get("type") == "pipeline_update":
                grezzi = evento.get("tasks") or []

        if not grezzi:
            # Un Architetto che non emette un piano nuovo non ha ripianificato:
            # dirlo e' meglio che proseguire su un grafo che nessuno ha
            # cambiato, credendo di averlo cambiato.
            yield {"type": "status",
                   "text": "⚠️ L'Architetto non ha prodotto un piano nuovo: "
                           "resta quello di prima."}
            yield {"type": "__piano_nuovo__", "ok": False}
            return

        normalizzati, _ = normalizza_piano(grezzi)
        nuovi = [
            TaskNode(
                id=str(t.get("id") or uuid.uuid4().hex[:8]),
                title=t.get("title", "Task"),
                role=(canonical_role(t.get("role"))
                      if canonical_role(t.get("role")) in DEV_ROLES else "coder"),
                description=descrivi_task(t, goal),
                depends_on=list(t.get("depends_on") or []),
                metadata={k: t[k] for k in ("files", "verify") if t.get(k)},
            )
            for t in normalizzati
        ]
        # In modalita' interattiva l'utente ha guardato e accettato un piano.
        # Sostituirglielo senza chiedere e' peggio che non fargli approvare
        # niente: crederebbe che stia girando quello che ha letto.
        if self.mode == ExecutionMode.INTERACTIVE:
            yield {
                "type": "approval_required",
                "phase": "replan",
                "message": "Il piano e' stato rifatto. Procedere con quello nuovo?",
                "tasks": [
                    {"id": t.get("id"), "title": t.get("title"),
                     "role": t.get("role"), "depends_on": t.get("depends_on") or []}
                    for t in normalizzati
                ],
            }
            decisione = self._wait_for_approval("replan")
            if decisione != "approved":
                yield {"type": "status",
                       "text": f"Piano nuovo non accettato ({decisione}): "
                               "resta quello di prima."}
                yield {"type": "__piano_nuovo__", "ok": False}
                return

        conteggi = self.pipeline.replan(nuovi)
        self._sync_pipeline()
        yield {"type": "replanned", **conteggi,
               "tasks": [n.to_dict() for n in self.pipeline.nodes.values()]}
        yield {"type": "__piano_nuovo__", "ok": True}

    def _phase_verify(self, goal: str, model: Optional[str]) -> Generator:
        """Tester generates and runs tests; Reviewer reviews code."""
        # Tester
        context = self.context.build_context_for_role(
            "tester",
            upstream_outputs=self._monte("tester"),
        )
        prompt = (
            f"Verifica le modifiche fatte per l'obiettivo:\n\n**{goal}**\n\n"
            f"1. Leggi i file modificati\n"
            f"2. Genera test appropriati in tests/\n"
            f"3. Esegui i test con il terminale: python -m pytest tests/ -v\n"
            f"4. Riporta i risultati"
        )

        tester_output = []
        test_passed = True
        for event in self.role_engine.generate_with_role(
            "tester", prompt, context, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
        ):
            yield event
            if event.get("type") == "token":
                tester_output.append(event.get("token", ""))
            if event.get("type") == "tool_result":
                result = event.get("result", {})
                if result.get("tool") == "terminal":
                    rc = result.get("returncode", 0)
                    cmd = str(result.get("command") or "")
                    if rc != 0:
                        test_passed = False
                    else:
                        from core.harness.verification import parse_verification, looks_like_test_run
                        if looks_like_test_run(cmd):
                            v = parse_verification(cmd, rc, result.get("stdout", ""), result.get("stderr", ""))
                            if not v.is_valid:
                                test_passed = False

        self.context.record_role_output("tester", "".join(tester_output))

        # Reviewer
        if not self._cancelled():
            review_context = self.context.build_context_for_role(
                "reviewer",
                upstream_outputs=self._monte("reviewer"),
            )
            review_prompt = (
                f"Revisiona le modifiche fatte per l'obiettivo:\n\n**{goal}**\n\n"
                f"Leggi i file modificati, verifica qualità del codice, "
                f"e pulisci eventuale codice superfluo."
            )

            reviewer_output = []
            for event in self.role_engine.generate_with_role(
                "reviewer", review_prompt, review_context, model,
                should_cancel=self._cancelled,
                workspace_root=self.context.session.workspace_root,
                ledger=self.ledger,
                session_id=self.session_id,
            ):
                yield event
                if event.get("type") == "token":
                    reviewer_output.append(event.get("token", ""))
            self.context.record_role_output("reviewer", "".join(reviewer_output))

        # Feedback loop if tests failed
        if not test_passed and not self._cancelled():
            yield {"type": "status", "text": "🔄 Test falliti — avvio ciclo di correzione..."}
            yield from self._feedback_loop(goal, model, max_retries=2)

    def _phase_deliver(self, goal: str, model: Optional[str]) -> Generator:
        """DevOps commits changes and prepares for PR."""
        context = self.context.build_context_for_role("devops")
        changes_summary = self.context.files.get_summary()
        if not changes_summary and self.ledger and self.ledger.modified_files:
            changes_summary = "File modificati nel ledger:\n" + "\n".join(f"- {f}" for f in self.ledger.modified_files)

        prompt = (
            f"Finalizza il lavoro per l'obiettivo:\n\n**{goal}**\n\n"
            f"Modifiche nella sessione:\n{changes_summary}\n\n"
            f"1. Verifica lo stato con git_status\n"
            f"2. Aggiungi i file modificati con git_add\n"
            f"3. Crea un commit con messaggio Conventional Commits\n"
            f"4. Se possibile, fai push del branch"
        )

        for event in self.role_engine.generate_with_role(
            "devops", prompt, context, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
        ):
            yield event

    # -- Helpers -------------------------------------------------------------

    def _sync_pipeline(self) -> None:
        """Riversa il piano nel ledger, che e' cio' che viene salvato.

        Il piano viveva solo in memoria nel processo: un refresh della pagina
        lo perdeva insieme al suo avanzamento, e con esso il senso del
        pannello che lo mostra. Passando dal ledger, il piano finisce sia nel
        blocco di stato che il modello legge a ogni turno sia nel file della
        sessione su disco, senza un secondo percorso di persistenza da tenere
        allineato.
        """
        if not (self.ledger and self.pipeline):
            return
        try:
            self.ledger.set_pipeline(
                [n.to_dict() for n in self.pipeline.nodes.values()]
            )
        except Exception as exc:
            log.debug("[Orchestrator] piano non sincronizzato: %s", exc)

    def _build_pipeline_from_architect(self, tasks: List[Dict], goal: str) -> None:
        """Il piano dell'Architect diventa il grafo che viene eseguito.

        I task arrivano gia' in forma canonica da `core.harness.plan`: ruolo
        riconosciuto, dipendenze verificate, descrizione intera. Qui non si
        interpreta piu' niente — la mappa dei nomi di ruolo stava anche qui, e
        due copie della stessa mappa divergono.

        La descrizione da eseguire viene composta da `descrivi_task`, che
        rimette insieme descrizione, file indicati e verifica richiesta: il
        titolo da solo e' una riga, ed era tutto cio' che l'esecutore riceveva.
        """
        self.pipeline = TaskPipeline(goal=goal)
        for t in tasks:
            ruolo = canonical_role(t.get("role"))
            if ruolo not in DEV_ROLES:
                ruolo = "coder"
            node = TaskNode(
                id=str(t.get("id") or uuid.uuid4().hex[:8]),
                title=t.get("title", "Task"),
                role=ruolo,
                description=descrivi_task(t, goal),
                depends_on=list(t.get("depends_on") or []),
                metadata={k: t[k] for k in ("files", "verify") if t.get(k)},
            )
            self.pipeline.add_task(node)

    def _execute_task(self, task: TaskNode, model: Optional[str]) -> Generator:
        """Execute a single task with the appropriate role."""
        self.pipeline.mark_running(task.id)
        yield {
            "type": "task_start",
            "task_id": task.id,
            "title": task.title,
            "role": task.role,
        }

        context = self.context.build_context_for_role(
            task.role,
            task_description=task.description,
            upstream_outputs=self._monte(task.role),
        )

        output_tokens = []
        files_modified = []
        success = True

        # Il piano dichiara come si dimostra questo task. Non passarla
        # significa chiedere all'agente di inventarsi la prova: su una prova
        # dal vivo e' costato tre run per una voce che il file giusto lo aveva
        # gia' scritto.
        verifica = str((task.metadata or {}).get("verify") or "")
        for event in self.role_engine.generate_with_role(
            task.role, task.description, context, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
            verify_command=verifica,
            review_writes=getattr(self, "review_writes", False),
        ):
            yield event
            if event.get("type") == "token":
                output_tokens.append(event.get("token", ""))
            if event.get("type") == "tool_result":
                result = event.get("result", {})
                if result.get("tool") in ("write_file", "edit_file", "append_file") and result.get("success"):
                    percorso = result.get("path") or result.get("full_path", "")
                    if percorso:
                        files_modified.append(percorso)
                        self.context.files.track_change(
                            result.get("full_path", percorso),
                            None, None, role=task.role,
                        )
                if result.get("tool") == "terminal":
                    rc = result.get("returncode", 0)
                    cmd = str(result.get("command") or "")
                    if rc != 0:
                        success = False
                    else:
                        from core.harness.verification import parse_verification, looks_like_test_run
                        if looks_like_test_run(cmd):
                            v = parse_verification(cmd, rc, result.get("stdout", ""), result.get("stderr", ""))
                            if not v.is_valid:
                                success = False

        output = "".join(output_tokens)
        if success:
            self.pipeline.mark_done(task.id, output, files_modified)
            yield {"type": "task_done", "task_id": task.id, "title": task.title}
        else:
            self.pipeline.mark_failed(task.id, "Task execution had errors")
            yield {"type": "task_failed", "task_id": task.id, "title": task.title}

        # Emit pipeline status
        self._sync_pipeline()
        yield {
            "type": "pipeline_update",
            "tasks": [n.to_dict() for n in self.pipeline.nodes.values()],
            "progress": self.pipeline.progress_percent,
        }

    def _single_task_implement(self, goal: str, model: Optional[str]) -> Generator:
        """Fallback: implement as a single Coder task without a structured plan."""
        context = self.context.build_context_for_role(
            "coder",
            upstream_outputs=self._monte("coder"),
        )
        prompt = (
            f"Implementa le modifiche necessarie per questo obiettivo:\n\n"
            f"**{goal}**\n\n"
            f"Segui il piano dell'Architect. Leggi i file prima di modificarli."
        )

        for event in self.role_engine.generate_with_role(
            "coder", prompt, context, model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
        ):
            yield event

    def _feedback_loop(self, goal: str, model: Optional[str],
                       max_retries: int = 2) -> Generator:
        """Corregge dopo una verifica fallita, con lo stesso metro del resto.

        Questo ciclo esisteva prima dell'autocorrezione e faceva la stessa cosa
        in modo piu' grezzo: rilanciare il Coder sull'intero obiettivo con
        dentro la **prosa del Tester**, fino a due volte, senza bilancio.
        Convivendo con `autocorrezione` erano due sistemi che non si parlano:
        uno contava le proprie mosse, l'altro no, e insieme potevano spendere
        molto piu' del tetto che il primo credeva di far rispettare.

        Ora la diagnosi e il bilancio sono gli stessi. Cambia solo cio' su cui
        si applicano: qui non c'e' un task caduto ma una verifica rossa alla
        fine, e l'istruzione al Coder viene dai fatti del ledger invece che da
        quello che il Tester ha raccontato.
        """
        for tentativo in range(max_retries):
            if self._cancelled():
                return
            if not self.bilancio.puo_correggere():
                yield {"type": "status",
                       "text": "⚠️ Bilancio delle correzioni esaurito: mi fermo "
                               "invece di riprovare a vuoto."}
                return

            istantanea = {}
            try:
                istantanea = self.ledger.snapshot() if self.ledger else {}
            except Exception as exc:
                log.debug("[Orchestrator] ledger non leggibile: %s", exc)

            # Un portatore del guasto: non e' un task del piano, e' la verifica
            # finale. La diagnosi non ha bisogno di altro — guarda il ledger.
            class _Guasto:
                id = "verifica-finale"
                title = "la verifica finale dell'obiettivo"
                error = ""
                metadata: Dict[str, Any] = {}
                files_modified: List[str] = []

            diagnosi = autocorrezione.diagnostica(_Guasto(), istantanea,
                                                  self.bilancio)
            self.bilancio.spendi(autocorrezione.CORREGGI)
            yield {"type": "self_correction", "task_id": "verifica-finale",
                   "title": "verifica finale", **diagnosi.to_dict(),
                   "budget": self.bilancio.to_dict()}

            if diagnosi.livello == autocorrezione.RINUNCIA:
                return

            yield {"type": "status",
                   "text": f"🔄 Correzione {tentativo + 1}/{max_retries}: {diagnosi.motivo}"}

            contesto = self.context.build_context_for_role(
                "coder",
                upstream_outputs=self._monte("coder"),
            )
            for evento in self.role_engine.generate_with_role(
                "coder", diagnosi.istruzione, contesto, model,
                should_cancel=self._cancelled,
                workspace_root=self.context.session.workspace_root,
                ledger=self.ledger,
                session_id=self.session_id,
                verify_command=self._comando_di_verifica(),
                review_writes=self.review_writes,
            ):
                yield evento

            if self._cancelled():
                return
            superata = False
            for evento in self._riesegui_la_verifica(model):
                if evento.get("type") == "__verifica__":
                    superata = bool(evento.get("ok"))
                    continue
                yield evento
            if superata:
                yield {"type": "status", "text": "✅ Verifica superata dopo la correzione."}
                return

        yield {"type": "status",
               "text": "⚠️ Limite di correzioni raggiunto: la verifica resta rossa."}

    def _comando_di_verifica(self) -> str:
        """Il comando che il piano indica come prova, se ce n'e' uno.

        Il primo task che ne dichiara uno vale per tutti: e' la prova
        dell'obiettivo, non di un passo. Senza, l'agente deve trovarsela, e a
        volte non ci riesce.
        """
        if not self.pipeline:
            return ""
        for nodo in self.pipeline.nodes.values():
            comando = str((nodo.metadata or {}).get("verify") or "").strip()
            if comando:
                return comando
        return ""

    def _riesegui_la_verifica(self, model: Optional[str]) -> Generator:
        """Rifa' la prova e dice se e' verde. Emette `__verifica__`."""
        comando = self._comando_di_verifica() or "python -m pytest tests/ -v"
        yield {"type": "status", "text": f"🧪 Rieseguo `{comando}`"}

        superata = True
        visto = False
        for evento in self.role_engine.generate_with_role(
            "tester", f"Esegui `{comando}` e riporta l'esito senza cambiare nulla.",
            self.context.build_context_for_role("tester"), model,
            should_cancel=self._cancelled,
            workspace_root=self.context.session.workspace_root,
            ledger=self.ledger,
            session_id=self.session_id,
            verify_command=comando,
        ):
            yield evento
            if evento.get("type") != "tool_result":
                continue
            risultato = evento.get("result", {})
            if risultato.get("tool") != "terminal":
                continue
            visto = True
            rc = risultato.get("returncode", 0)
            cmd = str(risultato.get("command") or "")
            if rc != 0:
                superata = False
                continue
            from core.harness.verification import looks_like_test_run, parse_verification
            if looks_like_test_run(cmd):
                rapporto = parse_verification(cmd, rc, risultato.get("stdout", ""),
                                              risultato.get("stderr", ""))
                if not rapporto.is_valid:
                    superata = False

        # Nessun comando eseguito non e' una verifica superata: e' una verifica
        # che non ha avuto luogo, ed e' la distinzione che il cancello di
        # completamento fa da sempre.
        yield {"type": "__verifica__", "ok": superata and visto}

    def _get_role_output(self, role_id: str) -> str:
        """Get the latest output from a role."""
        outputs = self.context.role_outputs.get(role_id, [])
        return outputs[-1] if outputs else ""

    def _monte(self, ruolo: str) -> Dict[str, str]:
        """Cosa hanno prodotto i ruoli che vengono prima di questo.

        In una squadra il senso e' che chi viene dopo sappia cosa e' successo
        prima. Qui ogni ruolo riceveva soltanto l'output dell'Architetto: il
        Reviewer non vedeva cosa aveva trovato il Tester, il Tester non vedeva
        cosa aveva deciso il Coder. Cinque ruoli che lavoravano in parallelo
        fingendo una fila.

        L'ordine e' quello delle fasi, che e' anche l'ordine in cui il lavoro
        di uno diventa il materiale dell'altro. Si prende solo chi ha davvero
        prodotto qualcosa: una sezione vuota nel contesto occupa finestra e non
        dice niente.
        """
        ordine = [f["role"] for f in PHASES]
        try:
            fino_a = ordine.index(ruolo)
        except ValueError:
            fino_a = len(ordine)
        visti, monte = set(), {}
        for precedente in ordine[:fino_a]:
            if precedente in visti:
                continue
            visti.add(precedente)
            uscita = self._get_role_output(precedente)
            if uscita.strip():
                monte[precedente] = uscita
        return monte

    def _emit_final_report(self) -> Generator:
        """Il consuntivo dell'obiettivo, costruito dai fatti del ledger.

        Prima erano tre suggerimenti scritti a mano, identici a ogni run,
        accanto a un elenco di file. Non dicevano quali criteri fossero stati
        accettati ne' quale comando avesse dimostrato il lavoro — cioe' le due
        cose che si vogliono sapere alla fine.
        """
        report = {
            "type": "orchestrator_done",
            "goal": self.context.session.goal,
            "branch": self.context.session.branch_name,
            "files_modified": self.context.files.get_changed_paths(),
            "changes_summary": self.context.files.get_summary(),
        }

        if self.pipeline:
            report["pipeline"] = self.pipeline.summary()
            report["budget"] = self.bilancio.to_dict()

        try:
            from core.harness.resoconto import resoconto

            report["report"] = resoconto(
                self.ledger.snapshot() if self.ledger else {},
                obiettivo=self.context.session.goal,
                branch=self.context.session.branch_name or "",
                raggiunto=bool(self.pipeline and self.pipeline.is_complete
                               and not self.pipeline.has_failures),
            )
        except Exception as exc:
            log.debug("[Orchestrator] resoconto non prodotto: %s", exc)

        yield report
        yield {"type": "done", "full_text": "Workflow di sviluppo completato."}

    # -- State queries -------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Current orchestrator state."""
        return {
            "goal": self.context.session.goal,
            "phase": self.context.session.phase,
            "branch": self.context.session.branch_name,
            "mode": self.mode,
            "pipeline": self.pipeline.summary() if self.pipeline else None,
            "roles": self.role_engine.get_stats(),
        }
