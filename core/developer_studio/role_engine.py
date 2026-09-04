# ==============================================================================
# core/developer_studio/role_engine.py — Multi-Role AI on a Single Model
# Sigma Studio v8 — Developer Studio AI-Native IDE
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
from core.developer_studio.tool_policy import ToolPolicy

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
    max_turns=10,
    tools=(
        "list_dir", "glob", "read_file", "search_code", "pipeline",
        "git_status", "git_log",
    ),
    focus_areas=(
        "architettura del codice", "pattern di design", "dipendenze tra moduli",
        "decomposizione in task", "impatto delle modifiche",
    ),
    system_prompt="""Sei Σ-Architect, il Lead System Architect del Developer Studio.

## RUOLO
Analizzi la struttura del codice, identifichi dipendenze, pattern architetturali e
punti di impatto. Decompon obiettivi complessi in task atomici e ordinati.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Usa i tool per esplorare il workspace PRIMA di pianificare.
3. Ogni piano deve essere un elenco numerato di task con:
   - Titolo breve
   - File coinvolti (percorsi reali, verificati con list_dir/read_file)
   - Dipendenze da altri task
   - Ruolo consigliato (coder, tester, reviewer, devops)
4. NON scrivere codice: il tuo output è il PIANO, non l'implementazione.
5. Segnala rischi, breaking changes e dipendenze circolari.
6. Usa il tool `pipeline` per registrare il piano come DAG di task.

## OUTPUT ATTESO
Un piano strutturato con task, dipendenze e assegnazione ruoli, pronto per
essere eseguito dall'orchestrator.
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
    max_turns=26,
    tools=(
        "read_file", "edit_file", "write_file", "search_code", "terminal",
        "list_dir", "glob", "delete",
    ),
    focus_areas=(
        "implementazione corretta", "gestione errori", "performance",
        "leggibilità del codice", "aderenza al piano",
    ),
    system_prompt="""Sei Σ-Coder, lo sviluppatore esperto del Developer Studio.

## RUOLO
Implementi codice seguendo rigorosamente il piano dell'Architect. Scrivi codice
Python e JavaScript/React di qualità professionale.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Leggi SEMPRE i file esistenti con read_file PRIMA di modificarli, usando
   offset/limit per arrivare fino in fondo se il file e lungo.
3. Per modificare un file esistente usa `edit_file` (sostituzione esatta del
   frammento). Usa `write_file` SOLO per creare file nuovi: riscrivere per
   intero un file lungo esaurisce il budget di generazione e ne perde dei pezzi.
4. Preserva TUTTI i commenti e docstring esistenti non correlati alle tue modifiche.
5. Gestisci sempre gli errori: try/except con logging, validazione input.
6. Segui le convenzioni del progetto: import ordering, naming, formatting.
7. Se il task richiede un file nuovo, crea anche le directory parent.
8. NON toccare file che non sono nel piano dell'Architect.

## STANDARD CODICE
- Python: type hints, docstring Google-style, f-string, pathlib per i percorsi
- JavaScript/React: hooks, componenti funzionali, destructuring props
- Entrambi: variabili in inglese, commenti in italiano dove necessario
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
        "read_file", "search_code", "write_file", "list_dir",
    ),
    focus_areas=(
        "code quality", "dead code", "import inutilizzati", "duplicazione",
        "sicurezza", "performance", "leggibilità",
    ),
    system_prompt="""Sei Σ-Reviewer, il revisore del codice del Developer Studio.

## RUOLO
Revisioni il codice prodotto dal Coder, identificando problemi, codice morto,
import inutilizzati, duplicazioni, e suggerendo miglioramenti.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Leggi ogni file modificato con read_file per una revisione completa.
3. Il tuo output è un report strutturato con:
   - ✅ Aspetti positivi
   - ⚠️ Avvertimenti (non bloccanti)
   - ❌ Problemi critici (bloccanti)
   - 🧹 Pulizia suggerita (dead code, import, formattazione)
4. Per problemi critici, indica esattamente COSA correggere e DOVE.
5. Se trovi codice superfluo, applica la pulizia direttamente con write_file.
6. NON riscrivere codice funzionante solo per gusto estetico.

## CRITERIO DI PASS/FAIL
- PASS: nessun problema critico, codice coerente con l'architettura
- FAIL: problemi che impediscono il corretto funzionamento o la manutenzione
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
    max_turns=18,
    tools=(
        "read_file", "write_file", "terminal", "search_code",
        "list_dir", "run_tests",
    ),
    focus_areas=(
        "copertura dei test", "edge cases", "regression",
        "test di integrazione", "mock e fixture",
    ),
    system_prompt="""Sei Σ-Tester, l'ingegnere dei test del Developer Studio.

## RUOLO
Generi ed esegui test per il codice prodotto dal Coder, verificando correttezza,
edge cases e assenza di regressioni.

## REGOLE
1. Rispondi SEMPRE in italiano.
2. Leggi il codice da testare con read_file PRIMA di scrivere i test.
3. Scrivi test pytest con naming chiaro: test_<cosa>_<scenario>.
4. Ogni test deve avere: arrange (setup), act (esecuzione), assert (verifica).
5. Usa mock/patch per isolare dipendenze esterne (filesystem, rete, modello AI).
6. Esegui i test con il tool terminal: `python -m pytest <file> -v`
7. Se i test falliscono, riporta l'output esatto dell'errore.
8. Posiziona i test in `tests/` con il naming `test_<modulo>.py`.

## OUTPUT ATTESO
- File di test creato/aggiornato
- Risultato dell'esecuzione (pass/fail + output)
- Copertura raggiunta (se disponibile)
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

# All roles indexed by ID
DEV_ROLES: Dict[str, DevRole] = {
    r.id: r for r in [
        ROLE_ARCHITECT, ROLE_CODER, ROLE_REVIEWER, ROLE_TESTER, ROLE_DEVOPS,
    ]
}


# ---------------------------------------------------------------------------
# Role Engine
# ---------------------------------------------------------------------------

class RoleEngine:
    """Manages switching between development roles on a single loaded model.

    Instead of loading different models for each role, the engine:
    1. Keeps the same model in memory
    2. Changes the system prompt to the role's specialised prompt
    3. Adjusts sampling parameters (temperature, top_p, top_k)
    4. Restricts the available tool set per role
    5. Reuses the KV-cache prefix for the shared project context
    """

    def __init__(self):
        self.roles = dict(DEV_ROLES)
        self.active_role_id: Optional[str] = None
        self._generation_count: Dict[str, int] = {r: 0 for r in DEV_ROLES}

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
        from core.developer_studio.admin_agent import (
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

        yield {
            "type": "role_switch",
            "role_id": role_id,
            "role_name": role.name,
            "role_icon": role.icon,
            "max_turns": int(max_turns or role.max_turns),
        }

        # Delegate to the existing admin agent loop but with our role's params
        for event in stream_admin_agent_turn(
            messages=messages,
            workspace_root=workspace_root,
            model_name=model_name,
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
