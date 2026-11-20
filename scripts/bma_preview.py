#!/usr/bin/env python3
"""Previews: the places where the user can try the app right now. Standard library only.

Claude records one whenever it has the app running for the user to try (after a feature is
verified, in QA, for a release candidate). The web UI shows an "Open app" button for each live one.

  bma_preview.py add --kind web     --target http://localhost:5173 --label "Dev build after F-004" [--cmd "npm run dev"] [--pid 123] [--screenshot shot.png]
  bma_preview.py add --kind api     --target http://localhost:8000/docs --label "API docs"
  bma_preview.py add --kind ios     --target com.example.habits --label "Simulator · dev build" [--screenshot shot.png]
  bma_preview.py add --kind android --target com.example.habits --label "Emulator · dev build"
  bma_preview.py list [--json]      Previews with whether each is alive
  bma_preview.py remove <id>|--all
  bma_preview.py open <id>          Bring it up (web/api: prints the URL)
  bma_preview.py shot <id>          Refresh the screenshot (iOS Simulator / Android emulator)

Safety: web and API targets must be on this machine (localhost); iOS and Android targets must be
plain app identifiers. Opening runs fixed commands filled in from the record, never free text.
A preview of the same kind and target replaces the older one.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bma_events import append, clip, ui_dir, ui_enabled  # noqa: E402

KINDS = ("web", "api", "ios", "android")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "[::1]"}
APP_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z0-9_-]+)+$")
MAX_PREVIEWS = 6


def root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def store(r: Path) -> Path:
    return r / ".build-my-app" / "previews.json"


def shots_dir(r: Path) -> Path:
    return r / ".build-my-app" / "previews"


def load(r: Path) -> list[dict]:
    try:
        return json.loads(store(r).read_text())
    except (FileNotFoundError, ValueError):
        return []


def save(r: Path, items: list[dict]) -> None:
    p = store(r)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, indent=2, ensure_ascii=False))
    os.replace(tmp, p)


def check_target(kind: str, target: str) -> str | None:
    """Why the target is not allowed, or None."""
    if kind in ("web", "api"):
        u = urlparse(target)
        if u.scheme not in ("http", "https") or (u.hostname or "") not in LOCAL_HOSTS:
            return "Web and API previews must be http(s) URLs on this machine (localhost or 127.0.0.1)."
        return None
    if not APP_ID.match(target) or len(target) > 200:
        return "iOS and Android previews need the app's bundle id or package name, like com.example.app."
    return None


def run(argv: list[str], timeout: float = 8) -> subprocess.CompletedProcess | None:
    if not shutil.which(argv[0]):
        return None
    try:
        return subprocess.run(argv, capture_output=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None


def proc_start(pid: int) -> str | None:
    r = run(["ps", "-o", "lstart=", "-p", str(pid)], 3)
    out = r.stdout.decode().strip() if r and r.returncode == 0 else ""
    return out or None


# -- liveness -----------------------------------------------------------------------------

def port_open(target: str) -> bool:
    u = urlparse(target)
    port = u.port or (443 if u.scheme == "https" else 80)
    host = "127.0.0.1" if u.hostname in ("localhost", "127.0.0.1") else "::1"
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False


def ios_state(bundle: str) -> str:
    r = run(["xcrun", "simctl", "list", "devices", "booted", "-j"])
    if r is None or r.returncode != 0:  # no xcrun, or only the Command Line Tools (no simctl)
        return "no Xcode tools"
    try:
        booted = [d for ds in json.loads(r.stdout)["devices"].values() for d in ds if d.get("state") == "Booted"]
    except (ValueError, KeyError):
        booted = []
    if not booted:
        return "simulator off"
    c = run(["xcrun", "simctl", "get_app_container", "booted", bundle])
    return "running" if c and c.returncode == 0 else "not installed"


def android_state(package: str) -> str:
    r = run(["adb", "get-state"], 4)
    if r is None:
        return "no Android tools"
    if r.returncode != 0 or b"device" not in r.stdout:
        return "emulator off"
    p = run(["adb", "shell", "pm", "path", package], 6)
    return "running" if p and p.returncode == 0 and p.stdout.strip() else "not installed"


def state_of(p: dict) -> str:
    """"running" when the user can open it now; otherwise a short reason."""
    if p["kind"] in ("web", "api"):
        return "running" if port_open(p["target"]) else "stopped"
    return ios_state(p["target"]) if p["kind"] == "ios" else android_state(p["target"])


# -- actions ------------------------------------------------------------------------------

def take_shot(r: Path, p: dict) -> bool:
    out = shots_dir(r) / f"{p['id']}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp.png")
    if p["kind"] == "ios":
        res = run(["xcrun", "simctl", "io", "booted", "screenshot", "--type=png", str(tmp)], 15)
        ok = bool(res and res.returncode == 0 and tmp.exists())
    elif p["kind"] == "android":
        res = run(["adb", "exec-out", "screencap", "-p"], 15)
        ok = bool(res and res.returncode == 0 and res.stdout.startswith(b"\x89PNG"))
        if ok:
            tmp.write_bytes(res.stdout)
    else:
        return False
    if ok:
        os.replace(tmp, out)
        p["shot_at"] = time.time()
    return ok


def open_preview(r: Path, p: dict) -> tuple[bool, str]:
    """Bring the preview up. Returns (ok, message or URL)."""
    if p["kind"] in ("web", "api"):
        return (True, p["target"]) if port_open(p["target"]) else (False, "The preview isn't running. Ask Claude to restart it.")
    if p["kind"] == "ios":
        if ios_state(p["target"]) != "running":
            return False, "The app isn't on a booted simulator. Ask Claude to restart the preview."
        run(["open", "-a", "Simulator"], 5)
        res = run(["xcrun", "simctl", "launch", "booted", p["target"]], 20)
        if not res or res.returncode != 0:
            return False, "The Simulator didn't launch the app."
    else:
        if android_state(p["target"]) != "running":
            return False, "The app isn't on a running emulator. Ask Claude to restart the preview."
        res = run(["adb", "shell", "monkey", "-p", p["target"], "-c", "android.intent.category.LAUNCHER", "1"], 15)
        if not res or res.returncode != 0:
            return False, "The emulator didn't start the app."
    time.sleep(1.5)
    take_shot(r, p)
    return True, "Opened in the " + ("Simulator." if p["kind"] == "ios" else "emulator.")


def stop_owned(r: Path, p: dict) -> bool:
    """Stop the preview's server if Claude recorded its pid and it is still that same process."""
    pid, started = p.get("pid"), p.get("pid_start")
    if not pid or not started or proc_start(pid) != started:
        return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def git_head(r: Path) -> str | None:
    res = run(["git", "-C", str(r), "rev-parse", "--short", "HEAD"], 3)
    return res.stdout.decode().strip() if res and res.returncode == 0 else None


