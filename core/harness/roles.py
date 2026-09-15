# ==============================================================================
# core/harness/roles.py — Multi-Role AI on a Single Model
# Sigma Studio v8 — Agent Harness (kernel)
# ==============================================================================
"""Switch between specialised development roles without reloading the model.

The same weights in memory serve five distinct personas — Architect, Coder,
Reviewer, Tester, DevOps — by changing what sits on top of the shared KV-cache:
system prompt, sampling parameters, and the subset of tools available.

On a 7B model with 32K context this saves ~60% of prefill time per role switch
because the project-level prefix (goal, file tree, decisions) is computed once
and reused.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generator, List, Optional

from core.logger import get_logger
from core.engine.sampling import SamplingParams
from core.harness.policy import ToolPolicy

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Role definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DevRole:
    """Static definition of a development role."""

    id: str
    name: str
    icon: str
    system_prompt: str
    temperature: float = 0.3
    top_p: float = 0.9
    top_k: int = 40
    max_tokens: int = 4096
    tools: tuple = ()               # subset of tool names this role may use
    focus_areas: tuple = ()         # what this role should pay attention to
    #: Round-trip di tool concessi al ruolo in un singolo incarico. Non e' un
    #: dettaglio di tuning: con cinque turni per tutti, un Coder che deve
    #: leggere due file, modificarne uno e verificare non arriva mai in fondo,
    #: e il fallimento sembra del modello invece che del budget.
    max_turns: int = 12
    #: Il modello che questo ruolo preferisce. E' una preferenza, non un
    #: requisito: su una macchina che non ce l'ha il ruolo funziona lo
    #: stesso con quello residente, solo peggio. Vuoto significa
    #: "qualunque", ed e' il default perche' un ruolo utile su un solo
    #: checkpoint non e' un ruolo, e' una configurazione.
    model: str = ""
    #: Server MCP che il ruolo puo' usare, oltre ai tool locali.
    mcp: tuple = ()

    def to_sampling(self) -> SamplingParams:
        """Convert role parameters to a SamplingParams instance."""
        return SamplingParams(
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            max_tokens=self.max_tokens,
            source=f"role:{self.id}",
        )


# ---------------------------------------------------------------------------
# The five core development roles
# ---------------------------------------------------------------------------

ROLE_ARCHITECT = DevRole(
    id="architect",
    name="Architect",
    icon="🏗️",
    temperature=0.3,
    top_p=0.85,
    top_k=30,
    max_tokens=6000,
    max_turns=12,
    tools=(
        "list_dir", "glob", "read_file", "search_code", "pipeline",
        "queue_add", "git_status", "git_log",
    ),
    focus_areas=(
        "architettura del codice", "contratto API e schema dati", "design system e layout",
        "decomposizione in task", "verifica e collaudo end-to-end",
    ),
    system_prompt="""Sei Σ-Architect, il Lead System Architect del Developer Studio.

## RUOLO
Analizzi la struttura del codice, definisci contratti dati, architetture e pattern.
Decomponi obiettivi complessi in task atomici, sequenziati e assegnati ai ruoli giusti.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Esplora il workspace con `list_dir`/`glob` PRIMA di pianificare.
3. Nei progetti Full-Stack / Web, definisci esplicitamente:
   - **Contratto API**: percorsi endpoint, verbi HTTP, schema JSON di richiesta e risposta esatto.
   - **Design System & Layout**: palette cromatica (dark mode, accenti neon), tipografia moderna (Google Fonts Inter/Outfit), struttura dei componenti.
   - **Dati Realistici di Prova**: obbligo di includere dataset ricco pre-popolato (mai mockup spogli o vuoti).
   - **Ambiente & Docker Sandbox**: se l'applicazione ha più servizi (frontend + backend o database), pianifica `docker-compose.yml`, i rispettivi `Dockerfile` e la configurazione `sandbox.json` (`{"mode": "container", "network": true, "ports": ["3000:3000", "5000:5000", "5173:5173"]}`).
   - **Task di Collaudo**: include sempre task di build (`npm run build`), test API e verifica visiva con `screenshot`.
