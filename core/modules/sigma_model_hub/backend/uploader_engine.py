# ==============================================================================
# core/modules/sigma_model_hub/backend/uploader_engine.py
# High-Performance Asynchronous Model Publisher for Hugging Face Hub
# ==============================================================================
from __future__ import annotations
import os
import io
import time
import json
import uuid
import threading
from typing import Dict, Any, List, Optional, Callable
from core.logger import get_logger
from .hf_client import resolve_hf_token

log = get_logger(__name__)


def _format_bytes(num_bytes: int) -> str:
    """Format bytes to human readable string (KB, MB, GB)."""
    if num_bytes < 1024:
        return f"{num_bytes} B"
    elif num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.1f} KB"
    elif num_bytes < 1024 * 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{num_bytes / (1024 * 1024 * 1024):.2f} GB"


class ProgressReader(io.BufferedReader):
    """File reader wrapper that tracks bytes read and reports progress."""
    def __init__(self, raw_file, total_size: int, on_progress: Callable[[int, int], None], check_cancelled: Callable[[], bool]):
        super().__init__(raw_file)
        self.total_size = total_size
        self.on_progress = on_progress
        self.check_cancelled = check_cancelled
        self.bytes_read = 0

    def read(self, size=-1):
        if self.check_cancelled():
            raise InterruptedError("Caricamento annullato dall'utente")
        chunk = super().read(size)
        if chunk:
            self.bytes_read += len(chunk)
            if self.on_progress:
                self.on_progress(self.bytes_read, self.total_size)
        return chunk

    def seek(self, offset, whence=io.SEEK_SET):
        res = super().seek(offset, whence)
        self.bytes_read = self.tell()
        return res


class ModelUploadTask:
    """Represents an active or completed model upload task."""
    def __init__(
        self,
        task_id: str,
        local_path: str,
        repo_id: str,
        repo_type: str = "model",
        private: bool = False,
        commit_message: str = "Upload model via Sigma Studio",
        model_card: Optional[str] = None
    ):
        self.task_id = task_id
        self.local_path = os.path.abspath(local_path)
        self.filename = os.path.basename(self.local_path)
        self.is_dir = os.path.isdir(self.local_path)
        self.repo_id = repo_id.strip()
        self.repo_type = repo_type
        self.private = private
        self.commit_message = commit_message or "Upload model via Sigma Studio"
        self.model_card = model_card

        self.status = "queued"  # queued, uploading, completed, failed, cancelled
        self.progress_pct = 0.0
        self.uploaded_bytes = 0
        self.total_bytes = 0
        self.speed_bps = 0.0
        self.speed_label = "0 MB/s"
        self.uploaded_label = "0 MB"
        self.eta_seconds = 0
        self.error_message = ""
        self.hf_url = f"https://huggingface.co/{self.repo_id}"
        self.created_at = time.time()
        self.completed_at = 0.0

        self._cancelled = False
        self._start_time = 0.0
        self._last_progress_time = 0.0
        self._last_progress_bytes = 0

    def cancel(self):
        self._cancelled = True
        self.status = "cancelled"
        self.error_message = "Caricamento annullato dall'utente"

    def is_cancelled(self) -> bool:
        return self._cancelled

    def update_progress(self, current_bytes: int, total_bytes: int):
        now = time.time()
        self.uploaded_bytes = current_bytes
        self.total_bytes = max(total_bytes, 1)
        self.progress_pct = round(min(100.0, (current_bytes / self.total_bytes) * 100.0), 1)
        self.uploaded_label = f"{_format_bytes(current_bytes)} / {_format_bytes(self.total_bytes)}"

        if self._last_progress_time > 0 and (now - self._last_progress_time) >= 0.5:
            dt = now - self._last_progress_time
            db = current_bytes - self._last_progress_bytes
            if dt > 0 and db >= 0:
                self.speed_bps = db / dt
                self.speed_label = f"{_format_bytes(int(self.speed_bps))}/s"
                remaining = self.total_bytes - current_bytes
                if self.speed_bps > 0:
                    self.eta_seconds = int(remaining / self.speed_bps)
                else:
                    self.eta_seconds = 0
            self._last_progress_time = now
            self._last_progress_bytes = current_bytes
        elif self._last_progress_time == 0:
            self._last_progress_time = now
            self._last_progress_bytes = current_bytes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "local_path": self.local_path,
            "filename": self.filename,
            "is_dir": self.is_dir,
            "repo_id": self.repo_id,
            "repo_type": self.repo_type,
            "private": self.private,
            "commit_message": self.commit_message,
            "status": self.status,
            "progress_pct": self.progress_pct,
            "uploaded_bytes": self.uploaded_bytes,
            "total_bytes": self.total_bytes,
            "uploaded_label": self.uploaded_label,
            "speed_label": self.speed_label,
            "eta_seconds": self.eta_seconds,
            "error_message": self.error_message,
            "hf_url": self.hf_url,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }


