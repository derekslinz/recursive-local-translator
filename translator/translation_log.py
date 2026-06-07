import json
import threading
import time
from pathlib import Path


class TranslationLog:
    def __init__(self, path: str):
        self._path = Path(path)
        self._lock = threading.Lock()
        # Append mode — survives multiple runs
        self._fh = self._path.open("a", encoding="utf-8")

    def log_rename(self, old: Path, new: Path) -> None:
        self._write({"event": "rename", "old": str(old), "new": str(new), "ts": time.time()})

    def log_content(self, path: Path, kind: str) -> None:
        self._write({"event": "content", "path": str(path), "kind": kind, "ts": time.time()})

    def log_sidecar(self, source: Path, sidecar: Path) -> None:
        self._write({"event": "sidecar", "source": str(source), "sidecar": str(sidecar), "ts": time.time()})

    def _write(self, record: dict) -> None:
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            self._fh.write(line + "\n")
            self._fh.flush()

    def close(self) -> None:
        with self._lock:
            self._fh.close()
