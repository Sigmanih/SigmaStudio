"""Backup and Rollback Manager for Sigma Studio agentic actions."""
import os
import shutil
import json
import datetime
import uuid
from core.logger import get_logger

log = get_logger(__name__)

BACKUP_DIR = ".backups"
REGISTRY_FILE = os.path.join(BACKUP_DIR, "registry.json")

def _load_registry() -> dict:
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR, exist_ok=True)
    if not os.path.exists(REGISTRY_FILE):
        return {}
    try:
        with open(REGISTRY_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as e:
        log.error("Failed to load backup registry: %s", e)
        return {}

def _save_registry(registry: dict):
    try:
        with open(REGISTRY_FILE, "w", encoding="utf-8") as fh:
            json.dump(registry, fh, indent=2)
    except Exception as e:
        log.error("Failed to save backup registry: %s", e)

def create_backup(file_path: str, action_type: str) -> str:
    """Create a security backup of a file before it is written, overwritten, renamed or deleted.

    Returns:
        The backup ID string if successful, empty string otherwise.
    """
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR, exist_ok=True)
            
        backup_id = str(uuid.uuid4())[:8]
        exists_before = os.path.exists(file_path)
        backup_file_path = ""
        
        if exists_before:
            filename = os.path.basename(file_path)
            backup_filename = f"{backup_id}_{filename}.bak"
            backup_file_path = os.path.join(BACKUP_DIR, backup_filename).replace("\\", "/")
            shutil.copy2(file_path, backup_file_path)
            
        registry = _load_registry()
        registry[backup_id] = {
            "backup_id": backup_id,
            "original_path": file_path.replace("\\", "/"),
            "backup_path": backup_file_path,
            "action_type": action_type,
            "timestamp": datetime.datetime.now().isoformat(),
            "exists_before": exists_before
        }
        _save_registry(registry)
        log.info("Backup created: %s -> %s (exists_before=%s)", file_path, backup_id, exists_before)
        return backup_id
    except Exception as e:
        log.error("Error creating backup for %s: %s", file_path, e)
        return ""

def rollback_backup(backup_id: str) -> tuple[bool, str]:
    """Restore the file to its pre-action state using the backup registry entry.

    Returns:
        A tuple (success, message).
    """
    try:
        registry = _load_registry()
        if backup_id not in registry:
            return False, f"ID backup '{backup_id}' non trovato nel registro."
            
        entry = registry[backup_id]
        original_path = entry["original_path"]
        backup_path = entry["backup_path"]
        exists_before = entry["exists_before"]
        
        if exists_before:
            if not backup_path or not os.path.exists(backup_path):
                return False, f"File di backup '{backup_path}' non trovato sul disco."
            # Restore original file
            os.makedirs(os.path.dirname(os.path.abspath(original_path)) or ".", exist_ok=True)
            shutil.copy2(backup_path, original_path)
            log.info("Rollback: restored %s from backup %s", original_path, backup_path)
        else:
            # File was created, so rollback means removing it
            if os.path.exists(original_path):
                os.remove(original_path)
                log.info("Rollback: deleted created file %s", original_path)
                
        # Clean up backup file
        if backup_path and os.path.exists(backup_path):
            try:
                os.remove(backup_path)
            except Exception:
                pass
            
        del registry[backup_id]
        _save_registry(registry)
        return True, f"Ripristinato con successo: {os.path.basename(original_path)}"
    except Exception as e:
        log.error("Rollback failed for backup %s: %s", backup_id, e)
        return False, str(e)
