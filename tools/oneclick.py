# oneclick.py - one-click launcher core for the TRAE CN relay.
# Called by launch.vbs (hidden via pythonw, desktop shortcut) and
# start-trae2api.cmd (console via python). Ensures the relay (8092) and OAuth
# helper (8765) are running, waits for health, then opens the admin console in
# a Chrome app window.
#
# Every process in the hidden path must be GUI-subsystem: a console binary
# here would flash a Windows Terminal window even when started hidden, because
# the default-terminal handoff ignores SW_HIDE. The venv's pythonw.exe cannot
# be used - the 3.13 venv launcher stub re-execs the base python.exe (console
# subsystem) as its child, which pops a real terminal window. So the base
# pythonw.exe runs the services directly with the venv site-packages on
# PYTHONPATH. ASCII output only - cmd callers may read this file with a
# legacy codepage.

import os
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV_HOME = ""  # base interpreter dir from pyvenv.cfg; set in main()
RELAY_HEALTH = "http://127.0.0.1:8092/healthz"
HELPER_HEALTH = "http://127.0.0.1:8765/healthz"
DATA = os.path.join(BASE, "data")
ADMIN_URL = "http://127.0.0.1:8092/web/login"
ADMIN_PROFILE = os.path.join(DATA, "admin-profile")


def read_venv_home():
    """Base interpreter dir from pyvenv.cfg; empty when unavailable."""
    path = os.path.join(BASE, ".venv", "pyvenv.cfg")
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.lower().startswith("home"):
                    _, _, value = line.partition("=")
                    return value.strip().strip('"')
    except OSError:
        pass
    return ""


def windowless_pythonw():
    """GUI-subsystem interpreter for the services, or None to fall back."""
    candidate = os.path.join(VENV_HOME, "pythonw.exe")
    return candidate if VENV_HOME and os.path.isfile(candidate) else None


def log(msg):
    # pythonw has no stdout; the console twin (python.exe) prints.
    if sys.stdout is not None:
        print(msg, flush=True)


def healthy(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def spawn_hidden(args, log_name):
    out = open(os.path.join(DATA, log_name + "-stdout.log"), "ab")
    err = open(os.path.join(DATA, log_name + "-stderr.log"), "ab")
    flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
    subprocess.Popen(args, cwd=BASE, stdout=out, stderr=err, creationflags=flags)


def spawn_service(script_args, log_name):
    """Start a service on the GUI interpreter; fall back to the venv stub."""
    pyw = windowless_pythonw()
    if pyw:
        site = os.path.join(BASE, ".venv", "Lib", "site-packages")
        env = dict(os.environ)
        env["PYTHONPATH"] = site + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
        out = open(os.path.join(DATA, log_name + "-stdout.log"), "ab")
        err = open(os.path.join(DATA, log_name + "-stderr.log"), "ab")
        flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        subprocess.Popen([pyw] + script_args, cwd=BASE, stdout=out, stderr=err,
                         creationflags=flags, env=env)
    else:
        log("[trae2api] WARNING: base pythonw not found, falling back to venv stub")
        spawn_hidden([os.path.join(BASE, ".venv", "Scripts", "pythonw.exe")] + script_args,
                     log_name)


def main():
    global VENV_HOME
    # --no-open: ensure services only, do not touch the console window.
    # The watchdog uses this so a respawn never steals focus or stacks windows.
    no_open = "--no-open" in sys.argv[1:]
    VENV_HOME = read_venv_home()
    if not os.path.isfile(os.path.join(BASE, ".venv", "Scripts", "pythonw.exe")):
        log("[trae2api] python venv not found: .venv\\Scripts\\pythonw.exe")
        return 1
    os.makedirs(DATA, exist_ok=True)

    if healthy(RELAY_HEALTH):
        log("[trae2api] relay already running.")
    else:
        log("[trae2api] relay starting on http://127.0.0.1:8092 ...")
        spawn_service(
            ["-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", "8092"],
            "relay",
        )

    if healthy(HELPER_HEALTH):
        log("[trae2api] login helper already running.")
    else:
        log("[trae2api] login helper starting on http://127.0.0.1:8765 ...")
        spawn_service(
            [os.path.join(BASE, "web_login.py"),
             "--relay", "http://127.0.0.1:8092", "--port", "8765", "--no-open"],
            "login-helper",
        )

    up = False
    for _ in range(20):
        time.sleep(1)
        if healthy(RELAY_HEALTH):
            up = True
            break
    if not up:
        log("[trae2api] FAILED: relay did not become healthy within 20s. Check data\\relay-stderr.log")
        return 1
    log("[trae2api] relay healthy.")

    if no_open:
        return 0

    # Console in a Chrome app window (frameless, isolated profile). The marker
    # flag survives on the command line so stop-trae2api-helper.ps1 can close
    # the window when the service stops. Chrome ignores unknown flags.
    chrome = ""
    for p in (
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
    ):
        if os.path.isfile(p):
            chrome = p
            break
    if chrome:
        subprocess.Popen(
            [chrome, "--user-data-dir=" + ADMIN_PROFILE, "--trae2api-admin-window",
             "--no-first-run", "--no-default-browser-check", "--app=" + ADMIN_URL]
        )
        log("[trae2api] console opened.")
    else:
        os.startfile(ADMIN_URL)  # default browser fallback (GUI, no console)
        log("[trae2api] console opened in default browser (Chrome not found).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
