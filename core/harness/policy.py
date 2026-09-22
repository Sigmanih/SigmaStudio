# ==============================================================================
# core/harness/policy.py — Quali tool puo' usare chi
# Sigma Studio v8 — Agent Harness (kernel)
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
    # ricerca simboli AST
    "find_symbol": "find_symbol",
    "symbol": "find_symbol",
    "definition": "find_symbol",
    "where_is": "find_symbol",
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
    "spec": "spec",
    "requirements": "spec",
    "criteri": "spec",
    "specifica": "spec",
    "tasks": "pipeline",
    "set_tasks": "pipeline",
    "update_pipeline": "pipeline",
    "pipeline": "pipeline",
    "finish_task": "complete_goal",
    "task_complete": "complete_goal",
    "complete_goal": "complete_goal",
    # KiCad — progettazione della scheda
    "kicad_status": "kicad_status", "kicad_open": "kicad_open",
    "kicad_board_read": "kicad_board_read", "kicad_list_parts": "kicad_list_parts",
    "kicad_pads": "kicad_pads", "kicad_nets": "kicad_nets",
    "kicad_trace_width": "kicad_trace_width",
    "kicad_board_evaluate": "kicad_board_evaluate",
    "kicad_placement_optimize": "kicad_placement_optimize",
    "kicad_placement_apply": "kicad_placement_apply",
    "kicad_add_track": "kicad_add_track", "kicad_add_route": "kicad_add_route",
    "kicad_add_via": "kicad_add_via",
    "kicad_add_footprint": "kicad_add_footprint",
    "kicad_remove_footprint": "kicad_remove_footprint",
    "kicad_undo": "kicad_undo",
    "kicad_drc": "kicad_drc", "kicad_erc": "kicad_erc",
    "kicad_export_gerbers": "kicad_export_gerbers",
    "kicad_export_bom": "kicad_export_bom", "kicad_render": "kicad_render",
    # pcbnew bridge: creazione e ispezione diretta via API pcbnew
    "kicad_pcbnew_status": "kicad_pcbnew_status",
    "kicad_libraries": "kicad_libraries",
    "kicad_search_footprint": "kicad_search_footprint",
    "kicad_new_board": "kicad_new_board",
    "kicad_add_part": "kicad_add_part",
    "kicad_read_board_full": "kicad_read_board_full",
    "instrada": "kicad_add_route", "verifica_pcb": "kicad_drc",
    # EDA — disegno del circuito
    "eda_status": "eda_status",
    "eda_search_part": "eda_search_part",
    "cerca_componente": "eda_search_part",
    "eda_place_part": "eda_place_part",
    "piazza_componente": "eda_place_part",
    "eda_list_parts": "eda_list_parts",
    "eda_pins": "eda_pins",
    "eda_connect": "eda_connect",
    "collega": "eda_connect",
    "eda_wire": "eda_wire",
    "pista": "eda_wire",
    "eda_note": "eda_note",
    "eda_verify": "eda_verify",
    "verifica_circuito": "eda_verify",
    "eda_capture": "eda_capture",
    "eda_save": "eda_save",
    "eda_pcb_drc": "eda_pcb_drc",
    "eda_pcb_unrouted": "eda_pcb_unrouted",
    "eda_pcb_route_net": "eda_pcb_route_net",
    "eda_pcb_route_all": "eda_pcb_route_all",
    "eda_pcb_add_via": "eda_pcb_add_via",
    "eda_pcb_outline": "eda_pcb_outline",
    "eda_pcb_mounting_holes": "eda_pcb_mounting_holes",
    "eda_export_gerbers": "eda_export_gerbers",
    # coda di lavoro
    "queue_add": "queue_add",
    "add_to_queue": "queue_add",
    "enqueue": "queue_add",
    "coda": "queue_add",
}

#: Non toccano il workspace: registrano il piano e chiudono il lavoro.
#: `queue_add` sta qui perche' non scrive un file: mette in fila del lavoro che
#: altri run faranno. Chi puo' pianificare puo' anche depositare il piano.
CONTROL_TOOLS: Set[str] = {"spec", "pipeline", "complete_goal", "queue_add"}

#: I tool EDA che guardano il progetto senza toccarlo. `eda_verify` sta qui ed
#: e' il piu' importante: la prova di un collegamento deve poter essere chiesta
#: anche da chi non ha il permesso di scrivere.
EDA_READ_TOOLS: Set[str] = {
    "eda_status", "eda_search_part", "eda_list_parts", "eda_pins",
    "eda_verify", "eda_capture", "eda_pcb_drc", "eda_pcb_unrouted",
    "eda_export_gerbers",
}
EDA_WRITE_TOOLS: Set[str] = {
    "eda_place_part", "eda_connect", "eda_wire", "eda_note", "eda_save",
    "eda_pcb_route_net", "eda_pcb_route_all", "eda_pcb_add_via",
    "eda_pcb_outline", "eda_pcb_mounting_holes",
}

