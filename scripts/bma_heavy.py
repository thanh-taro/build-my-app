#!/usr/bin/env python3
"""Run a heavy command (build, test suite, e2e, app run, profiling) under the machine's
resource budget, so parallel agents cannot exhaust memory and crash the computer.

  bma_heavy.py [--label F-003] [--slots N] [--workers N] [--wait-timeout S] -- <command ...>

- Global slots: at most `slots` heavy commands run at once on this machine, across every
  agent, worktree, and project (file locks under the git common dir, falling back to the temp
  dir; released automatically if the process dies). Others wait their turn.
- Worker caps: exports BMA_TEST_WORKERS (the project's test config reads it) plus the
  runner-specific variables we know are honored.
- Low priority: the command runs under `nice`, so the desktop stays responsive.
- Memory watchdog: when the OS reports critical memory pressure (macOS) or available memory
  falls under 7% / 1 GiB (Linux), the whole process group is stopped and the script exits 137
  with advice, instead of letting the machine swap to death.

Budget comes from flags, else `resources` in .build-my-app/state.json (`bma_state.py
resources`), else a safe default computed from RAM/CPU. Standard library only.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bma_resources import budget, memory_state  # noqa: E402

POLL = 2.0


def git_common_dir() -> Path | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                             capture_output=True, text=True, timeout=5)
        return Path(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None
    except Exception:
        return None


def configured_budget() -> dict:
    """State lives in the main checkout; worktrees find it through the git common dir."""
    roots = [Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())]
    common = git_common_dir()
    if common:
        roots.append(common.parent)
    for root in roots:
        p = root / ".build-my-app" / "state.json"
        try:
            res = json.loads(p.read_text()).get("resources")
            if res:
                return res
        except Exception:
            continue
    return budget()


def lock_dir() -> Path:
    # One lock dir per machine user: the scarce resource is the machine, not the project.
    d = Path(tempfile.gettempdir()) / f"build-my-app-heavy-{os.getuid()}"
    try:
        d.mkdir(parents=True, exist_ok=True)
        return d
    except OSError:
        common = git_common_dir() or Path.cwd()
        d = common / "bma-locks"
        d.mkdir(parents=True, exist_ok=True)
        return d


def acquire(slots: int, label: str, timeout: float):
    d = lock_dir()
    start = time.time()
    announced = False
    while True:
        for i in range(slots):
            f = open(d / f"slot-{i}.lock", "a+")
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                f.close()
                continue
            f.seek(0); f.truncate(); f.write(f"{os.getpid()} {label}\n"); f.flush()
            return f
        if not announced:
            print(f"[bma_heavy] waiting for a free slot ({slots} max) — another heavy run is in progress",
                  file=sys.stderr, flush=True)
            announced = True
        if timeout and time.time() - start > timeout:
            sys.exit(f"[bma_heavy] gave up after {int(timeout)}s waiting for a slot")
        time.sleep(POLL)


def wait_for_memory(timeout: float = 300) -> None:
    start = time.time()
    while memory_state() == "critical" and time.time() - start < timeout:
        print("[bma_heavy] memory pressure is critical — waiting before starting", file=sys.stderr, flush=True)
        time.sleep(10)


def worker_env(workers: int) -> dict:
    env = dict(os.environ)
    w = str(workers)
    env.update({
        "BMA_TEST_WORKERS": w,
        "BMA_HEAVY": "1",
        "VITEST_MAX_THREADS": w, "VITEST_MAX_FORKS": w,   # older vitest
        "PLAYWRIGHT_WORKERS": w,                          # read by the project's playwright config
        "PYTEST_XDIST_AUTO_NUM_WORKERS": w,               # pytest -n auto
        "GOMAXPROCS": env.get("GOMAXPROCS", w),
        "CARGO_BUILD_JOBS": env.get("CARGO_BUILD_JOBS", w),
        "RUST_TEST_THREADS": env.get("RUST_TEST_THREADS", w),
    })
    return env


def kill_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        for _ in range(20):
            if proc.poll() is not None:
                return
            time.sleep(0.5)
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--label", default="")
    ap.add_argument("--slots", type=int)
    ap.add_argument("--workers", type=int)
    ap.add_argument("--wait-timeout", type=float, default=3600)
    ap.add_argument("--no-watchdog", action="store_true")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    if not cmd:
        ap.error("missing command after --")
    res = configured_budget()
    slots = max(1, a.slots or int(res.get("heavy_slots", 1)))
    workers = max(1, a.workers or int(res.get("test_workers", 2)))

    lock = acquire(slots, a.label or " ".join(cmd)[:80], a.wait_timeout)
    wait_for_memory()
    print(f"[bma_heavy] running ({slots} slot(s), {workers} test worker(s)): {' '.join(cmd)}",
          file=sys.stderr, flush=True)
    shell = len(cmd) == 1  # a single string → let the shell parse it (pipes, &&)
    proc = subprocess.Popen(cmd[0] if shell else cmd, shell=shell, env=worker_env(workers),
                            start_new_session=True, preexec_fn=lambda: os.nice(10))
    strikes = 0
    try:
        while proc.poll() is None:
            time.sleep(POLL)
            if a.no_watchdog:
                continue
            strikes = strikes + 1 if memory_state() == "critical" else 0
            if strikes >= 3:  # ~6 s of sustained critical pressure
                print("[bma_heavy] ABORTED: critical memory pressure. Stopped the run to protect the machine.\n"
                      "  Lower the budget (`bma_state.py resources --workers 1 --slots 1`), run a narrower test\n"
                      "  selection, close simulators/emulators/dev servers you do not need, then retry.",
                      file=sys.stderr, flush=True)
                kill_group(proc)
                return 137
    except KeyboardInterrupt:
        kill_group(proc)
        return 130
    finally:
        lock.close()
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
