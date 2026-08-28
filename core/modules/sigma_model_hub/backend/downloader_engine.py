# ==============================================================================
# core/modules/sigma_model_hub/backend/downloader_engine.py
# High-Performance Resilient Multi-Threaded Model Downloader with Auto-Resume for SigmaEngine
# ==============================================================================
from __future__ import annotations
import os
import time
import uuid
import threading
import urllib.request
import urllib.error
import http.client
import socket
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from core.logger import get_logger
from core.net_utils import safe_urlopen

log = get_logger(__name__)

from core.model_paths import models_dir as _active_models_dir

# The same directory the engine loads from, so a finished download is
# immediately visible to inference instead of landing where it never looks.
DEFAULT_MODELS_DIR = _active_models_dir()


@dataclass
class ModelDownloadTask:
    task_id: str
    model_id: str
    filename: str
    download_url: str
    save_path: str
    hf_token: Optional[str] = None
    status: str = "queued"  # queued | downloading | completed | failed | cancelled
    total_bytes: int = 0
    downloaded_bytes: int = 0
    speed_mbps: float = 0.0
    progress_pct: float = 0.0
    eta_seconds: float = 0.0
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    _cancel_flag: bool = False
    
    # Whole-repository multi-shard support
    is_repo_download: bool = False
    files_queue: List[Dict[str, str]] = field(default_factory=list)
    current_file_idx: int = 0
    current_file_name: str = ""

    def __post_init__(self):
        if self.files_queue:
            self.is_repo_download = True

    def to_dict(self) -> Dict[str, Any]:
        c_label = time.strftime('%Y-%m-%d %H:%M', time.localtime(self.created_at)) if self.created_at else None
        comp_label = time.strftime('%Y-%m-%d %H:%M', time.localtime(self.completed_at)) if self.completed_at else (c_label if self.status == "completed" else None)
        tot = max(self.total_bytes, self.downloaded_bytes) if self.total_bytes > 0 else self.downloaded_bytes
        pct = 100.0 if self.status == "completed" else (min(99.9, (self.downloaded_bytes / tot * 100.0)) if tot > 0 else self.progress_pct)
        return {
            "task_id": self.task_id,
            "model_id": self.model_id,
            "filename": self.filename,
            "download_url": self.download_url,
            "save_path": self.save_path,
            "status": self.status,
            "total_bytes": tot,
            "downloaded_bytes": self.downloaded_bytes,
            "total_mb": round(tot / (1024**2), 1) if tot > 0 else 0,
            "downloaded_mb": round(self.downloaded_bytes / (1024**2), 1),
            "speed_mbps": round(self.speed_mbps, 2),
            "progress_pct": round(pct, 1),
            "eta_seconds": int(self.eta_seconds),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "created_at_label": c_label,
            "completed_at_label": comp_label,
            "error_message": self.error_message,
            "is_repo_download": self.is_repo_download,
            "total_files": len(self.files_queue) if self.files_queue else 1,
            "current_file_idx": self.current_file_idx,
            "current_file_name": self.current_file_name
        }


