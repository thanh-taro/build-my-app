"""Event log for the build-my-app web UI. Standard library only.

Writers (the ui_events hook, bma_heavy.py) append one JSON object per line to
`.build-my-app/tmp/ui/events.jsonl`, but only while the UI server is running (it writes
`ui.json` next to the log and removes it on exit). With the UI off, every call is a cheap no-op.
The server tails the log and turns it into the live room and feed.
"""
from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024   # rotate the log past 2 MB ...
KEEP_BYTES = 512 * 1024       # ... keeping the newest 512 KB


def ui_dir(root: Path) -> Path:
    return root / ".build-my-app" / "tmp" / "ui"


def ui_info_path(root: Path) -> Path:
    return ui_dir(root) / "ui.json"


def events_path(root: Path) -> Path:
    return ui_dir(root) / "events.jsonl"


def ui_enabled(root: Path) -> bool:
    return ui_info_path(root).exists()


def clip(text: str | None, n: int) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def clip_text(text: str | None, n: int) -> str:
    """Like clip, but keeps line breaks (for chat messages shown in the feed)."""
    lines = [" ".join(line.split()) for line in str(text or "").strip().splitlines()]
    out = "\n".join(lines).strip()
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out if len(out) <= n else out[: n - 1].rstrip() + "…"


def first_line(text: str | None) -> str:
    return next((line.strip() for line in str(text or "").splitlines() if line.strip()), "")


def lower_first(text: str) -> str:
    """'Implement F-003' -> 'implement F-003', but leave 'F-003 pause' and 'UI audit' alone."""
    if len(text) > 1 and text[0].isupper() and text[1].islower():
        return text[0].lower() + text[1:]
    return text


def append(root: Path, event: dict) -> None:
    """Append one event. Never raises: the UI must never break the workflow."""
    try:
        if not ui_enabled(root):
            return
        event.setdefault("ts", round(time.time(), 3))
        line = (json.dumps(event, ensure_ascii=False) + "\n").encode()
        p = events_path(root)
        with open(p, "ab") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(line)
                f.flush()
                if f.tell() > MAX_BYTES:
                    _rotate(p)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    except Exception:
        pass


def _rotate(p: Path) -> None:
    data = p.read_bytes()[-KEEP_BYTES:]
    cut = data.find(b"\n")
    tmp = p.with_suffix(".tmp")
    tmp.write_bytes(data[cut + 1:] if cut >= 0 else b"")
    os.replace(tmp, p)  # the server notices the shrink and re-reads from the start