# -- CLI ------------------------------------------------------------------------------------

def cmd_add(a, r: Path) -> None:
    if not (r / ".build-my-app" / "state.json").exists():
        sys.exit("Not a build-my-app project.")
    why = check_target(a.kind, a.target)
    if why:
        sys.exit(why)
    items = [p for p in load(r) if not (p["kind"] == a.kind and p["target"] == a.target)]
    pid = a.pid if a.pid and a.pid > 1 else None
    p = {"id": f"{a.kind}-{int(time.time()) % 10**6}", "kind": a.kind, "target": a.target,
         "label": clip(a.label or {"web": "Web app", "api": "API", "ios": "iOS app", "android": "Android app"}[a.kind], 80),
         "cmd": clip(a.cmd, 200) if a.cmd else None, "commit": git_head(r), "added": time.time(),
         "pid": pid, "pid_start": proc_start(pid) if pid else None}
    if a.screenshot:
        src = Path(a.screenshot)
        if src.suffix.lower() == ".png" and src.is_file() and src.stat().st_size < 8 * 1024 * 1024:
            shots_dir(r).mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, shots_dir(r) / f"{p['id']}.png")
            p["shot_at"] = time.time()
        else:
            print("Screenshot skipped: give a PNG file under 8 MB.", file=sys.stderr)
    items = ([p] + items)[:MAX_PREVIEWS]
    save(r, items)
    if ui_enabled(r):
        append(r, {"ev": "preview", "id": p["id"], "kind": p["kind"], "label": p["label"]})
    print(f"{p['id']}: {p['label']} ({state_of(p)})")


def cmd_list(a, r: Path) -> None:
    items = load(r)
    if a.json:
        print(json.dumps([{**p, "state": state_of(p)} for p in items], indent=2, ensure_ascii=False))
        return
    for p in items:
        print(f"{p['id']}  {p['kind']:<7} {state_of(p):<14} {p['label']}  ({p['target']})")
    if not items:
        print("No previews recorded.")


def cmd_remove(a, r: Path) -> None:
    items = load(r)
    keep = [] if a.all else [p for p in items if p["id"] != a.id]
    for p in items:
        if p not in keep:
            (shots_dir(r) / f"{p['id']}.png").unlink(missing_ok=True)
    save(r, keep)
    print(f"Removed {len(items) - len(keep)} preview(s).")


def find(r: Path, pid: str) -> tuple[list[dict], dict]:
    items = load(r)
    p = next((p for p in items if p["id"] == pid), None)
    if not p:
        sys.exit(f"No preview {pid}.")
    return items, p


def cmd_open(a, r: Path) -> None:
    items, p = find(r, a.id)
    ok, msg = open_preview(r, p)
    save(r, items)
    print(msg)
    sys.exit(0 if ok else 1)


def cmd_shot(a, r: Path) -> None:
    items, p = find(r, a.id)
    ok = take_shot(r, p)
    save(r, items)
    print("Screenshot updated." if ok else "No screenshot (only the Simulator and emulator can be captured).")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    s = sub.add_parser("add")
    s.add_argument("--kind", choices=KINDS, required=True)
    s.add_argument("--target", required=True)
    s.add_argument("--label")
    s.add_argument("--cmd", help="the command that started it, so Claude can restart it")
    s.add_argument("--pid", type=int, help="pid of the dev server, so an idle preview can be stopped")
    s.add_argument("--screenshot", help="a PNG of the app as it looks now")
    s = sub.add_parser("list"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("remove"); g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("id", nargs="?"); g.add_argument("--all", action="store_true")
    s = sub.add_parser("open"); s.add_argument("id")
    s = sub.add_parser("shot"); s.add_argument("id")
    a = ap.parse_args()
    {"add": cmd_add, "list": cmd_list, "remove": cmd_remove, "open": cmd_open, "shot": cmd_shot}[a.action](a, root())


if __name__ == "__main__":
    main()
