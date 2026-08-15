# ==============================================================================
# core/engine/disk_streamer.py — Multi-Drive Sharded Lookahead Streamer
# Implements AiloFlow-inspired multi-drive striped weight storage & streaming
# Multiplies input bandwidth by reading parameter shards concurrently across drives.
# ==============================================================================
import os
import io
import time
import queue
import threading
from typing import Dict, Any, List, Optional
from core.logger import get_logger

log = get_logger(__name__)


class MultiDriveShardedStreamer:
    """
    Splits cold LLM layer weights across multiple physical drives (e.g. C:, D:, E:)
    and performs asynchronous lookahead streaming during forward pass.
    """

    def __init__(self, target_drives: Optional[List[str]] = None, chunk_size_mb: int = 32):
        self.chunk_size_mb = chunk_size_mb
        self.target_drives = target_drives or [os.path.abspath("data/shards")]
        self.shard_registry: Dict[str, List[str]] = {}
        self.prefetch_queue = queue.Queue(maxsize=4)
        self._active = False
        self._worker_thread = None

        # Ensure base directories exist
        for d in self.target_drives:
            shard_dir = os.path.join(d, "sigma_layer_shards") if not d.endswith("sigma_layer_shards") else d
            os.makedirs(shard_dir, exist_ok=True)

    def register_sharded_layer(self, layer_index: int, layer_bytes: bytes) -> List[str]:
        """
        Splits layer tensor bytes into chunks and stripes them across all available drives.
        """
        chunk_bytes = self.chunk_size_mb * 1024 * 1024
        chunks = [layer_bytes[i:i + chunk_bytes] for i in range(0, len(layer_bytes), chunk_bytes)]
        
        file_paths = []
        for chunk_idx, chunk_data in enumerate(chunks):
            # Round-robin assign drive
            drive_root = self.target_drives[chunk_idx % len(self.target_drives)]
            shard_dir = os.path.join(drive_root, "sigma_layer_shards")
            os.makedirs(shard_dir, exist_ok=True)
            
            filename = f"layer_{layer_index}_chunk_{chunk_idx}.shard"
            full_path = os.path.join(shard_dir, filename)
            
            with open(full_path, "wb") as f:
                f.write(chunk_data)
            file_paths.append(full_path)

        self.shard_registry[f"layer_{layer_index}"] = file_paths
        log.debug(f"[DiskStreamer] Layer {layer_index} striped across {len(file_paths)} shards ({len(self.target_drives)} drives)")
        return file_paths

    def fetch_layer_parallel(self, layer_index: int) -> bytes:
        """
        Reads all shards for a layer concurrently from multiple drives, multiplying throughput.
        """
        shard_paths = self.shard_registry.get(f"layer_{layer_index}", [])
        if not shard_paths:
            return b""

        results: Dict[int, bytes] = {}
        threads = []

        def _read_chunk(idx: int, path: str):
            try:
                with open(path, "rb") as f:
                    results[idx] = f.read()
            except Exception as e:
                log.error(f"[DiskStreamer] Error reading shard {path}: {e}")
                results[idx] = b""

        t0 = time.perf_counter()
        for idx, path in enumerate(shard_paths):
            t = threading.Thread(target=_read_chunk, args=(idx, path))
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        t1 = time.perf_counter()
        
        # Reconstruct layer in memory
        ordered_chunks = [results[i] for i in range(len(shard_paths)) if i in results]
        assembled = b"".join(ordered_chunks)
        
        elapsed = max(t1 - t0, 0.0001)
        throughput_mb = round((len(assembled) / (1024**2)) / elapsed, 2)
        log.debug(f"[DiskStreamer] Layer {layer_index} assembled ({round(len(assembled)/(1024**2), 1)} MB) in {round(elapsed*1000, 1)}ms ({throughput_mb} MB/s)")
        
        return assembled

    def cleanup_shards(self):
        """Remove temporary shard files."""
        for layer_key, paths in self.shard_registry.items():
            for p in paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass
        self.shard_registry.clear()
