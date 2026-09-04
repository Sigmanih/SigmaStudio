# ==============================================================================
# core/developer_studio/tool_policy.py — Quali tool puo' usare chi
# Sigma Studio v8 — Developer Studio AI-Native IDE
# ==============================================================================
"""Il permesso d'uso dei tool e profili operativi (Read-Only, Plan-Only, Autonomous).
"""

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Set, Tuple

#: alias -> nome canonico. Ricalca i gruppi accettati da `execute_admin_tool`:
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

READ_ONLY_TOOLS: Set[str] = {
    "read_file", "list_dir", "glob", "search_code", "screenshot", "pipeline", "complete_goal"
}

PLAN_ONLY_TOOLS: Set[str] = {
    "read_file", "list_dir", "glob", "search_code", "pipeline", "complete_goal"
}


def canonical(tool_name: str) -> str:
    """Il nome canonico di un tool, o il nome stesso se non e' un alias noto."""
    return ALIASES.get(str(tool_name or "").strip().lower(), str(tool_name or "").strip().lower())


@dataclass(frozen=True)
class ToolPolicy:
    """L'insieme dei tool che un run puo' usare."""

    allowed: Optional[frozenset] = None
    label: str = ""

    @classmethod
    def unrestricted(cls) -> "ToolPolicy":
        return cls(allowed=None, label="")

    @classmethod
    def read_only(cls) -> "ToolPolicy":
        return cls(allowed=frozenset(READ_ONLY_TOOLS), label="Sola Lettura")

    @classmethod
    def plan_only(cls) -> "ToolPolicy":
        return cls(allowed=frozenset(PLAN_ONLY_TOOLS), label="Sola Pianificazione")

    @classmethod
    def for_profile(cls, profile_name: str) -> "ToolPolicy":
        p = str(profile_name or "").lower().strip()
        if p in ("read_only", "readonly", "read"):
            return cls.read_only()
        elif p in ("plan_only", "planonly", "plan", "planning"):
            return cls.plan_only()
        return cls.unrestricted()

    @classmethod
    def of(cls, tools: Optional[Iterable[str]], label: str = "") -> "ToolPolicy":
        """Una policy dai nomi dichiarati, normalizzati e completati."""
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
        """Il messaggio restituito al modello quando il tool e' vietato."""
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
        """La riga di prompt che dichiara la restrizione al modello."""
        if self.allowed is None:
            return ""
        return (
            "\n## TOOL PERMESSI IN QUESTA FASE\n"
            f"Puoi usare esclusivamente: {', '.join(self.visible_tools())}.\n"
            "Ogni altro tool verra rifiutato dal sistema."
        )