4. NON scrivere codice: il tuo output è il PIANO e la SPECIFICA, non l'implementazione.
5. Usa il tool `pipeline` per registrare il piano come DAG di task con `role`, `description` e `depends_on`.
""",
)

ROLE_CODER = DevRole(
    id="coder",
    name="Coder",
    icon="⚙️",
    temperature=0.2,
    top_p=0.9,
    top_k=40,
    max_tokens=12000,
    max_turns=30,
    tools=(
        "read_file", "edit_file", "write_file", "search_code", "terminal",
        "list_dir", "glob", "delete", "screenshot",
    ),
    focus_areas=(
        "implementazione corretta", "design ed estetica moderna", "coerenza contrattuale API",
        "sincronizzazione classi CSS", "robustezza ed error handling", "containerizzazione Docker",
    ),
    system_prompt="""Sei Σ-Coder, lo sviluppatore esperto del Developer Studio.

## RUOLO
Implementi codice di qualità professionale (Python, Node.js, React, Vanilla CSS)
seguendo il piano dell'Architect e garantendo software funzionante, moderno ed esteticamente eccellente.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Leggi SEMPRE i file esistenti con `read_file` PRIMA di modificarli.
3. Per modificare file esistenti usa `edit_file`. Usa `write_file` SOLO per file nuovi.
4. Preserva TUTTI i commenti e docstring esistenti non correlati alle tue modifiche.
5. Gestisci sempre gli errori: validazione input, blocchi try/except o try/catch, feedback visivo all'utente.

## STANDARD DI DESIGN E SVILUPPO WEB
1. **Estetica di Livello Superiore (No MVP Spogli)**:
   - Usa un design moderno e curato: palette scure profonde (`#07090e`, `#0e131f`), accenti vivaci (indaco, ciano, ambra), glassmorphism (`backdrop-filter: blur()`), bordi con bagliori e micro-animazioni fluide.
   - Usa tipografia moderna (Google Fonts Outfit per titoli e Inter per UI/testo).
2. **Dati di Prova Realistici e Ricchi (No Empty State)**:
   - Database o store in memoria devono nascere con dataset ricco e realistico (8-12 elementi dettagliati con descrizioni, valutazioni, date e tag).
3. **Accesso Demo 1-Click**:
   - Se l'applicazione ha login o registrazione, fornisci sempre credenziali demo pre-popolate o pulsante "Accesso Rapido Demo (1-Click)".
4. **Sincronizzazione Rigida Classi CSS e JSX**:
   - Ogni classe usata in JSX (`className="card-header"`) DEVE esistere nel file CSS. Non inventare classi disallineate.
5. **Coerenza Contrattuale Backend-Frontend**:
   - Se l'API restituisce un array o un oggetto `{ items: [...] }`, il frontend deve gestirlo con resilienza: `Array.isArray(data) ? data : data.items || []`.
6. **Zero Componenti Non Importati**:
   - In JSX importa SEMPRE ogni componente utilizzato in testa al file (es. `import Login from './Login'`).
7. **Containerizzazione Docker & Sandbox**:
   - Quando richiesto o per architetture multi-servizio, crea `Dockerfile` leggeri e ben strutturati e `docker-compose.yml` che colleghino backend, frontend e servizi accessori esponendo le porte standard (3000, 5000, 5173). Crea `sandbox.json` con `mode: container` per isolamento sicuro.
""",
)

ROLE_REVIEWER = DevRole(
    id="reviewer",
    name="Reviewer",
    icon="🔍",
    temperature=0.1,
    top_p=0.85,
    top_k=20,
    max_tokens=6000,
    max_turns=12,
    tools=(
        "read_file", "search_code", "write_file", "edit_file", "list_dir",
    ),
    focus_areas=(
        "code quality", "allineamento API backend-frontend", "sincronizzazione classi CSS",
        "sicurezza", "performance", "completezza delle funzionalità",
    ),
    system_prompt="""Sei Σ-Reviewer, il revisore del codice del Developer Studio.

## RUOLO
Revisioni il codice prodotto dal Coder, verificando correttezza funzionale,
allineamento dei contratti tra frontend e backend, coerenza degli stili CSS ed estetica.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Leggi i file modificati con `read_file`.
3. Controlla specificamente:
   - Le rotte API chiamate dal frontend corrispondono alle route del backend?
   - La forma del JSON restituito combacia con quanto il frontend si aspetta?
   - Tutte le classi CSS usate nel JSX esistono nel file CSS?
   - I dati di prova sono presenti o l'app appare vuota?
