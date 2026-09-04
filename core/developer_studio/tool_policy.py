# ==============================================================================
# core/developer_studio/tool_policy.py — Quali tool puo' usare chi
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Il permesso d'uso dei tool, in un posto solo.

I ruoli dichiarano da sempre il sottoinsieme di tool che gli compete
(`DevRole.tools`), ma nessuno lo verificava: il Reviewer poteva scrivere file
esattamente come il Coder, e la dichiarazione era decorazione. Questo modulo la
rende effettiva.

Due nozioni servono per farlo senza rompere nulla:

**Nome canonico.** L'agente accetta gli alias (`read`, `write`, `shell`, `rm`,
`grep`...) perche' un modello locale li produce comunque; una policy che
confronta stringhe grezze verrebbe aggirata dal primo sinonimo. Qui ogni alias
viene ricondotto al suo nome canonico prima del confronto.

**Tool di controllo.** `pipeline` e `complete_goal` non toccano il workspace:
registrano il piano e chiudono il lavoro. Vietarli a un ruolo significherebbe
renderlo incapace di dichiarare finito cio' che ha fatto, quindi restano
sempre permessi a chiunque.
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple

#: alias -> nome canonico. Ricalca i gruppi accettati da `execute_admin_tool`:
#: se li' se ne aggiunge uno, va aggiunto anche qui, altrimenti sfugge alla
#: policy pur essendo eseguibile.
ALIASES: Dict[str, str] = {
    # lettura
    "read": "read_file",
    "read_file": "read_file",
    # scrittura integrale
    "write": "write_file",
    "save_file": "write_file",
    "write_file": "write_file",
    # modifica puntuale
    "edit": "edit_file",
    "replace_in_file": "edit_file",
    "str_replace": "edit_file",
    "edit_file": "edit_file",
    # aggiunta in coda
    "append": "append_file",
    "add_to_file": "append_file",
    "append_file": "append_file",
    # esecuzione
    "shell": "terminal",
    "exec": "terminal",
    "command": "terminal",
    "terminal": "terminal",
    # esplorazione
    "ls": "list_dir",
    "list_directory": "list_dir",
    "list_dir": "list_dir",
    "find_files": "glob",
    "glob_files": "glob",
    "glob": "glob",
    "grep": "search_code",
    "search_code": "search_code",
    # rimozione
    "rm": "delete",
    "delete_file": "delete",
    "remove_file": "delete",
    "delete": "delete",
    # varie
    "restore_file": "restore_file",
    "visual_check": "screenshot",
    "guarda": "screenshot",
    "screenshot": "screenshot",
    # controllo
    "tasks": "pipeline",
    "set_tasks": "pipeline",
    "update_pipeline": "pipeline",
    "pipeline": "pipeline",
    "finish_task": "complete_goal",
    "task_complete": "complete_goal",
    "complete_goal": "complete_goal",
}

#: Non toccano il workspace: registrano il piano e chiudono il lavoro.
CONTROL_TOOLS: Set[str] = {"pipeline", "complete_goal"}


def canonical(tool_name: str) -> str:
    """Il nome canonico di un tool, o il nome stesso se non e' un alias noto.

    I tool MCP (`git_commit`, `run_tests`, `lint_python`...) non hanno alias e
    passano di qui immutati, che e' esattamente il comportamento voluto: la
    policy li nomina con lo stesso nome con cui li nomina il bridge.
    """
    return ALIASES.get(str(tool_name or "").strip().lower(), str(tool_name or "").strip().lower())


@dataclass(frozen=True)
class ToolPolicy:
    """L'insieme dei tool che un run puo' usare.

    `allowed` a None significa nessuna restrizione — il caso della chat libera
    del Developer Studio, dove l'utente e' presente e decide lui. Un insieme
    esplicito e' il caso dei ruoli orchestrati, dove nessuno guarda.
    """

    allowed: Optional[frozenset] = None
    label: str = ""

    @classmethod
    def unrestricted(cls) -> "ToolPolicy":
        return cls(allowed=None, label="")

    @classmethod
    def of(cls, tools: Optional[Iterable[str]], label: str = "") -> "ToolPolicy":
        """Una policy dai nomi dichiarati, normalizzati e completati.

        Un elenco vuoto o assente non e' «nessun tool permesso»: e' «nessuna
        restrizione dichiarata». Un ruolo che volesse davvero non poter fare
        nulla non avrebbe motivo di esistere, mentre un elenco dimenticato e'
        un incidente frequente — e interpretarlo come divieto totale
        bloccherebbe il run al primo tool.
        """
        if not tools:
            return cls.unrestricted()
        canonici = {canonical(t) for t in tools if str(t or "").strip()}
        if not canonici:
            return cls.unrestricted()
        return cls(allowed=frozenset(canonici | CONTROL_TOOLS), label=label)

    @property
    def restricted(self) -> bool:
        return self.allowed is not None

    def permits(self, tool_name: str) -> bool:
        if self.allowed is None:
            return True
        return canonical(tool_name) in self.allowed

    def visible_tools(self) -> Tuple[str, ...]:
        """I tool permessi, in ordine stabile, per prompt e diagnostica."""
        if self.allowed is None:
            return ()
        return tuple(sorted(self.allowed))

    def refusal(self, tool_name: str) -> str:
        """Il messaggio restituito al modello quando il tool e' vietato.

        Nomina le alternative: un rifiuto che non dice cosa si puo' fare
        invece produce un secondo tentativo identico, che e' il modo piu' caro
        di spendere un turno.
        """
        nome = canonical(tool_name)
        chi = f" al ruolo {self.label}" if self.label else ""
        return (
            f"Tool '{nome}' NON permesso{chi} in questa fase. "
            f"Puoi usare soltanto: {', '.join(self.visible_tools())}. "
            "Scegli fra questi il tool adatto al passo successivo; se il "
            "lavoro richiede davvero un tool non disponibile, dichiaralo "
            "nella risposta invece di riprovare."
        )

    def prompt_section(self) -> str:
        """La riga di prompt che dichiara la restrizione al modello.

        Vietare senza dirlo funziona lo stesso, ma costa un turno per ogni
        divieto scoperto; dirlo in anticipo costa una riga sola.
        """
        if self.allowed is None:
            return ""
        return (
            "\n## TOOL PERMESSI IN QUESTA FASE\n"
            f"Puoi usare esclusivamente: {', '.join(self.visible_tools())}.\n"
            "Ogni altro tool verra rifiutato dal sistema."
        )
