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

log = get_logger(__name__)

DEFAULT_MODELS_DIR = os.path.join(os.getcwd(), "data", "models")


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
        return {
            "task_id": self.task_id,
            "model_id": self.model_id,
            "filename": self.filename,
            "download_url": self.download_url,
            "save_path": self.save_path,
            "status": self.status,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "total_mb": round(self.total_bytes / (1024**2), 1) if self.total_bytes > 0 else 0,
            "downloaded_mb": round(self.downloaded_bytes / (1024**2), 1),
            "speed_mbps": round(self.speed_mbps, 2),
            "progress_pct": round(self.progress_pct, 1),
            "eta_seconds": int(self.eta_seconds),
            "created_at": self.created_at,
            "completed_at": self.completed_at,
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
        self.lock = threading.Lock()

    def set_models_dir(self, new_dir: str):
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

        task_id = str(uuid.uuid4())[:8]
        display_name = f"Intero Modello ({len(files_list)} file / shard)"
        task = ModelDownloadTask(
            task_id=task_id,
            model_id=model_id,
            filename=display_name,
            download_url="",
            save_path=target_dir,
            hf_token=hf_token,
            files_queue=files_list
        )

        with self.lock:
            self.tasks[task_id] = task

        t = threading.Thread(target=self._repo_download_worker, args=(task, target_dir), daemon=True)
        t.start()

        log.info(f"[ModelDownloader] Whole-Repo task {task_id} launched for {model_id} ({len(files_list)} files)")
        return task.to_dict()

    def retry_download(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Resumes/Retries a failed or cancelled download task from where it left off."""
        with self.lock:
            task = self.tasks.get(task_id)
            if not task:
                return None

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
            if task and task.status in ["queued", "downloading"]:
                task._cancel_flag = True
                task.status = "cancelled"
                return True
        return False

    def remove_task(self, task_id: str) -> bool:
        """Removes a task from the list."""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                return True
        return False

    def get_tasks(self) -> List[Dict[str, Any]]:
        with self.lock:
            return [t.to_dict() for t in self.tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            task = self.tasks.get(task_id)
            return task.to_dict() if task else None

    def _single_download_worker(self, task: ModelDownloadTask):
        """Worker thread executing streaming chunked HTTP download with auto-resume and retry loops."""
        task.status = "downloading"
        chunk_size = 1024 * 1024  # 1 MB
        temp_path = f"{task.save_path}.part"
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
                if task.hf_token:
                    req.add_header("Authorization", f"Bearer {task.hf_token}")
                if existing_bytes > 0:
                    req.add_header("Range", f"bytes={existing_bytes}-")

                with urllib.request.urlopen(req, timeout=25) as response:
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

                task.status = "completed"
                task.progress_pct = 100.0
                task.completed_at = time.time()
                task.speed_mbps = 0.0
                task.eta_seconds = 0
                log.info(f"[ModelDownloader] Task {task.task_id} COMPLETED: {task.save_path}")
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
            for file_info in task.files_queue:
                fname = file_info.get("filename", "")
                save_file = os.path.join(target_dir, fname)
                part_file = f"{save_file}.part"
                if os.path.exists(save_file):
                    already_done_bytes += os.path.getsize(save_file)
                elif os.path.exists(part_file):
                    already_done_bytes += os.path.getsize(part_file)

            if task.total_bytes == 0:
                task.total_bytes = max(
                    already_done_bytes,
                    sum((5 * 1024**3 if f.get("filename", "").endswith(".safetensors") else 2 * 1024**2) for f in task.files_queue)
                )

            task.downloaded_bytes = already_done_bytes

            # 2. Iterate through each shard/file
            for idx, file_info in enumerate(task.files_queue):
                if task._cancel_flag:
                    break

                fname = file_info.get("filename", "")
                d_url = file_info.get("download_url") or f"https://huggingface.co/{task.model_id}/resolve/main/{fname}"
                save_file = os.path.join(target_dir, fname)
                temp_file = f"{save_file}.part"

                task.current_file_idx = idx + 1
                task.current_file_name = fname

                # Check if this shard is ALREADY completely downloaded on disk
                if os.path.exists(save_file) and os.path.getsize(save_file) > 0:
                    log.info(f"[ModelDownloader] Repo {task.task_id}: Shard {idx+1}/{total_files} ({fname}) already on disk. Skipping.")
                    task.progress_pct = min(99.9, ((idx + 1) / total_files) * 100.0)
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
                        if task.hf_token:
                            req.add_header("Authorization", f"Bearer {task.hf_token}")
                        if existing_bytes > 0:
                            req.add_header("Range", f"bytes={existing_bytes}-")

                        with urllib.request.urlopen(req, timeout=30) as resp:
                            mode = "ab" if existing_bytes > 0 else "wb"
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

                                        if task.total_bytes > 0:
                                            task.progress_pct = min(99.9, (task.downloaded_bytes / task.total_bytes) * 100.0)
                                        else:
                                            task.progress_pct = min(99.9, ((idx + 0.5) / total_files) * 100.0)

                                        if task.speed_mbps > 0 and task.total_bytes > task.downloaded_bytes:
                                            task.eta_seconds = (task.total_bytes - task.downloaded_bytes) / (task.speed_mbps * 1024**2)

                        if task._cancel_flag:
                            break

                        # Rename completed .part file
                        if os.path.exists(save_file):
                            os.remove(save_file)
                        os.rename(temp_file, save_file)
                        task.progress_pct = min(99.9, ((idx + 1) / total_files) * 100.0)
                        shard_success = True
                        break

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