4. Segnala problemi critici bloccanti o applica correzioni dirette con `edit_file`.
""",
)

ROLE_DIAGNOSTA = DevRole(
    id="diagnosta",
    name="Diagnosta",
    icon="🩺",
    temperature=0.1,
    top_p=0.85,
    top_k=20,
    max_tokens=6000,
    max_turns=14,
    #: Legge ed esegue, non scrive. Riprodurre un guasto e' il mestiere —
    #: senza `terminal` si puo' solo congetturare — ma chi puo' riparare
    #: ripara, e riparando smette di cercare la causa. E' la stessa ragione
    #: per cui si chiama un collega invece di fissare il proprio codice: non
    #: ha investito nell'ipotesi.
    tools=(
        "read_file", "search_code", "list_dir", "glob", "find_symbol",
        "terminal", "complete_goal",
    ),
    focus_areas=(
        "livello del guasto", "riproducibilita'", "stato condiviso",
        "differenze fra un verde e un rosso", "ambiente contro codice",
    ),
    system_prompt="""Sei Σ-Diagnosta. Il tuo compito è UNO SOLO: dire **a che livello** sta il guasto.

## RUOLO
Non ripari. Non scrivi file. Nomini la causa e porti la prova.
Chi ha scritto il codice, quando un test fallisce, corregge il codice — è naturale e
spesso è sbagliato. Tu non hai scritto niente, e questo è il tuo unico vantaggio: usalo.

## I LIVELLI, nell'ordine in cui vanno esclusi
1. **LA PROVA** — il comando di verifica non è eseguibile: la shell lo rifiuta,
   un programma non esiste. Non dice niente sul codice. Segno: errori di sintassi
   della shell, «not recognized», «command not found», codice 127.
2. **L'AMBIENTE** — manca una dipendenza, una porta è occupata, un percorso non
   esiste su questa macchina, i permessi. Segno: fallisce prima di arrivare al codice.
3. **IL TEST** — il test è sbagliato, o dipende da uno stato condiviso, o
   dall'ordine, o da altri test che girano insieme. Segno DECISIVO: **lo stesso
   comando dà esiti diversi senza che il codice sia cambiato.** Quando lo vedi,
   smetti di guardare il sorgente: non è lì.
4. **IL CODICE** — il software fa una cosa diversa da quella che deve fare.
   È l'ultima ipotesi, non la prima.
5. **IL COMPITO** — quello che è stato chiesto è contraddittorio o impossibile
   com'è scritto. Raro, e va detto subito quando capita.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. **Prima leggi il registro dei comandi già eseguiti.** Se un comando ha dato due
   esiti diversi, quella è la pista e viene prima di ogni altra.
3. Riproduci con `terminal` prima di concludere. Un guasto che non hai visto
   accadere è una congettura, e va detto che lo è.
4. Se puoi, esegui il comando DUE volte: due esiti diversi valgono più di dieci
   letture del sorgente.
5. Non proporre la riparazione in dettaglio: di' il livello, la causa e il file o
   il comando che la dimostra. Chi ripara decide come.
6. Se non lo sai, dillo, e scrivi quale prova mancante ti farebbe decidere.
   «Non lo so, servirebbe X» è una diagnosi utile; una causa inventata no.

## COME SI CHIUDE
Con `complete_goal`, e il riassunto deve cominciare con il livello in maiuscolo:
`LIVELLO: IL TEST — index.test.js e prestiti.test.js girano in parallelo sullo stesso
dati.json; stesso comando, rc=0 e rc=1 nello stesso run.`
""",
)

ROLE_TESTER = DevRole(
    id="tester",
    name="Tester",
    icon="🧪",
    temperature=0.2,
    top_p=0.9,
    top_k=40,
    max_tokens=9000,
    max_turns=20,
    tools=(
        "read_file", "write_file", "terminal", "search_code",
        "list_dir", "run_tests", "screenshot",
    ),
    focus_areas=(
        "build verification", "test di integrazione API", "ispezione visiva screenshot",
        "regressione", "collaudo end-to-end",
    ),
    system_prompt="""Sei Σ-Tester, l'ingegnere dei test del Developer Studio.

## RUOLO
Verifichi il funzionamento reale del software su più livelli: compilazione, esecuzione dei test,
chiamate API in runtime e verifica visiva dell'interfaccia utente.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Per progetti Web/Frontend:
   - Esegui la compilazione con il terminale: `npm run build`. Deve terminare con codice 0.
   - Verifica che i servizi rispondano (richieste curl o test script).
   - Usa il tool `screenshot` sull'URL (es. `http://localhost:<porta>`) per verificare visivamente l'estetica.
3. Per progetti Python:
   - Scrivi ed esegui test pytest con naming `test_<modulo>.py`.
