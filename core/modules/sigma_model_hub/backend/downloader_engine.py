# ==============================================================================
# core/modules/sigma_model_hub/backend/downloader_engine.py
# High-Speed Streaming Asynchronous Model Downloader with Multi-Shard & Whole-Repo Support
# ==============================================================================
from __future__ import annotations
import os
import sys
import time
import uuid
import threading
import urllib.request
from typing import Dict, Any, List, Optional
from core.logger import get_logger

log = get_logger(__name__)

# Default model download directory in Sigma Studio
DEFAULT_MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "data", "models")


class ModelDownloadTask:
    def __init__(
        self,
        task_id: str,
        model_id: str,
        filename: str,
        download_url: str,
        save_path: str,
        hf_token: Optional[str] = None,
        files_queue: Optional[List[Dict[str, str]]] = None
    ):
        self.task_id = task_id
        self.model_id = model_id
        self.filename = filename
        self.download_url = download_url
        self.save_path = save_path
        self.hf_token = hf_token
        self.files_queue = files_queue or []
        self.is_repo_download = len(self.files_queue) > 1

        self.status = "queued"  # queued, downloading, completed, failed, cancelled
        self.total_bytes = 0
        self.downloaded_bytes = 0
        self.speed_mbps = 0.0
        self.progress_pct = 0.0
        self.eta_seconds = 0
        self.current_file_name = filename
        self.current_file_idx = 1
        self.total_files = max(1, len(self.files_queue))
        self.error_message: Optional[str] = None
        self.created_at = time.time()
        self.completed_at: Optional[float] = None
        self._cancel_flag = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "model_id": self.model_id,
            "filename": self.filename,
            "current_file_name": self.current_file_name,
            "current_file_idx": self.current_file_idx,
            "total_files": self.total_files,
            "is_repo_download": self.is_repo_download,
            "save_path": self.save_path,
            "status": self.status,
            "total_bytes": self.total_bytes,
            "total_mb": round(self.total_bytes / (1024**2), 1) if self.total_bytes else 0,
            "downloaded_bytes": self.downloaded_bytes,
            "downloaded_mb": round(self.downloaded_bytes / (1024**2), 1),
            "progress_pct": round(self.progress_pct, 1),
            "speed_mbps": round(self.speed_mbps, 2),
            "eta_seconds": int(self.eta_seconds),
            "error_message": self.error_message,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


