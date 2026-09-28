# respawn.py - detached helper for /api/restart.
# Started by the running relay just before it exits: waits for the old
# process to free port 8092, then starts a fresh uvicorn relay with output
# redirected into the relay log files. Exits immediately after the spawn.
import os
import socket
import subprocess
import sys
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(BASE, ".venv", "Scripts", "python.exe")
PORT = 8092


def port_busy() -> bool:
    s = socket.socket()
    s.settimeout(0.5)
    try:
        s.connect(("127.0.0.1", PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main() -> None:
    time.sleep(2.5)
    for _ in range(30):
        if not port_busy():
            break
        time.sleep(0.5)
    log = open(os.path.join(BASE, "data", "relay-stdout.log"), "ab")
    err = open(os.path.join(BASE, "data", "relay-stderr.log"), "ab")
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    if hasattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB"):
        flags |= subprocess.CREATE_BREAKAWAY_FROM_JOB
    try:
        subprocess.Popen(
            [PY, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=BASE,
            stdout=log,
            stderr=err,
            creationflags=flags,
        )
    except OSError:
        subprocess.Popen(
            [PY, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=BASE,
            stdout=log,
            stderr=err,
        )


if __name__ == "__main__":
    main()