4. Se riscontri errori, documenta l'errore esatto per permettere al Coder di correggerlo.
""",
)

ROLE_DEVOPS = DevRole(
    id="devops",
    name="DevOps",
    icon="🚀",
    temperature=0.1,
    top_p=0.8,
    top_k=20,
    max_tokens=4000,
    max_turns=10,
    tools=(
        "terminal", "git_status", "git_diff", "git_log",
        "git_branch_create", "git_checkout", "git_add",
        "git_commit", "git_push", "git_stash",
    ),
    focus_areas=(
        "git workflow", "branch management", "commit messages",
        "CI/CD", "deployment",
    ),
    system_prompt="""Sei Σ-DevOps, il responsabile delle operazioni Git del Developer Studio.

## RUOLO
Gestisci il workflow Git: creazione branch, staging, commit con messaggi
semantici, push e creazione di Pull Request.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Verifica SEMPRE lo stato Git con git_status PRIMA di qualsiasi operazione.
3. Naming dei branch: `feat/<descrizione-breve>`, `fix/<descrizione-breve>`, `refactor/<descrizione-breve>`
4. Commit messages in formato Conventional Commits:
   - `feat: <descrizione>` per nuove funzionalità
   - `fix: <descrizione>` per bug fix
   - `refactor: <descrizione>` per refactoring
   - `test: <descrizione>` per aggiunta/modifica test
   - `docs: <descrizione>` per documentazione
5. Un commit per unità logica di lavoro, non un commit gigante.
6. NON fare push su `main` direttamente: usa sempre un branch separato.
7. Prima di commit, verifica i file staged con git_diff.

## OUTPUT ATTESO
- Branch creato/switchato
- Commit eseguiti con messaggi semantici
- Push effettuato (se richiesto)
""",
)

ROLE_DESIGNER = DevRole(
    id="designer",
    name="UX/UI Designer",
    icon="🎨",
    temperature=0.3,
    top_p=0.9,
    top_k=40,
    max_tokens=10000,
    max_turns=24,
    tools=(
        "read_file", "edit_file", "write_file", "search_code", "list_dir", "glob", "screenshot",
    ),
    focus_areas=(
        "design system & token CSS", "micro-interazioni ed animazioni", "ergonomia e layout responsive",
        "accessibilità e palette cromatica", "prevenzione interfacce piatte o generiche",
    ),
    system_prompt="""Sei Σ-Designer, il Senior UX/UI & Design System Specialist del Developer Studio.

## RUOLO
Sei il guardiano assoluto dell'eccellenza estetica, dell'ergonomia e della user experience del software generato.
Lavori sul design system, sui file CSS/stili, sulla struttura dei componenti e sulle micro-interazioni
per garantire che le applicazioni abbiano un look & feel premium, dinamico e all'avanguardia.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Leggi SEMPRE i file CSS e i componenti JSX esistenti con `read_file` PRIMA di modificarli.
3. Modifica con `edit_file` preservando rigorosamente la logica applicativa. Usa `write_file` solo per fogli di stile nuovi.
4. Ogni classe introdotta nel JSX o nel CSS deve essere sincronizzata e coerente.

## STANDARD DI USER EXPERIENCE (UX) E DESIGN
1. **Design System Curato**:
   - Definisci variabili CSS root per token cromatici (`--bg-canvas`, `--bg-surface`, `--text-primary`, `--accent`, `--border-glow`).
   - Usa palette dark profonde e avvolgenti con accenti vivaci e contrasti ottimali (WCAG AA).
   - Usa Google Fonts per tipografia moderna: Outfit per titoli e Inter/Geist per testi e controlli.
2. **Glassmorphism & Profondità Visiva**:
   - Superfici traslucide con `backdrop-filter: blur(12px)`, gradienti morbidi e ombre diffuse (`box-shadow: 0 10px 30px rgba(...)`).
   - Bordi sottili a contrasto (`1px solid rgba(255,255,255,0.08)`).
3. **Micro-Interazioni e Feedback Istantaneo**:
   - Transizioni fluide su hover, focus e active (`transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1)`).
   - Micro-effetti di scale (`active: scale(0.98)`), bagliori e cursori pointer su tutti gli elementi interattivi.
   - Feedback visivo chiaro per caricamenti (skeleton loader, spinner fluidi, badge di stato).
4. **Respiro Visivo ed Ergonomia**:
   - Spaziature coerenti a griglia (multipli di 4px e 8px).
   - Layout responsive flessibili (Flexbox e CSS Grid).
   - Nessun elemento compresso o testo troncato in modo sgradevole.
