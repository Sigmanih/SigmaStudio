"""Registro limitato degli eventi per ricollegare una chat senza rieseguire il lavoro."""
import json
import tempfile
import threading
import uuid


class RunEvents:
    def __init__(self, max_bytes=64 * 1024 * 1024, run_id=None):
        self.run_id = uuid.UUID(run_id).hex if run_id else uuid.uuid4().hex
        self.cancel = threading.Event()
        self.finished = threading.Event()
        self._file = tempfile.SpooledTemporaryFile(max_size=1024 * 1024)
        self._lock = threading.RLock()
        self._offsets = [0]
        self._max_bytes = max_bytes

    def append(self, event):
        raw = (json.dumps(event, ensure_ascii=False) + '\n').encode('utf-8')
        with self._lock:
            allowance = 4096 if event.get('type') == 'error' else 0
            if self._offsets[-1] + len(raw) > self._max_bytes + allowance:
                raise RuntimeError('Registro eventi pieno: run interrotto senza perdere eventi precedenti')
            self._file.seek(self._offsets[-1])
            self._file.write(raw)
            self._offsets.append(self._file.tell())

    def read(self, after=0, limit=256):
        with self._lock:
            end = min(len(self._offsets) - 1, after + limit)
            if after < 0 or after >= len(self._offsets):
                raise ValueError('Cursore eventi non valido')
            self._file.seek(self._offsets[after])
            return [dict(json.loads(self._file.readline()), event_id=i + 1,
                         run_id=self.run_id) for i in range(after, end)]

    def close(self):
        with self._lock:
            self._file.close()
