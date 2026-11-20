"""File-based locks for BTK workers (prevent duplicate runs)."""

from __future__ import annotations

import os
import time
from pathlib import Path

LOCK_DIR = Path(os.getenv("BTK_LOCK_DIR", Path.cwd() / ".locks"))
MAX_LOCK_AGE_SEC = 5 * 60


def acquire_lock(name: str) -> bool:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    path = LOCK_DIR / f"{name}.lock"
    if path.exists():
        age = time.time() - path.stat().st_mtime
        if age > MAX_LOCK_AGE_SEC:
            try:
                path.unlink()
            except OSError:
                pass
        else:
            return False
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w") as fh:
            fh.write(str(os.getpid()))
        return True
    except FileExistsError:
        return False


def release_lock(name: str) -> None:
    path = LOCK_DIR / f"{name}.lock"
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
