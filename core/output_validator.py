"""Output Validator for Sigma Studio — Valida l'output JSON degli agenti contro schemi.
Previene l'esecuzione di azioni malformate o non consentite."""
import json

# Schemi di validazione per tipo di agente
AGENT_OUTPUT_SCHEMAS = {
    "code_architect": {
        "response": {"type": "string", "min_length": 1},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"enum": ["create_file", "edit_file", "delete_file", "rename_file", "create_module", "create_topic", "run_test", "read_file", "run_terminal", "update_task", "send_notification"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "search": {"type": "string"},
                    "cmd": {"type": "string"},
                }
            }
        }
    },
    "math1": {
        "response": {"type": "string", "min_length": 1},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"enum": ["create_file", "edit_file", "create_module", "create_topic", "run_test", "read_file", "update_task", "send_notification"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                }
            }
        }
    },
    "sigma_architect": {
        "response": {"type": "string", "min_length": 1},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
                "properties": {
                    "type": {"enum": ["create_file", "edit_file", "delete_file", "rename_file", "create_module", "run_test", "read_file", "run_terminal", "update_task", "send_notification"]},
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "cmd": {"type": "string"},
                }
            }
        }
    },
    "default": {
        "response": {"type": "string"},
        "actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type"],
            }
        }
    }
}


def validate_agent_output(agent_id: str, parsed_json: dict) -> tuple:
    """Validate an agent's JSON output against its schema.

    Args:
        agent_id: Agent identifier ('sigma_architect', 'math1', 'code_architect', etc.)
        parsed_json: Parsed JSON dict from agent response

    Returns:
        Tuple of (is_valid: bool, errors: list of error messages)
    """
    if not isinstance(parsed_json, dict):
        return False, ["Output non è un oggetto JSON valido"]

    # Get schema for this agent
    schema = AGENT_OUTPUT_SCHEMAS.get(agent_id, AGENT_OUTPUT_SCHEMAS["default"])
    errors = []

    # Check required top-level keys
    if "response" not in parsed_json:
        errors.append("Manca il campo 'response' nell'output JSON")
    elif not isinstance(parsed_json["response"], str) or len(parsed_json["response"].strip()) == 0:
        errors.append("Il campo 'response' deve essere una stringa non vuota")

    # Validate actions if present
    actions = parsed_json.get("actions", [])
    if not isinstance(actions, list):
        errors.append("Il campo 'actions' deve essere un array")
    else:
        for i, action in enumerate(actions):
            action_errors = _validate_action(action, schema)
            if action_errors:
                for err in action_errors:
                    errors.append(f"Azioni[{i}]: {err}")

    # Validate tasks if in planning mode
    tasks = parsed_json.get("tasks", [])
    if tasks:
        if not isinstance(tasks, list):
            errors.append("Il campo 'tasks' deve essere un array")
        else:
            for i, task in enumerate(tasks):
                if not isinstance(task.get("titolo"), str) or not task["titolo"].strip():
                    errors.append(f"Tasks[{i}]: 'titolo' mancante o vuoto")
                if task.get("priorita") and task["priorita"] not in ("critica", "alta", "media", "bassa"):
                    errors.append(f"Tasks[{i}]: 'priorita' non valida: {task['priorita']}")

    return len(errors) == 0, errors


def _validate_action(action: dict, schema: dict) -> list:
    """Validate a single action against schema rules."""
    errors = []

    if not isinstance(action, dict):
        return ["L'azione deve essere un oggetto JSON"]

    action_type = action.get("type", "")
    if not action_type:
        return ["Manca il campo 'type' nell'azione"]

    # Check action type is in allowed list
    items_schema = schema.get("actions", {}).get("items", {})
    props = items_schema.get("properties", {})
    type_enum = props.get("type", {}).get("enum", [])
    if type_enum and action_type not in type_enum:
        errors.append(f"Tipo '{action_type}' non consentito per questo agente. Tipi validi: {', '.join(type_enum)}")

    # Validate required fields per action type
    if action_type in ("create_file", "edit_file") and not action.get("path"):
        errors.append(f"Azioni di tipo '{action_type}' richiedono il campo 'path'")

    if action_type == "run_terminal" and not action.get("cmd"):
        errors.append("Azioni 'run_terminal' richiedono il campo 'cmd'")

    if action_type == "rename_file":
        if not action.get("old_path"):
            errors.append("Azioni 'rename_file' richiedono il campo 'old_path'")
        if not action.get("new_path"):
            errors.append("Azioni 'rename_file' richiedono il campo 'new_path'")

    return errors


def clean_action_paths(actions: list) -> list:
    """Normalize and validate file paths in actions."""
    cleaned = []
    for action in actions:
        if not isinstance(action, dict):
            continue
        for path_key in ("path", "old_path", "new_path"):
            if path_key in action and action[path_key]:
                path = action[path_key].replace("\\", "/")
                # Prevent path traversal
                if ".." in path:
                    continue
                action[path_key] = path
        cleaned.append(action)
    return cleaned