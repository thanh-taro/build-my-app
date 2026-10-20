"""Shared helpers for build-my-app hooks. Every hook must be a silent no-op outside
build-my-app projects, and must never crash the session (fail open)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
STATE_CLI = PLUGIN_ROOT / "scripts" / "bma_state.py"


def read_input() -> dict:
    try:
        return json.load(sys.stdin)
    except Exception:
        return {}


def project_dir(data: dict) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())


def state_file(root: Path) -> Path:
    return root / ".build-my-app" / "state.json"


def is_bma_project(root: Path) -> bool:
    return state_file(root).exists()


def has_spec_tools(root: Path) -> bool:
    return (root / "tools" / "spec_lint.py").exists() and (root / "specs").is_dir()


def state_cli(root: Path, *args: str) -> str:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(root))
    r = subprocess.run([sys.executable, str(STATE_CLI), *args], capture_output=True, text=True,
                       cwd=root, env=env, timeout=20)
    return r.stdout.strip()


def emit(obj: dict) -> None:
    print(json.dumps(obj))


def deny(reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                 "permissionDecision": "deny", "permissionDecisionReason": reason}})


def ask(reason: str) -> None:
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                 "permissionDecision": "ask", "permissionDecisionReason": reason}})
