"""Advisory lock marking an in-flight scan.

flock is used rather than a pidfile so the lock dies with the process — a
scan killed mid-run can never leave the supervisor permanently deferred.
"""

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path

LOCK_PATH = Path(os.environ.get("BROTHER_RUNDIR", "/run/brother")) / "scan.lock"


def _open_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    return os.open(LOCK_PATH, os.O_CREAT | os.O_RDWR, 0o644)


@contextmanager
def scan_lock():
    fd = _open_lock()
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)


def scan_in_progress():
    try:
        fd = _open_lock()
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)