class ModelUploaderManager:
    """Manages background upload tasks to Hugging Face Hub."""
    def __init__(self):
        self.tasks: Dict[str, ModelUploadTask] = {}
        self._lock = threading.Lock()

    def get_whoami(self, token: Optional[str] = None) -> Dict[str, Any]:
        """Validates token with Hugging Face Hub and returns authenticated user profile & permissions."""
        resolved = resolve_hf_token(token)
        actual_token = resolved.get("token", "")
        if not actual_token:
            return {
                "authenticated": False,
                "error": "Nessun token Hugging Face trovato. Configura il tuo Access Token in Impostazioni.",
                "token_source": resolved.get("source", "none"),
                "token_detail": resolved.get("detail", "")
            }

        try:
            from huggingface_hub import whoami
            info = whoami(token=actual_token)
            username = info.get("name") or info.get("username", "")
            fullname = info.get("fullname", "")
            avatar_url = info.get("avatarUrl", "")
            email = info.get("email", "")
            orgs = [
                {
                    "name": org.get("name"),
                    "fullname": org.get("fullname", org.get("name")),
                    "avatar_url": org.get("avatarUrl", "")
                }
                for org in (info.get("orgs") or [])
                if isinstance(org, dict) and org.get("name")
            ]

            # Detect write permission
            auth = info.get("auth", {})
            access_token_info = auth.get("accessToken", {}) if isinstance(auth, dict) else {}
            role = access_token_info.get("role", "")
            can_write = True
            if role == "read":
                can_write = False

            return {
                "authenticated": True,
                "username": username,
                "fullname": fullname,
                "email": email,
                "avatar_url": avatar_url,
                "orgs": orgs,
                "role": role or "write",
                "can_write": can_write,
                "token_source": resolved.get("source", "input"),
                "token_detail": resolved.get("detail", "")
            }
        except Exception as e:
            log.warning(f"[ModelUploader] Whoami check failed: {e}")
            return {
                "authenticated": False,
                "error": f"Autenticazione fallita: {str(e)}",
                "token_source": resolved.get("source", "input"),
                "token_detail": resolved.get("detail", "")
            }

    def _generate_default_model_card(self, task: ModelUploadTask) -> str:
        """Generates a rich README.md model card if not provided."""
        filename = task.filename
        fname_lower = filename.lower()
        is_gguf = fname_lower.endswith(".gguf") or "gguf" in fname_lower
        
        # Tags detection
        tags = ["text-generation", "sigma-studio"]
        if is_gguf:
            tags.extend(["gguf", "llama.cpp"])
        else:
            tags.append("safetensors")

        tags_yaml = "\n".join([f"- {t}" for t in tags])

        return f"""---
language:
- en
- it
license: apache-2.0
tags:
{tags_yaml}
pipeline_tag: text-generation
---

# {task.repo_id}

Modello pubblicato direttamente da **[Σ-SIGMA Studio](https://github.com/Sigmanih/SigmaStudio)**.

## Dettagli Modello
- **File / Storage:** `{filename}`
- **Formato:** `{'GGUF (Quantized)' if is_gguf else 'Safetensors / Standard'}`
- **Data di Pubblicazione:** `{time.strftime('%Y-%m-%d %H:%M:%S')}`

## Utilizzo con SigmaEngine / llama.cpp
```bash
# Esempio di inferenza con llama.cpp o SigmaEngine
llama-cli -m {filename} -p "Ciao, come posso aiutarti oggi?"
```

---
*Creato e caricato con il modulo Model Hub di Sigma Studio.*
"""

    def start_upload(
        self,
        local_path: str,
        repo_id: str,
        private: bool = False,
        commit_message: str = "Upload model via Sigma Studio",
        model_card: Optional[str] = None,
        token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates and launches a background upload task."""
        if not local_path or not os.path.exists(local_path):
            return {"success": False, "error": f"File o directory '{local_path}' non trovato."}

        if not repo_id or "/" not in repo_id.strip():
            return {"success": False, "error": "Il nome del repository deve essere nel formato 'username/nome-modello'."}

        resolved = resolve_hf_token(token)
        actual_token = resolved.get("token", "")
        if not actual_token:
            return {"success": False, "error": "Token Hugging Face mancante. Inserisci un Access Token valido."}

        task_id = str(uuid.uuid4())[:8]
        task = ModelUploadTask(
            task_id=task_id,
            local_path=local_path,
            repo_id=repo_id,
            private=private,
            commit_message=commit_message,
            model_card=model_card
        )

        # Calculate initial total size
        if task.is_dir:
            total_size = sum(
                os.path.getsize(os.path.join(root, f))
                for root, _, files in os.walk(task.local_path)
                for f in files
            )
        else:
            total_size = os.path.getsize(task.local_path)

        task.total_bytes = total_size
        task.uploaded_label = f"0 B / {_format_bytes(total_size)}"

        with self._lock:
            self.tasks[task_id] = task

        thread = threading.Thread(target=self._run_upload_worker, args=(task, actual_token), daemon=True)
        thread.start()

        log.info(f"[ModelUploader] Launched upload task {task_id} for '{task.local_path}' -> '{task.repo_id}' ({_format_bytes(total_size)})")
        return {"success": True, "task": task.to_dict()}

    def _run_upload_worker(self, task: ModelUploadTask, token: str):
        """Worker thread executing the Hugging Face upload."""
        task.status = "uploading"
        task._start_time = time.time()
        task._last_progress_time = time.time()
        log.info(f"[ModelUploader][Task {task.task_id}] Connecting to Hugging Face Hub...")

        try:
            from huggingface_hub import HfApi
            api = HfApi(token=token)

            # 1. Ensure repository exists or create it
            log.info(f"[ModelUploader][Task {task.task_id}] Creating/Verifying repo '{task.repo_id}' (private={task.private})...")
            try:
                api.create_repo(
                    repo_id=task.repo_id,
                    repo_type="model",
                    private=task.private,
                    exist_ok=True
                )
            except Exception as e:
                # If repo already exists or created
                log.info(f"[ModelUploader][Task {task.task_id}] create_repo notice: {e}")

            if task.is_cancelled():
                return

            # 2. Upload README.md model card if not already uploaded or if provided
            try:
                card_content = task.model_card or self._generate_default_model_card(task)
                card_bytes = card_content.encode("utf-8")
                api.upload_file(
                    path_or_fileobj=io.BytesIO(card_bytes),
                    path_in_repo="README.md",
                    repo_id=task.repo_id,
                    repo_type="model",
                    commit_message=f"Update model card for {task.filename}"
                )
            except Exception as e:
                log.warning(f"[ModelUploader][Task {task.task_id}] Could not upload README.md: {e}")

            if task.is_cancelled():
                return

            # 3. Upload model file(s)
            if task.is_dir:
                # Directory upload
                log.info(f"[ModelUploader][Task {task.task_id}] Uploading folder '{task.local_path}' to '{task.repo_id}'...")
                
                # Walk and upload files with progress tracking
                all_files = []
                for root, _, files in os.walk(task.local_path):
                    for f in files:
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, task.local_path).replace("\\", "/")
                        size = os.path.getsize(full_path)
                        all_files.append((full_path, rel_path, size))

                accumulated_bytes = 0
                for full_path, rel_path, fsize in all_files:
                    if task.is_cancelled():
                        return
                    
                    def file_progress(read_in_file, total_in_file):
                        task.update_progress(accumulated_bytes + read_in_file, task.total_bytes)

                    with open(full_path, "rb") as raw_f:
                        wrapped = ProgressReader(raw_f, fsize, file_progress, task.is_cancelled)
                        api.upload_file(
                            path_or_fileobj=wrapped,
                            path_in_repo=rel_path,
                            repo_id=task.repo_id,
                            repo_type="model",
                            commit_message=task.commit_message
                        )
                    accumulated_bytes += fsize
            else:
                # Single file upload (e.g. .gguf)
                target_filename = task.filename
                log.info(f"[ModelUploader][Task {task.task_id}] Uploading file '{task.local_path}' as '{target_filename}'...")
                
                def file_progress(read_in_file, total_in_file):
                    task.update_progress(read_in_file, total_in_file)

                with open(task.local_path, "rb") as raw_f:
                    wrapped = ProgressReader(raw_f, task.total_bytes, file_progress, task.is_cancelled)
                    api.upload_file(
                        path_or_fileobj=wrapped,
                        path_in_repo=target_filename,
                        repo_id=task.repo_id,
                        repo_type="model",
                        commit_message=task.commit_message
                    )

            # Upload successfully finished
            task.progress_pct = 100.0
            task.uploaded_bytes = task.total_bytes
            task.uploaded_label = f"{_format_bytes(task.total_bytes)} / {_format_bytes(task.total_bytes)}"
            task.status = "completed"
            task.completed_at = time.time()
            log.info(f"[ModelUploader][Task {task.task_id}] Upload COMPLETED successfully -> {task.hf_url}")

        except InterruptedError as ie:
            task.status = "cancelled"
            task.error_message = str(ie)
            log.info(f"[ModelUploader][Task {task.task_id}] Upload cancelled by user.")
        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            log.error(f"[ModelUploader][Task {task.task_id}] Upload FAILED: {e}", exc_info=True)

    def cancel_upload(self, task_id: str) -> bool:
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status in ("queued", "uploading"):
                task.cancel()
                return True
        return False

    def remove_task(self, task_id: str) -> bool:
        with self._lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
        return False

    def list_tasks(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [task.to_dict() for task in sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)]


# Global singleton instance
uploader_manager = ModelUploaderManager()