#: KiCad: guardare la scheda non e' toccarla. `kicad_drc` sta fra le letture
#: perche' la prova che un layout regge deve poterla chiedere anche chi non ha
#: il permesso di scrivere — e' cosi' che un revisore controlla.
KICAD_READ_TOOLS: Set[str] = {
    "kicad_status", "kicad_open", "kicad_board_read", "kicad_list_parts",
    "kicad_pads", "kicad_nets", "kicad_trace_width", "kicad_board_evaluate",
    "kicad_placement_optimize", "kicad_drc", "kicad_erc",
    # pcbnew bridge: letture che non toccano i file di progetto
    "kicad_pcbnew_status", "kicad_libraries", "kicad_search_footprint",
    "kicad_read_board_full",
}
KICAD_WRITE_TOOLS: Set[str] = {
    "kicad_placement_apply", "kicad_add_track", "kicad_add_route",
    "kicad_add_via", "kicad_add_footprint", "kicad_remove_footprint",
    "kicad_undo", "kicad_export_gerbers", "kicad_export_bom", "kicad_render",
    # pcbnew bridge: questi due scrivono file di progetto
    "kicad_new_board", "kicad_add_part",
}

READ_ONLY_TOOLS: Set[str] = {
    "spec", "read_file", "list_dir", "glob", "search_code", "find_symbol",
    "screenshot", "pipeline", "queue_add", "complete_goal"
} | EDA_READ_TOOLS | KICAD_READ_TOOLS

PLAN_ONLY_TOOLS: Set[str] = {
    "spec", "read_file", "list_dir", "glob", "search_code", "find_symbol",
    "pipeline", "queue_add", "complete_goal"
}


def canonical(tool_name: str) -> str:
    """Il nome canonico di un tool, o il nome stesso se non e' un alias noto."""
    return ALIASES.get(str(tool_name or "").strip().lower(), str(tool_name or "").strip().lower())


#: Dove comincia e dove finisce l'elenco dei tool nel prompt di sistema.
_INIZIO_TOOL = "## TOOL DISPONIBILI"
_FINE_TOOL = "## VINCOLI GENERALI"


def filter_tool_docs(prompt: str, policy: "ToolPolicy") -> str:
    """Il prompt con documentati solo i tool che questo run puo' usare.

    Dichiarare un tool e poi rifiutarlo non e' neutro: il modello lo legge, lo
    sceglie perche' e' quello adatto al passo, e si prende un rifiuto. Su un run
    reale dell'orchestratore l'Architect e il Coder hanno provato entrambi
    `append_file` — documentato nel prompt, assente dai loro ruoli — e hanno
    perso un turno a testa per una possibilita' che non esisteva.

    Il filtro toglie le voci dei tool non permessi invece di aggiungere una
    riga che li vieta: un elenco corretto costa meno di un elenco sbagliato piu'
    la sua smentita, e soprattutto non lascia al modello modo di sceglierli.
    """
    if not policy.restricted:
        return prompt

    inizio = prompt.find(_INIZIO_TOOL)
    fine = prompt.find(_FINE_TOOL, inizio + 1) if inizio >= 0 else -1
    if inizio < 0 or fine < 0:
        # Prompt personalizzato senza la sezione attesa: meglio lasciarlo
        # com'e' che tagliarlo a caso.
        return prompt

    permessi = set(policy.visible_tools())
    tenuti = []
    for blocco in prompt[inizio:fine].split("\n\n"):
        spoglio = blocco.strip()
        if not spoglio.startswith("`"):
            # Intestazione della sezione o testo di raccordo: resta.
            tenuti.append(blocco)
            continue
        nome = spoglio[1:].split("`", 1)[0]
        if canonical(nome) in permessi:
            tenuti.append(blocco)

    return prompt[:inizio] + "\n\n".join(tenuti) + prompt[fine:]


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

    def intersect(self, altra: "ToolPolicy") -> "ToolPolicy":
        """Il permesso che soddisfa entrambe le restrizioni.

        Serve quando un profilo scelto dall'utente e un elenco dichiarato da un
        ruolo valgono insieme: il profilo e' un tetto — in sola lettura nessun
        ruolo puo' scrivere, per quanti tool dichiari — e il ruolo restringe
        dentro quel tetto. Prendere l'unione, o lasciare vincere l'ultimo
        arrivato, renderebbe il profilo aggirabile scegliendo il ruolo giusto.
        """
        if altra.allowed is None:
            return self
        if self.allowed is None:
            return altra
        comune = frozenset(self.allowed & altra.allowed) | CONTROL_TOOLS
        etichetta = " + ".join(x for x in (self.label, altra.label) if x)
        return ToolPolicy(allowed=comune, label=etichetta)

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
