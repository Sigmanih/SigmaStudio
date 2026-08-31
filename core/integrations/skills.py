"""Registro delle skill di Sigma Studio.

Sigma è un kernel: le sue capacità sono skill componibili, non funzionalità
cablate. Ogni skill dichiara cosa serve per funzionare (applicazioni, pacchetti
Python, backend) e lo stato viene calcolato dal sistema reale — così l'utente
vede *perché* una skill non è pronta, non solo che manca.

Le skill disabilitate spariscono dalla barra laterale ma restano installabili:
disattivare è una scelta di ingombro, non una disinstallazione.
"""

import importlib.util
import json
from dataclasses import dataclass, field
from pathlib import Path

from core import paths
from core.logger import get_logger

log = get_logger("skills")

CONFIG_PATH = paths.config_file()


@dataclass(frozen=True)
class Skill:
    id: str
    label: str
    description: str
    tab_type: str = ""                # tipo di tab aperto dalla sidebar
    icon: str = "sparkles"
    core: bool = False                # le skill core non si disattivano
    requires_apps: tuple = ()         # id in app_manager.APPS
    requires_python: tuple = ()       # moduli importabili
    optional_apps: tuple = ()         # migliorano la skill ma non la bloccano
    mcp_server: str = ""              # server MCP che espone la skill agli agenti
    provides: tuple = field(default_factory=tuple)


SKILLS: tuple[Skill, ...] = (
    Skill(
        id="research", label="Ricerca & Moduli", core=True, icon="atom",
        description="Argomenti, moduli, teoria, script Python ed editor markdown.",
        tab_type="knowledge",
        provides=("organizzazione della ricerca", "editor", "esecuzione script"),
    ),
    Skill(
        id="chat", label="AI Studio Chat", core=True, icon="message-square",
        description="Chat con modelli locali e cloud, con accesso agli strumenti MCP.",
        tab_type="chat", mcp_server="",
        provides=("conversazione", "orchestrazione agenti"),
    ),
    Skill(
        id="creative", label="Creative Lab", icon="palette",
        description="Generazione immagini, editing, 3D, materiali, video e pipeline a nodi.",
        tab_type="creative_studio",
        optional_apps=("comfyui", "blender"),
        requires_python=("PIL", "numpy"),
        mcp_server="Creative MCP",
        provides=("immagini", "editing", "3D", "materiali", "video", "pipeline creative"),
    ),
    Skill(
        id="training", label="Training Lab", icon="graduation-cap",
        description="Fine-tuning, dataset, quantizzazione e benchmark dei modelli.",
        tab_type="training_lab",
        optional_apps=("ollama",),
        provides=("fine-tuning", "dataset", "benchmark"),
    ),
    Skill(
        id="hardware", label="Hardware Lab", icon="cpu",
        description="Stato GPU, VRAM, processi e tuning delle risorse.",
        tab_type="hardware_lab",
        provides=("monitoraggio GPU", "gestione VRAM"),
    ),
    Skill(
        id="mcp", label="MCP Hub", icon="plug",
        description="Strumenti interni ed esterni disponibili agli agenti, con policy di sicurezza.",
        tab_type="mcp_hub",
        provides=("tool per agenti", "server esterni", "governance"),
    ),
)

SKILLS_BY_ID = {s.id: s for s in SKILLS}


# ---------------------------------------------------------------------------

def _load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def enabled_ids(config: dict = None) -> set:
    """Skill attive: tutto è attivo salvo disattivazione esplicita."""
    cfg = config if config is not None else _load_config()
    disabled = set(cfg.get("skills", {}).get("disabled", []))
    return {s.id for s in SKILLS if s.core or s.id not in disabled}


def _python_missing(skill: Skill) -> list:
    return [m for m in skill.requires_python if importlib.util.find_spec(m) is None]


def status_all(config: dict = None) -> list[dict]:
    """Stato completo di ogni skill: attiva, pronta, e cosa manca."""
    from core.integrations import app_manager

    cfg = config if config is not None else _load_config()
    active = enabled_ids(cfg)
    apps = {a["id"]: a for a in app_manager.status_all()}

    out = []
    for skill in SKILLS:
        missing_apps = [aid for aid in skill.requires_apps
                        if not apps.get(aid, {}).get("installed")]
        missing_python = _python_missing(skill)
        inactive_optional = [aid for aid in skill.optional_apps
                             if not apps.get(aid, {}).get("running")]

        out.append({
            "id": skill.id,
            "label": skill.label,
            "description": skill.description,
            "icon": skill.icon,
            "tab_type": skill.tab_type,
            "core": skill.core,
            "enabled": skill.id in active,
            "ready": not missing_apps and not missing_python,
            "missing_apps": [apps.get(a, {"id": a, "label": a}) for a in missing_apps],
            "missing_python": missing_python,
            "optional_apps": [apps[a] for a in skill.optional_apps if a in apps],
            "degraded": [apps[a]["label"] for a in inactive_optional if a in apps],
            "mcp_server": skill.mcp_server,
            "provides": list(skill.provides),
        })
    return out


def set_enabled(skill_id: str, enabled: bool) -> dict:
    """Attiva o disattiva una skill, persistendo la scelta in config.json."""
    skill = SKILLS_BY_ID.get(skill_id)
    if not skill:
        return {"success": False, "error": f"Skill '{skill_id}' sconosciuta"}
    if skill.core and not enabled:
        return {"success": False,
                "error": f"'{skill.label}' è una skill di base e non può essere disattivata"}

    cfg = _load_config()
    disabled = set(cfg.setdefault("skills", {}).setdefault("disabled", []))
    disabled.discard(skill_id) if enabled else disabled.add(skill_id)
    cfg["skills"]["disabled"] = sorted(disabled)
    _save_config(cfg)

    log.info(f"Skill '{skill_id}' {'attivata' if enabled else 'disattivata'}")
    return {"success": True, "skill": skill_id, "enabled": enabled}