class ModelDownloadManager:
    """Manages background downloads from Hugging Face with multi-shard resume and auto-recovery."""

    def __init__(self, models_dir: str = DEFAULT_MODELS_DIR):
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)
        self.tasks: Dict[str, ModelDownloadTask] = {}
        self.dismissed_task_ids: set = set()
        self.lock = threading.Lock()

    def set_models_dir(self, new_dir: str):
        # Keep the shared resolver in step, or the engine would carry on
        # reading the previous location.
        from core.model_paths import set_models_dir as _set_shared
        _set_shared(new_dir)
        with self.lock:
            self.models_dir = new_dir
            os.makedirs(self.models_dir, exist_ok=True)

    def start_single_download(
        self,
        model_id: str,
        filename: str,
        download_url: str,
        hf_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Starts a background download task for a single file."""
        clean_mid = model_id.replace("/", "--")
        target_dir = os.path.join(self.models_dir, clean_mid)
        os.makedirs(target_dir, exist_ok=True)
        save_path = os.path.join(target_dir, filename)

        if not hf_token:
            from .hf_client import get_effective_hf_token
            hf_token = get_effective_hf_token()

        task_id = str(uuid.uuid4())[:8]
        task = ModelDownloadTask(
            task_id=task_id,
            model_id=model_id,
            filename=filename,
            download_url=download_url,
            save_path=save_path,
            hf_token=hf_token
        )

        with self.lock:
            self.tasks[task_id] = task

        t = threading.Thread(target=self._single_download_worker, args=(task,), daemon=True)
        t.start()

        log.info(f"[ModelDownloader] Task {task_id} launched for {model_id}/{filename}")
        return task.to_dict()

    start_download = start_single_download

    def start_repo_download(
        self,
        model_id: str,
        files_list: Optional[List[Dict[str, str]]] = None,
        hf_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Starts a background download task for the entire model (all shards and config files)."""
        if not hf_token:
            from .hf_client import get_effective_hf_token
            hf_token = get_effective_hf_token()

        if not files_list:
            from .hf_client import get_hf_model_details
            details = get_hf_model_details(model_id, hf_token=hf_token)
            files_list = details.get("files", [])

        if not files_list:
            files_list = [{
                "filename": f"{model_id.split('/')[-1]}.safetensors",
                "download_url": f"https://huggingface.co/{model_id}/resolve/main/model.safetensors"
            }]

        clean_mid = model_id.replace("/", "--")
        target_dir = os.path.join(self.models_dir, clean_mid)
        os.makedirs(target_dir, exist_ok=True)

        # Smart GGUF Filtering: If repository contains multiple GGUF quantization variants,
        # download ONLY the single optimal/preferred quantization instead of downloading all variants (avoiding 50GB+ duplicates)
        gguf_entries = [f for f in files_list if f.get("filename", "").lower().endswith(".gguf")]
        if len(gguf_entries) > 1:
            try:
                from .handlers import _load_hub_config
                cfg = _load_hub_config()
                pref_q = (cfg.get("preferred_quantization") or "Q4_K_M").upper()
            except Exception:
                pref_q = "Q4_K_M"

            # Check if model_id explicitly names a specific quantization variant (e.g. Q8_0 in MIDI-LLM_Llama-3.2-1B-Q8_0-GGUF)
            mid_upper = model_id.upper().replace("-", "_")
            explicit_id_quant = ""
            for q_cand in ["Q8_0", "Q5_K_M", "Q5_K_S", "Q5_0", "Q4_K_M", "Q4_K_S", "Q4_0", "Q6_K", "Q3_K_M", "Q3_K_S", "Q2_K", "IQ4_XS", "IQ3_M", "IQ2_XXS", "F16", "BF16"]:
                if q_cand in mid_upper:
                    explicit_id_quant = q_cand
                    break

            priority_list = [p for p in [
                explicit_id_quant,
                pref_q,
                "Q4_K_M", "Q4_K_S", "Q5_K_M", "Q5_K_S",
                "Q6_K", "Q8_0", "Q3_K_M", "Q3_K_S", "Q2_K", "F16", "BF16"
            ] if p]

            selected_ggufs = []
            matched_tag = ""
            for q_tag in priority_list:
                q_clean = q_tag.lower().replace("_", "").replace("-", "")
                matches = [
                    f for f in gguf_entries
                    if q_clean in f.get("filename", "").lower().replace("_", "").replace("-", "")
                ]
                if matches:
                    selected_ggufs = matches
                    matched_tag = q_tag
                    break

            if not selected_ggufs:
                selected_ggufs = [gguf_entries[0]]
                matched_tag = "GGUF"

            non_gguf_entries = [f for f in files_list if not f.get("filename", "").lower().endswith(".gguf")]
            files_list = selected_ggufs + non_gguf_entries
            display_name = f"{model_id.split('/')[-1]} ({matched_tag})"
        else:
            display_name = f"{model_id.split('/')[-1]} ({len(files_list)} file / shard)" if len(files_list) > 1 else files_list[0].get("filename", f"{model_id.split('/')[-1]}.safetensors")

        exact_bytes = sum(int(f.get("size", 0)) for f in files_list if f.get("size"))
        if exact_bytes > 0:
            estimated_total_bytes = exact_bytes
        else:
            from .hf_client import parse_model_specs
            specs = parse_model_specs(model_id, model_id)
            estimated_total_bytes = int(specs.get("size_gb", 0) * (1024**3))

        task_id = str(uuid.uuid4())[:8]
        task = ModelDownloadTask(
            task_id=task_id,
            model_id=model_id,
            filename=display_name,
            download_url="",
            save_path=target_dir,
            hf_token=hf_token,
            total_bytes=estimated_total_bytes,
            files_queue=files_list
        )

        with self.lock:
            self.tasks[task_id] = task

        t = threading.Thread(target=self._repo_download_worker, args=(task, target_dir), daemon=True)
        t.start()

        log.info(f"[ModelDownloader] Whole-Repo task {task_id} launched for {model_id} ({len(files_list)} files)")
        return task.to_dict()

    def pause_download(self, task_id: str) -> bool:
        """Pauses an active download, keeping partial bytes intact for later resume."""
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status in ["queued", "downloading"]:
                task._cancel_flag = True
                task.status = "paused"
                task.speed_mbps = 0.0
                task.eta_seconds = 0
                log.info(f"[ModelDownloader] Download #{task_id} ({task.filename}) in PAUSA.")
                return True
        return False

    def resume_download(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Resumes a paused download from where it stopped."""
        return self.retry_download(task_id)

    def retry_download(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Resumes/Retries a failed, paused or cancelled download task from where it left off."""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return None

            from .hf_client import get_effective_hf_token
            latest_token = get_effective_hf_token()
            if latest_token:
                task.hf_token = latest_token

            task._cancel_flag = False
            task.status = "queued"
            task.error_message = None

        if task.is_repo_download:
            t = threading.Thread(target=self._repo_download_worker, args=(task, task.save_path), daemon=True)
            t.start()
        else:
            t = threading.Thread(target=self._single_download_worker, args=(task,), daemon=True)
            t.start()

        log.info(f"[ModelDownloader] Resuming/Retrying task {task_id} for {task.model_id}...")
        return task.to_dict()

    def cancel_download(self, task_id: str) -> bool:
        """Cancels an active download."""
        with self.lock:
            task = self.tasks.get(task_id)
            if task and task.status in ["queued", "downloading", "paused"]:
                task._cancel_flag = True
                task.status = "cancelled"
                return True
        return False

    def remove_task(self, task_id: str, delete_from_disk: bool = False) -> bool:
        """Removes a task from the list and optionally deletes files from disk."""
        with self.lock:
            task = self.tasks.get(task_id)
            self.dismissed_task_ids.add(task_id)
            if task and task.model_id:
                self.dismissed_task_ids.add(task.model_id)

            if task:
                if task.status in ["queued", "downloading"]:
                    task._cancel_flag = True
                    task.status = "cancelled"

                if delete_from_disk and task.save_path:
                    try:
                        part_file = task.save_path + ".part"
                        if os.path.exists(part_file):
                            os.remove(part_file)
                        from .model_inventory import delete_local_model
                        delete_local_model(task.save_path)
                    except Exception as ex:
                        log.warning(f"[ModelDownloader] Errore cancellazione file per #{task_id}: {ex}")

                del self.tasks[task_id]
                return True
            elif task_id.startswith("disk-"):
                if delete_from_disk:
                    try:
                        from .model_inventory import scan_local_models, delete_local_model
                        for m in scan_local_models(self.models_dir):
                            m_id = m.get("model_id") or m.get("filename")
                            clean_id = m_id.replace("/", "--").replace(":", "-").lower()
                            if f"disk-{clean_id}"[:16] == task_id or task_id.endswith(clean_id):
                                delete_local_model(m.get("path"))
                                break
                    except Exception as ex:
                        log.warning(f"[ModelDownloader] Errore rimozione modello su disco {task_id}: {ex}")
                return True
        return False

    def clear_completed_tasks(self) -> int:
        """Clears all completed, failed, or cancelled tasks from history."""
        count = 0
        with self.lock:
            to_remove = [tid for tid, t in self.tasks.items() if t.status in ["completed", "failed", "cancelled"]]
            for tid in to_remove:
                self.dismissed_task_ids.add(tid)
                task = self.tasks.pop(tid, None)
                if task and task.model_id:
                    self.dismissed_task_ids.add(task.model_id)
                count += 1
        return count

    def _sync_disk_models_to_tasks(self):
        """Scans disk models and ensures all completed downloaded models appear in download history."""
        try:
            from .model_inventory import scan_local_models
            local_models = scan_local_models(self.models_dir)
            for m in local_models:
                m_id = m.get("model_id") or m.get("filename")
                clean_id = m_id.replace("/", "--").replace(":", "-").lower()
                task_id = f"disk-{clean_id}"[:16]
                if task_id in self.dismissed_task_ids or m_id in self.dismissed_task_ids:
                    continue
                if task_id not in self.tasks and not any(t.model_id == m_id for t in self.tasks.values()):
                    size_bytes = int(m.get("size_gb", 0) * (1024**3))
                    mod_time = time.time()
                    try:
                        m_path = m.get("path")
                        if m_path and os.path.exists(m_path):
                            mod_time = os.path.getmtime(m_path)
                    except Exception:
                        pass
                    self.tasks[task_id] = ModelDownloadTask(
                        task_id=task_id,
                        model_id=m_id,
                        filename=m.get("filename") if not m.get("is_repo_folder") else f"{m_id} ({m.get('total_shards', 1)} file / shard)",
                        download_url="",
                        save_path=m.get("path"),
                        status="completed",
                        total_bytes=size_bytes,
                        downloaded_bytes=size_bytes,
                        progress_pct=100.0,
                        created_at=mod_time,
                        completed_at=mod_time,
                        is_repo_download=m.get("is_repo_folder", False),
                        files_queue=[{}] * m.get("total_shards", 1)
                    )
        except Exception as ex:
            log.debug(f"[ModelDownloader] Error syncing disk models: {ex}")

    def get_tasks(self) -> List[Dict[str, Any]]:
        with self.lock:
            self._sync_disk_models_to_tasks()
            return [t.to_dict() for t in self.tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            self._sync_disk_models_to_tasks()
            task = self.tasks.get(task_id)
            return task.to_dict() if task else None


    def _single_download_worker(self, task: ModelDownloadTask):
        """Worker thread executing streaming chunked HTTP download with auto-resume and retry loops."""
        task.status = "downloading"
        chunk_size = 1024 * 1024  # 1 MB
        temp_path = f"{task.save_path}.part"
        os.makedirs(os.path.dirname(task.save_path), exist_ok=True)
        max_retries = 6

        for attempt in range(1, max_retries + 1):
            if task._cancel_flag:
                task.status = "cancelled"
                return

            last_time = time.time()
            bytes_since_last_calc = 0

            try:
                existing_bytes = 0
                if os.path.exists(temp_path):
                    existing_bytes = os.path.getsize(temp_path)
                    task.downloaded_bytes = existing_bytes

                req = urllib.request.Request(task.download_url)
                req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
                token = task.hf_token
                if not token:
                    from .hf_client import get_effective_hf_token
                    token = get_effective_hf_token()
                    task.hf_token = token

                if token:
                    req.add_header("Authorization", f"Bearer {token}")
                if existing_bytes > 0:
                    req.add_header("Range", f"bytes={existing_bytes}-")

                with safe_urlopen(req, timeout=25) as response:
                    content_len = response.headers.get("Content-Length")
                    if content_len:
                        task.total_bytes = int(content_len) + existing_bytes
                    elif task.total_bytes == 0:
                        task.total_bytes = existing_bytes + (4 * 1024**3)

                    mode = "ab" if existing_bytes > 0 else "wb"
                    with open(temp_path, mode) as out_file:
                        while not task._cancel_flag:
                            chunk = response.read(chunk_size)
                            if not chunk:
                                break

                            out_file.write(chunk)
                            task.downloaded_bytes += len(chunk)
                            bytes_since_last_calc += len(chunk)

                            now = time.time()
                            dt = now - last_time
                            if dt >= 0.5:
                                task.speed_mbps = (bytes_since_last_calc / (1024**2)) / dt
                                bytes_since_last_calc = 0
                                last_time = now

                                if task.total_bytes > 0:
                                    task.progress_pct = min(99.9, (task.downloaded_bytes / task.total_bytes) * 100.0)
                                    rem_bytes = max(0, task.total_bytes - task.downloaded_bytes)
                                    if task.speed_mbps > 0:
                                        task.eta_seconds = rem_bytes / (task.speed_mbps * 1024**2)

                if task._cancel_flag:
                    task.status = "cancelled"
                    return

                # Successfully completed
                if os.path.exists(task.save_path):
                    os.remove(task.save_path)
                os.rename(temp_path, task.save_path)

                # Validate GGUF file integrity if applicable
                if task.save_path.lower().endswith(".gguf") and os.path.exists(task.save_path):
                    sz = os.path.getsize(task.save_path)
                    if sz < 1024:
                        with open(task.save_path, "rb") as _tf:
                            sample = _tf.read(256)
                        if b"git-lfs" in sample or sample.startswith(b"version https://git-lfs"):
                            raise Exception(f"File scaricato come puntatore Git-LFS anziché binario reale ({sz} byte).")
                    with open(task.save_path, "rb") as _tf:
                        if _tf.read(4) != b"GGUF":
                            raise Exception("File GGUF scaricato non valido (magic bytes errati).")

                task.status = "completed"
                task.progress_pct = 100.0
                task.completed_at = time.time()
                task.speed_mbps = 0.0
                task.eta_seconds = 0
                log.info(f"[ModelDownloader] Task {task.task_id} COMPLETED: {task.save_path}")
                return

            except urllib.error.HTTPError as ex:
                if ex.code in (401, 403):
                    auth_err = (
                        f"Autenticazione richiesta (HTTP {ex.code}): Il modello '{task.model_id}' "
                        f"richiede un Hugging Face Access Token valido e l'accettazione della licenza del modello su huggingface.co. "
                        f"Inserisci il tuo Token (read) nella scheda 'Directory & HF Token' di Model Hub."
                    )
                    task.status = "failed"
                    task.error_message = auth_err
                    log.error(f"[ModelDownloader] Task {task.task_id} AUTH ERROR: {auth_err}")
                    return

                log.warning(f"[ModelDownloader] HTTP error {ex.code} on {task.filename} (attempt {attempt}/{max_retries}): {ex}. Retrying with Range resume...")
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                else:
                    task.status = "failed"
                    task.error_message = f"Errore HTTP {ex.code} dopo {max_retries} tentativi: {ex}"
                    log.error(f"[ModelDownloader] Task {task.task_id} FAILED: {ex}")
                    return

            except (urllib.error.URLError, http.client.RemoteDisconnected, http.client.IncompleteRead,
                    TimeoutError, socket.timeout, ConnectionResetError, OSError) as ex:
                log.warning(f"[ModelDownloader] Transient error on {task.filename} (attempt {attempt}/{max_retries}): {ex}. Retrying with Range resume...")
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                else:
                    task.status = "failed"
                    task.error_message = f"Connessione interrotta dopo {max_retries} tentativi: {ex}"
                    log.error(f"[ModelDownloader] Task {task.task_id} FAILED: {ex}")
                    return
            except Exception as ex:
                task.status = "failed"
                task.error_message = str(ex)
                log.error(f"[ModelDownloader] Task {task.task_id} UNEXPECTED FAILURE: {ex}")
                return

    def _repo_download_worker(self, task: ModelDownloadTask, target_dir: str):
        """Worker thread that sequentially downloads all files/shards with disk skip, Range auto-resume and retry loops."""
        task.status = "downloading"
        chunk_size = 1024 * 1024
        total_files = len(task.files_queue)
        max_shard_retries = 6

        try:
            # 1. Pre-calculate total bytes & already downloaded bytes on disk
            already_done_bytes = 0
            file_sizes = {}
            for file_info in task.files_queue:
                fname = file_info.get("filename", "")
                save_file = os.path.join(target_dir, fname)
                part_file = f"{save_file}.part"
                os.makedirs(os.path.dirname(save_file), exist_ok=True)
                f_size = int(file_info.get("size", 0))
                if os.path.exists(save_file):
                    sz = os.path.getsize(save_file)
                    already_done_bytes += sz
                    file_sizes[fname] = max(sz, f_size)
                elif os.path.exists(part_file):
                    sz = os.path.getsize(part_file)
                    already_done_bytes += sz
                    file_sizes[fname] = max(sz, f_size)
                elif f_size > 0:
                    file_sizes[fname] = f_size

            sum_sizes = sum(file_sizes.values())
            if sum_sizes > 0:
                task.total_bytes = max(task.total_bytes, sum_sizes, already_done_bytes)
            elif task.total_bytes < already_done_bytes:
                task.total_bytes = max(already_done_bytes, int(len(task.files_queue) * 3.5 * (1024**3)))

            task.downloaded_bytes = already_done_bytes
            eff_total = max(task.total_bytes, task.downloaded_bytes)
            if eff_total > 0:
                task.progress_pct = min(99.9, (task.downloaded_bytes / eff_total) * 100.0)

            # 2. Iterate through each shard/file
            for idx, file_info in enumerate(task.files_queue):
                if task._cancel_flag:
                    break

                fname = file_info.get("filename", "")
                d_url = file_info.get("download_url") or f"https://huggingface.co/{task.model_id}/resolve/main/{fname}"
                save_file = os.path.join(target_dir, fname)
                temp_file = f"{save_file}.part"

                # Ensure nested subdirectory exists (e.g. encoding/tests/...)
                os.makedirs(os.path.dirname(save_file), exist_ok=True)

                task.current_file_idx = idx + 1
                task.current_file_name = fname

                # Check if this shard is ALREADY completely downloaded on disk
                if os.path.exists(save_file) and os.path.getsize(save_file) > 0:
                    log.info(f"[ModelDownloader] Repo {task.task_id}: Shard {idx+1}/{total_files} ({fname}) already on disk. Skipping.")
                    eff_tot = max(task.total_bytes, task.downloaded_bytes)
                    task.progress_pct = min(99.9, (task.downloaded_bytes / eff_tot) * 100.0) if eff_tot > 0 else min(99.9, ((idx + 1) / total_files) * 100.0)
                    continue

                # Shard download attempt loop with auto-recovery
                shard_success = False
                for attempt in range(1, max_shard_retries + 1):
                    if task._cancel_flag:
                        break

                    last_time = time.time()
                    bytes_since_last_calc = 0

                    try:
                        existing_bytes = 0
                        if os.path.exists(temp_file):
                            existing_bytes = os.path.getsize(temp_file)

                        req = urllib.request.Request(d_url)
                        req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
                        token = task.hf_token
                        if not token:
                            from .hf_client import get_effective_hf_token
                            token = get_effective_hf_token()
                            task.hf_token = token

                        if token:
                            req.add_header("Authorization", f"Bearer {token}")
                        if existing_bytes > 0:
                            req.add_header("Range", f"bytes={existing_bytes}-")

                        with safe_urlopen(req, timeout=30) as resp:
                            content_len = resp.headers.get("Content-Length")
                            if content_len:
                                f_real_total = int(content_len) + existing_bytes
                                file_sizes[fname] = f_real_total
                                new_total = sum(file_sizes.values())
                                if new_total > task.total_bytes:
                                    task.total_bytes = new_total

                            mode = "ab" if existing_bytes > 0 else "wb"
                            os.makedirs(os.path.dirname(temp_file), exist_ok=True)
                            with open(temp_file, mode) as out_f:
                                while not task._cancel_flag:
                                    chunk = resp.read(chunk_size)
                                    if not chunk:
                                        break
                                    out_f.write(chunk)
                                    task.downloaded_bytes += len(chunk)
                                    bytes_since_last_calc += len(chunk)

                                    now = time.time()
                                    dt = now - last_time
                                    if dt >= 0.5:
                                        task.speed_mbps = (bytes_since_last_calc / (1024**2)) / dt
                                        bytes_since_last_calc = 0
                                        last_time = now

                                        eff_total_dyn = max(task.total_bytes, task.downloaded_bytes)
                                        if eff_total_dyn > 0:
                                            task.progress_pct = min(99.9, (task.downloaded_bytes / eff_total_dyn) * 100.0)
                                            rem_bytes = max(0, eff_total_dyn - task.downloaded_bytes)
                                            if task.speed_mbps > 0:
                                                task.eta_seconds = rem_bytes / (task.speed_mbps * 1024**2)
                                        else:
                                            task.progress_pct = min(99.9, ((idx + 0.5) / total_files) * 100.0)

                        if task._cancel_flag:
                            break

                        # Rename completed .part file
                        if os.path.exists(save_file):
                            os.remove(save_file)
                        os.rename(temp_file, save_file)

                        # Validate GGUF shard if applicable
                        if fname.lower().endswith(".gguf") and os.path.exists(save_file):
                            sz = os.path.getsize(save_file)
                            if sz < 1024:
                                with open(save_file, "rb") as _tf:
                                    sample = _tf.read(256)
                                if b"git-lfs" in sample or sample.startswith(b"version https://git-lfs"):
                                    raise Exception(f"File {fname} scaricato come puntatore Git-LFS anziché binario reale ({sz} byte).")
                            with open(save_file, "rb") as _tf:
                                if _tf.read(4) != b"GGUF":
                                    raise Exception(f"File GGUF {fname} scaricato non valido (magic bytes errati).")

                        task.progress_pct = min(99.9, ((idx + 1) / total_files) * 100.0)
                        shard_success = True
                        break

                    except urllib.error.HTTPError as ex:
                        if ex.code in (401, 403):
                            auth_err = (
                                f"Autenticazione richiesta (HTTP {ex.code}): Il modello '{task.model_id}' "
                                f"richiede un Hugging Face Access Token valido e l'accettazione della licenza del modello su huggingface.co. "
                                f"Inserisci il tuo Token (read) nella scheda 'Directory & HF Token' di Model Hub."
                            )
                            task.status = "failed"
                            task.error_message = auth_err
                            log.error(f"[ModelDownloader] Repo Task {task.task_id} AUTH ERROR: {auth_err}")
                            return

                        log.warning(f"[ModelDownloader] HTTP error {ex.code} on shard {idx+1}/{total_files} ({fname}, attempt {attempt}/{max_shard_retries}): {ex}. Retrying with Range...")
                        if attempt < max_shard_retries:
                            time.sleep(2 * attempt)
                        else:
                            raise Exception(f"Errore HTTP {ex.code} su shard {idx+1}/{total_files} ({fname}): {ex}")

                    except (urllib.error.URLError, http.client.RemoteDisconnected, http.client.IncompleteRead,
                            TimeoutError, socket.timeout, ConnectionResetError, OSError) as ex:
                        log.warning(f"[ModelDownloader] Transient error on shard {idx+1}/{total_files} ({fname}, attempt {attempt}/{max_shard_retries}): {ex}. Retrying with Range...")
                        if attempt < max_shard_retries:
                            time.sleep(2 * attempt)
                        else:
                            raise Exception(f"Errore download shard {idx+1}/{total_files} ({fname}): {ex}")

                if not shard_success and not task._cancel_flag:
                    raise Exception(f"Impossibile completare lo shard {fname} dopo {max_shard_retries} tentativi.")

            if task._cancel_flag:
                task.status = "cancelled"
                log.info(f"[ModelDownloader] Repo Task {task.task_id} cancelled.")
                return

            task.status = "completed"
            task.progress_pct = 100.0
            task.completed_at = time.time()
            task.speed_mbps = 0.0
            task.eta_seconds = 0
            log.info(f"[ModelDownloader] Whole-Repo Task {task.task_id} COMPLETED for {task.model_id}!")

        except Exception as ex:
            task.status = "failed"
            task.error_message = str(ex)
            log.error(f"[ModelDownloader] Whole-Repo Task {task.task_id} FAILED: {ex}")


# Global singleton instance
downloader_manager = ModelDownloadManager()