class ModelDownloadManager:
    """Manages single-file and multi-shard whole-model download jobs."""

    def __init__(self, models_dir: str = DEFAULT_MODELS_DIR):
        self.models_dir = models_dir
        os.makedirs(self.models_dir, exist_ok=True)
        self.tasks: Dict[str, ModelDownloadTask] = {}
        self.lock = threading.Lock()

    def start_download(
        self,
        model_id: str,
        filename: str,
        download_url: Optional[str] = None,
        hf_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Starts a background single-file download task."""
        if not download_url:
            download_url = f"https://huggingface.co/{model_id}/resolve/main/{filename}"

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

        # Launch worker thread
        t = threading.Thread(target=self._single_download_worker, args=(task,), daemon=True)
        t.start()

        log.info(f"[ModelDownloader] Task {task_id} launched for {model_id}/{filename}")
        return task.to_dict()

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
            # Fallback single model.safetensors
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

        # Launch whole-repo worker thread
        t = threading.Thread(target=self._repo_download_worker, args=(task, target_dir), daemon=True)
        t.start()

        log.info(f"[ModelDownloader] Whole-Repo task {task_id} launched for {model_id} ({len(files_list)} files)")
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

    def get_tasks(self) -> List[Dict[str, Any]]:
        """Returns all download tasks."""
        with self.lock:
            return [t.to_dict() for t in self.tasks.values()]

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self.lock:
            task = self.tasks.get(task_id)
            return task.to_dict() if task else None

    def _single_download_worker(self, task: ModelDownloadTask):
        """Worker thread executing streaming chunked HTTP download for a single file."""
        task.status = "downloading"
        chunk_size = 1024 * 1024  # 1 MB chunks
        last_time = time.time()
        bytes_since_last_calc = 0

        temp_path = f"{task.save_path}.part"

        try:
            req = urllib.request.Request(task.download_url)
            req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
            if task.hf_token:
                req.add_header("Authorization", f"Bearer {task.hf_token}")

            # Check if partial file exists for resume
            existing_bytes = 0
            if os.path.exists(temp_path):
                existing_bytes = os.path.getsize(temp_path)
                if existing_bytes > 0:
                    req.add_header("Range", f"bytes={existing_bytes}-")
                    task.downloaded_bytes = existing_bytes

            with urllib.request.urlopen(req, timeout=15) as response:
                content_len = response.headers.get("Content-Length")
                if content_len:
                    task.total_bytes = int(content_len) + existing_bytes
                else:
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
                        if dt >= 0.8:
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
                log.info(f"[ModelDownloader] Task {task.task_id} cancelled.")
                return

            # Rename .part to final filename
            if os.path.exists(task.save_path):
                os.remove(task.save_path)
            os.rename(temp_path, task.save_path)

            task.status = "completed"
            task.progress_pct = 100.0
            task.completed_at = time.time()
            task.speed_mbps = 0.0
            task.eta_seconds = 0
            log.info(f"[ModelDownloader] Task {task.task_id} COMPLETED: {task.save_path}")

        except Exception as ex:
            task.status = "failed"
            task.error_message = str(ex)
            log.error(f"[ModelDownloader] Task {task.task_id} FAILED: {ex}")

    def _repo_download_worker(self, task: ModelDownloadTask, target_dir: str):
        """Worker thread that sequentially downloads all files/shards of a complete repository."""
        task.status = "downloading"
        chunk_size = 1024 * 1024
        total_files = len(task.files_queue)
        last_time = time.time()
        bytes_since_last_calc = 0

        try:
            # Estimate combined total bytes (or approx 5GB per shard)
            task.total_bytes = sum(
                (5 * 1024**3 if f.get("filename", "").endswith(".safetensors") else 2 * 1024**2)
                for f in task.files_queue
            )

            for idx, file_info in enumerate(task.files_queue):
                if task._cancel_flag:
                    break

                fname = file_info.get("filename", "")
                d_url = file_info.get("download_url") or f"https://huggingface.co/{task.model_id}/resolve/main/{fname}"
                save_file = os.path.join(target_dir, fname)
                temp_file = f"{save_file}.part"

                task.current_file_idx = idx + 1
                task.current_file_name = fname
                log.info(f"[ModelDownloader] Repo {task.task_id}: Downloading {idx+1}/{total_files} ({fname})...")

                req = urllib.request.Request(d_url)
                req.add_header("User-Agent", "SigmaStudio-ModelHub/2.0")
                if task.hf_token:
                    req.add_header("Authorization", f"Bearer {task.hf_token}")

                existing_bytes = 0
                if os.path.exists(temp_file):
                    existing_bytes = os.path.getsize(temp_file)
                    if existing_bytes > 0:
                        req.add_header("Range", f"bytes={existing_bytes}-")
                        task.downloaded_bytes += existing_bytes

                with urllib.request.urlopen(req, timeout=20) as resp:
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
                            if dt >= 0.6:
                                task.speed_mbps = (bytes_since_last_calc / (1024**2)) / dt
                                bytes_since_last_calc = 0
                                last_time = now

                                # Calculate weighted percentage across all shards
                                if task.total_bytes > 0:
                                    task.progress_pct = min(99.9, (task.downloaded_bytes / task.total_bytes) * 100.0)
                                else:
                                    task.progress_pct = min(99.9, ((idx + 0.5) / total_files) * 100.0)

                                if task.speed_mbps > 0 and task.total_bytes > task.downloaded_bytes:
                                    task.eta_seconds = (task.total_bytes - task.downloaded_bytes) / (task.speed_mbps * 1024**2)

                if task._cancel_flag:
                    break

                if os.path.exists(save_file):
                    os.remove(save_file)
                os.rename(temp_file, save_file)
                # Mark completed shard ratio
                task.progress_pct = min(99.9, ((idx + 1) / total_files) * 100.0)


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