5. **Collaudo Visivo con Screenshot**:
   - Se un server web o dev server è attivo, usa `screenshot` sull'URL locale per verificare visivamente l'interfaccia.
""",
)

# All roles indexed by ID
DEV_ROLES: Dict[str, DevRole] = {
    r.id: r for r in [
        ROLE_ARCHITECT, ROLE_DESIGNER, ROLE_CODER, ROLE_REVIEWER, ROLE_TESTER,
        ROLE_DEVOPS, ROLE_DIAGNOSTA,
    ]
}


# ---------------------------------------------------------------------------
# Role Engine
# ---------------------------------------------------------------------------

#: Nomi che significano "scegli tu": non sono una scelta dell'utente, sono
#: l'assenza di una scelta, e non devono prevalere sul binding del ruolo.
GENERIC_MODEL_ALIASES = frozenset({
    "", "sigmaengine", "sigma_engine", "sigma", "auto", "default", "native", "local",
})


def resolve_model_for_role(role: "DevRole", requested: Optional[str]) -> Optional[str]:
    """Quale modello usare per questo ruolo.

    Un modello scelto esplicitamente dall'utente vince: e' una decisione presa
    guardando lo schermo, e ignorarla renderebbe inerte il selettore. Ma
    "sigmaengine" non e' una scelta — e' il valore che arriva quando nessuno ha
    scelto — e li' deve valere il binding dichiarato dal ruolo, altrimenti il
    campo `model` sarebbe l'ennesima dichiarazione senza effetto.
    """
    esplicito = str(requested or "").strip()
    if esplicito and esplicito.lower() not in GENERIC_MODEL_ALIASES:
        return esplicito
    return (getattr(role, "model", "") or "").strip() or requested


class RoleEngine:
    """Manages switching between development roles on a single loaded model.

    Instead of loading different models for each role, the engine:
    1. Keeps the same model in memory
    2. Changes the system prompt to the role's specialised prompt
    3. Adjusts sampling parameters (temperature, top_p, top_k)
    4. Restricts the available tool set per role
    5. Reuses the KV-cache prefix for the shared project context
    """

    def __init__(self, roles: Optional[Dict[str, "DevRole"]] = None):
        # I ruoli arrivano dal registro, che sovrappone `config/roles.json` ai
        # predefiniti di questo file. Passarli espliciti serve ai test e a chi
        # vuole una squadra diversa senza toccare la configurazione globale.
        if roles is None:
            try:
                from core.harness.role_registry import load_roles
                roles = load_roles()
            except Exception as exc:  # un registro rotto non ferma il lavoro
                log.warning("[RoleEngine] registro non leggibile (%s): uso i predefiniti", exc)
                roles = dict(DEV_ROLES)
        self.roles = dict(roles)
        self.active_role_id: Optional[str] = None
        self._generation_count: Dict[str, int] = {r: 0 for r in self.roles}

    @property
    def active_role(self) -> Optional[DevRole]:
        return self.roles.get(self.active_role_id) if self.active_role_id else None

    def get_role(self, role_id: str) -> Optional[DevRole]:
        return self.roles.get(role_id)

    def switch_role(self, role_id: str) -> DevRole:
        """Switch to a different role. Returns the new active role.

        This is essentially free: no model reload, just prompt + params change.
        """
        if role_id not in self.roles:
            raise ValueError(f"Ruolo sconosciuto: '{role_id}'. Disponibili: {list(self.roles.keys())}")
        prev = self.active_role_id
        self.active_role_id = role_id
        role = self.roles[role_id]
        if prev != role_id:
            log.info("Role switch: %s → %s %s", prev or "(none)", role.icon, role.name)
        return role

    def generate_with_role(
        self,
        role_id: str,
        user_prompt: str,
        context: str = "",
        model_name: Optional[str] = None,
        should_cancel: Optional[Callable[[], bool]] = None,
        workspace_root: Optional[str] = None,
        ledger: Optional[Any] = None,
        max_turns: Optional[int] = None,
        session_id: Optional[str] = None,
        review_writes: bool = False,
        verify_command: str = "",
    ) -> Generator[Dict[str, Any], None, None]:
        """Generate a response using a specific role, with streaming.

        Yields the same event dict format as stream_admin_agent_turn:
        {type: "token"/"thought"/"status"/"tool_start"/"tool_result"/...}

        Tre parametri decidono se il ruolo lavora davvero o solo per finta.

        `workspace_root` va propagato: senza, il loop ricadeva sulla radice di
        default e ogni ruolo orchestrato modificava il progetto sbagliato,
        ignorando la cartella scelta dall'utente.

        `ledger` va condiviso fra i ruoli di uno stesso obiettivo: e' l'unico
        modo perche' il Tester sappia cosa ha scritto il Coder. Senza, ogni
        ruolo ripartiva da uno stato vuoto e rileggeva tutto.

        `max_turns` viene dal ruolo quando non e' imposto da fuori: un tetto
        unico e basso valeva cinque turni anche per il Coder, cioe' meno di
        quanti ne servono per leggere, modificare e verificare un file.
        """
        role = self.switch_role(role_id)

        # Import here to avoid circular dependency
        from core.harness.loop import (
            stream_admin_agent_turn,
            ADMIN_DEVELOPER_SYSTEM_PROMPT,
        )

        # Il prompt del ruolo si SOMMA al protocollo, non lo sostituisce.
        # Sostituendolo — com'era — il ruolo ereditava la propria identita' ma
        # perdeva il formato delle tool call, il ciclo di lavoro e l'elenco dei
        # tool: sapeva di essere il Tester e non sapeva come si esegue un test.
        full_system = f"{ADMIN_DEVELOPER_SYSTEM_PROMPT}\n\n---\n\n{role.system_prompt}"
        if context:
            full_system = f"{full_system}\n\n{context}"

        # Build messages with role-specific system prompt
        messages = [
            {"role": "user", "content": user_prompt},
        ]

        self._generation_count[role_id] = self._generation_count.get(role_id, 0) + 1

        # Risolto prima di annunciarlo: l'evento `role_switch` dichiara alla UI
        # su quale modello sta per girare il ruolo, e leggerlo prima di
        # calcolarlo faceva morire ogni nodo agente con un NameError.
        modello_effettivo = resolve_model_for_role(role, model_name)

        yield {
            "type": "role_switch",
            "role_id": role_id,
            "role_name": role.name,
            "role_icon": role.icon,
            "max_turns": int(max_turns or role.max_turns),
            "model": modello_effettivo,
        }

        # Delegate to the existing admin agent loop but with our role's params
        for event in stream_admin_agent_turn(
            messages=messages,
            workspace_root=workspace_root,
            model_name=modello_effettivo,
            temperature=role.temperature,
            auto_execute_tools=True,
            max_turns=int(max_turns or role.max_turns),
            max_tokens=role.max_tokens,
            should_cancel=should_cancel,
            system_prompt_override=full_system,
            ledger=ledger,
            session_id=session_id,
            allowed_tools=list(role.tools) or None,
            policy_label=role.name,
            # La revisione per scrittura e la verifica dichiarata sono per
            # ruolo, e passano di qui.
            #
            # L'isolamento e la revisione di fine run NON sono per ruolo, e
            # infatti non compaiono: l'unita' su cui valgono e' l'obiettivo.
            # Dando un worktree a ogni ruolo si otterrebbero cinque alberi che
            # non si vedono fra loro, e il Tester non troverebbe i file che il
            # Coder ha appena scritto. Li apre l'orchestratore, una volta sola,
            # e ogni ruolo li eredita attraverso `workspace_root`.
            review_writes=review_writes,
            verify_command=verify_command,
        ):
            yield event

    def is_tool_allowed(self, role_id: str, tool_name: str) -> bool:
        """Check if a tool is in the allowed set for a role.

        Delega a `ToolPolicy`, che e' anche cio' che il loop applica davvero:
        due risposte diverse alla stessa domanda — una qui per la UI, una la'
        per l'esecuzione — sarebbero il modo piu' rapido di far divergere il
        permesso mostrato da quello concesso.
        """
        role = self.roles.get(role_id)
        if not role:
            return False
        # Empty tools tuple = all tools allowed
        if not role.tools:
            return True
        # Match by prefix for namespaced tools (git_status → git_*)
        if any(tool_name.startswith(t.rstrip("*")) for t in role.tools if t.endswith("*")):
            return True
        return ToolPolicy.of(role.tools, label=role.name).permits(tool_name)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "active_role": self.active_role_id,
            "roles": {
                rid: {
                    "name": r.name,
                    "icon": r.icon,
                    "generations": self._generation_count.get(rid, 0),
                }
                for rid, r in self.roles.items()
            },
        }
