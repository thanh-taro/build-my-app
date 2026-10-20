#!/usr/bin/env python3
"""Build-my-app workflow state: the orchestrator's memory.

State lives in the project at `.build-my-app/state.json` so a run survives session ends and
context compaction. Standard library only. Every command prints human-readable output; `--json`
prints machine-readable output where useful.

Usage (from the project root):
  bma_state.py init [--autonomy guided|balanced|autopilot]
  bma_state.py status [--short]          Progress, current phase/step, open decisions, loops
  bma_state.py next                      What the orchestrator should do next
  bma_state.py phase <id> <pending|in_progress|gate|done> [--step TEXT]
  bma_state.py step "<text>"             Record the current step within the current phase
  bma_state.py gate <phase-id> pass|reopen [--note TEXT]
  bma_state.py decide add "<question>" --options "A|B|C" [--recommend A] [--kind product|money|legal|release|design|technical]
  bma_state.py decide answer <D-id> "<answer>"
  bma_state.py decide list [--open]
  bma_state.py loop start <name> [--max 3]
  bma_state.py loop next <name>          Increments the round; exits 3 when the limit is reached
  bma_state.py loop end <name> [--outcome TEXT]
  bma_state.py set <key> <json-value>    Top-level settings: autonomy, profile, stack, design_tool, ...
  bma_state.py get <key>
  bma_state.py log "<event>"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PHASES = [
    ("setup", "0 Setup & discovery"),
    ("product-spec", "1 Product & spec"),
    ("design", "2 Design"),
    ("architecture", "3 Architecture & spikes"),
    ("build", "4 Implementation"),
    ("qa", "5 QA & hardening"),
    ("release", "6 Release candidate"),
    ("deploy", "7 Deploy"),
    ("iterate", "8 Iterate"),
]
PHASE_IDS = [p for p, _ in PHASES]
# Phases 0-5 run on the local machine only; "release" packages a candidate locally and
# "deploy" is the first phase allowed to ship anything off the machine.
LOCAL_PHASES = ("setup", "product-spec", "design", "architecture", "build", "qa", "release")
# Phases that may start once their prerequisites' gates have passed.
REQUIRES = {
    "setup": [],
    "product-spec": ["setup"],
    "design": ["product-spec"],
    "architecture": ["product-spec"],
    "build": ["design", "architecture"],
    "qa": ["build"],
    "release": ["qa"],
    "deploy": ["release"],
    "iterate": ["deploy"],
}
PHASE_SKILL = {pid: pid for pid in PHASE_IDS}  # skill names in the build-my-app plugin
AUTONOMY = ("guided", "balanced", "autopilot")
STATUSES = ("pending", "in_progress", "gate", "done")


def project_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())


def state_path() -> Path:
    return project_root() / ".build-my-app" / "state.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(required: bool = True) -> dict | None:
    p = state_path()
    if not p.exists():
        if required:
            sys.exit("No build-my-app state here. Run `/build-my-app:start` to start (or `bma_state.py init`).")
        return None
    return migrate(json.loads(p.read_text()))


def migrate(state: dict) -> dict:
    """Add phases introduced after the state was created (e.g. 'deploy' in v2)."""
    for pid, title in PHASES:
        ph = state["phases"].get(pid)
        if ph is None:
            ph = {"title": title, "status": "pending", "step": None,
                  "gate": {"status": "pending", "at": None, "note": None}}
            # v1 'release' meant "user submitted/published": treat deploy as already done.
            if pid == "deploy" and state["phases"].get("release", {}).get("gate", {}).get("status") == "passed":
                ph["status"] = "done"
                ph["gate"] = {"status": "passed", "at": now(), "note": "migrated: v1 release covered deployment"}
            state["phases"][pid] = ph
        else:
            ph["title"] = title
    state["phases"] = {pid: state["phases"][pid] for pid in PHASE_IDS}
    state["version"] = 2
    return state


def save(state: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    state["updated"] = now()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(p)  # atomic


def log(state: dict, event: str) -> None:
    state.setdefault("log", []).append({"at": now(), "event": event})
    state["log"] = state["log"][-200:]


def current_phase(state: dict) -> str | None:
    for pid in PHASE_IDS:
        if state["phases"][pid]["status"] in ("in_progress", "gate"):
            return pid
    return None


def ready_phases(state: dict) -> list[str]:
    out = []
    for pid in PHASE_IDS:
        ph = state["phases"][pid]
        if ph["status"] != "pending":
            continue
        if all(state["phases"][r]["gate"]["status"] == "passed" for r in REQUIRES[pid]):
            out.append(pid)
    return out


# -- commands ---------------------------------------------------------------

def cmd_init(a) -> None:
    if load(required=False):
        sys.exit("State already exists. Use `status`.")
    state = {
        "version": 2,
        "created": now(),
        "autonomy": a.autonomy,
        "profile": {},
        "stack": None,
        "design_tool": None,
        "phases": {pid: {"title": t, "status": "pending", "step": None,
                         "gate": {"status": "pending", "at": None, "note": None}}
                   for pid, t in PHASES},
        "decisions": [],
        "loops": {},
        "log": [],
    }
    log(state, f"initialized (autonomy={a.autonomy})")
    save(state)
    print(f"Initialized {state_path()}")


def summary_lines(state: dict, short: bool = False) -> list[str]:
    done = sum(1 for p in PHASE_IDS if state["phases"][p]["status"] == "done")
    cur = current_phase(state)
    open_d = [d for d in state["decisions"] if d["status"] == "open"]
    lines = []
    if cur:
        ph = state["phases"][cur]
        step = f" — {ph['step']}" if ph.get("step") else ""
        lines.append(f"build-my-app: phase {ph['title']} [{ph['status']}]{step} · {done}/{len(PHASE_IDS)} phases done"
                     f" · autonomy {state['autonomy']}")
    else:
        nxt = ready_phases(state)
        lines.append(f"build-my-app: {done}/{len(PHASE_IDS)} phases done · next: "
                     f"{', '.join(state['phases'][p]['title'] for p in nxt) or 'nothing (all done)'}")
    if open_d:
        lines.append(f"Open decisions ({len(open_d)}): " + "; ".join(f"{d['id']} {d['question']}" for d in open_d[:5]))
    if short:
        return lines
    lines.append("")
    for pid in PHASE_IDS:
        ph = state["phases"][pid]
        mark = {"pending": " ", "in_progress": ">", "gate": "?", "done": "x"}[ph["status"]]
        gate = "gate passed" if ph["gate"]["status"] == "passed" else ""
        lines.append(f"  [{mark}] {ph['title']:<26} {ph['status']:<12} {gate}")
    active_loops = {k: v for k, v in state["loops"].items() if v.get("active")}
    if active_loops:
        lines.append("")
        lines.append("Active loops: " + ", ".join(f"{k} round {v['round']}/{v['max']}" for k, v in active_loops.items()))
    return lines


def cmd_status(a) -> None:
    print("\n".join(summary_lines(load(), a.short)))


def cmd_next(a) -> None:
    state = load()
    open_d = [d for d in state["decisions"] if d["status"] == "open"]
    cur = current_phase(state)
    if open_d:
        print(f"ASK: {len(open_d)} open decision(s) block progress. Present them (with recommendations) "
              f"and record answers via `decide answer`. First: {open_d[0]['id']} {open_d[0]['question']}")
        return
    if cur:
        ph = state["phases"][cur]
        if ph["status"] == "gate":
            print(f"GATE: phase '{cur}' awaits its gate. Run the gate checklist in skill "
                  f"'{PHASE_SKILL[cur]}', then `gate {cur} pass` once approved.")
        else:
            print(f"CONTINUE: phase '{cur}' (skill '{PHASE_SKILL[cur]}'), step: {ph.get('step') or 'start'}")
        return
    nxt = ready_phases(state)
    if not nxt:
        print("DONE: all phases complete. Use /build-my-app:change for new work or start the next milestone in 'iterate'.")
        return
    print("START: " + ", ".join(f"phase '{p}' (skill '{PHASE_SKILL[p]}')" for p in nxt)
          + (" — these may run in parallel." if len(nxt) > 1 else ""))


def cmd_phase(a) -> None:
    state = load()
    if a.id not in PHASE_IDS:
        sys.exit(f"Unknown phase '{a.id}'. Phases: {', '.join(PHASE_IDS)}")
    if a.status not in STATUSES:
        sys.exit(f"Unknown status '{a.status}'.")
    missing = [r for r in REQUIRES[a.id] if state["phases"][r]["gate"]["status"] != "passed"]
    if a.status == "in_progress" and missing:
        sys.exit(f"Cannot start '{a.id}': gate(s) not passed: {', '.join(missing)}")
    if a.status == "done" and state["phases"][a.id]["gate"]["status"] != "passed":
        sys.exit(f"Cannot finish '{a.id}': its gate has not passed.")
    state["phases"][a.id]["status"] = a.status
    if a.step is not None:
        state["phases"][a.id]["step"] = a.step
    log(state, f"phase {a.id} -> {a.status}")
    save(state)
    print(f"{a.id}: {a.status}")


def cmd_step(a) -> None:
    state = load()
    cur = current_phase(state)
    if not cur:
        sys.exit("No phase in progress.")
    state["phases"][cur]["step"] = a.text
    log(state, f"{cur} step: {a.text}")
    save(state)
    print(f"{cur}: {a.text}")


def cmd_gate(a) -> None:
    state = load()
    ph = state["phases"].get(a.phase)
    if not ph:
        sys.exit(f"Unknown phase '{a.phase}'.")
    if a.action == "pass":
        ph["gate"] = {"status": "passed", "at": now(), "note": a.note}
        ph["status"] = "done"
        log(state, f"gate {a.phase} passed" + (f": {a.note}" if a.note else ""))
    else:
        ph["gate"] = {"status": "pending", "at": now(), "note": a.note}
        ph["status"] = "in_progress"
        log(state, f"gate {a.phase} reopened" + (f": {a.note}" if a.note else ""))
    save(state)
    print(f"gate {a.phase}: {ph['gate']['status']}")


def cmd_decide(a) -> None:
    state = load()
    ds = state["decisions"]
    if a.action == "add":
        did = f"D-{len(ds) + 1:03d}"
        ds.append({"id": did, "question": a.text, "options": (a.options or "").split("|") if a.options else [],
                   "recommendation": a.recommend, "kind": a.kind, "phase": current_phase(state),
                   "status": "open", "answer": None, "asked": now(), "answered": None})
        log(state, f"decision {did} opened: {a.text}")
        save(state)
        print(did)
    elif a.action == "answer":
        d = next((d for d in ds if d["id"] == a.text), None)
        if not d:
            sys.exit(f"No decision {a.text}")
        d.update(status="answered", answer=a.answer, answered=now())
        log(state, f"decision {d['id']} answered: {a.answer}")
        save(state)
        print(f"{d['id']}: {a.answer}")
    else:
        items = [d for d in ds if d["status"] == "open"] if a.open else ds
        if a.json:
            print(json.dumps(items, indent=2, ensure_ascii=False))
            return
        for d in items:
            rec = f" (recommended: {d['recommendation']})" if d.get("recommendation") else ""
            ans = f" → {d['answer']}" if d.get("answer") else ""
            print(f"{d['id']} [{d['status']}, {d['kind']}] {d['question']}{rec}{ans}")


def cmd_loop(a) -> None:
    state = load()
    loops = state["loops"]
    if a.action == "start":
        loops[a.name] = {"round": 1, "max": a.max, "active": True, "started": now(), "outcome": None}
        log(state, f"loop {a.name} started (max {a.max})")
        save(state)
        print(f"{a.name}: round 1/{a.max}")
    elif a.action == "next":
        lp = loops.get(a.name)
        if not lp or not lp["active"]:
            sys.exit(f"Loop {a.name} is not active.")
        if lp["round"] >= lp["max"]:
            print(f"{a.name}: limit of {lp['max']} rounds reached — escalate remaining blockers to the user.")
            sys.exit(3)
        lp["round"] += 1
        log(state, f"loop {a.name} round {lp['round']}")
        save(state)
        print(f"{a.name}: round {lp['round']}/{lp['max']}")
    else:
        lp = loops.get(a.name)
        if not lp:
            sys.exit(f"No loop {a.name}")
        lp.update(active=False, outcome=a.outcome, ended=now())
        log(state, f"loop {a.name} ended: {a.outcome}")
        save(state)
        print(f"{a.name}: ended")


def cmd_set(a) -> None:
    state = load()
    try:
        value = json.loads(a.value)
    except json.JSONDecodeError:
        value = a.value
    if a.key == "autonomy" and value not in AUTONOMY:
        sys.exit(f"autonomy must be one of {AUTONOMY}")
    if a.key in ("phases", "decisions", "loops", "log"):
        sys.exit(f"Use the dedicated command to change '{a.key}'.")
    state[a.key] = value
    log(state, f"set {a.key}")
    save(state)
    print(f"{a.key} = {json.dumps(value, ensure_ascii=False)}")


def cmd_get(a) -> None:
    state = load()
    print(json.dumps(state.get(a.key), indent=2, ensure_ascii=False))


def cmd_log(a) -> None:
    state = load()
    log(state, a.text)
    save(state)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("init"); s.add_argument("--autonomy", choices=AUTONOMY, default="balanced")
    s = sub.add_parser("status"); s.add_argument("--short", action="store_true")
    sub.add_parser("next")
    s = sub.add_parser("phase"); s.add_argument("id"); s.add_argument("status"); s.add_argument("--step")
    s = sub.add_parser("step"); s.add_argument("text")
    s = sub.add_parser("gate"); s.add_argument("phase"); s.add_argument("action", choices=["pass", "reopen"])
    s.add_argument("--note")
    s = sub.add_parser("decide"); s.add_argument("action", choices=["add", "answer", "list"])
    s.add_argument("text", nargs="?"); s.add_argument("answer", nargs="?")
    s.add_argument("--options"); s.add_argument("--recommend")
    s.add_argument("--kind", default="product",
                   choices=["product", "money", "legal", "release", "design", "technical"])
    s.add_argument("--open", action="store_true"); s.add_argument("--json", action="store_true")
    s = sub.add_parser("loop"); s.add_argument("action", choices=["start", "next", "end"]); s.add_argument("name")
    s.add_argument("--max", type=int, default=3); s.add_argument("--outcome")
    s = sub.add_parser("set"); s.add_argument("key"); s.add_argument("value")
    s = sub.add_parser("get"); s.add_argument("key")
    s = sub.add_parser("log"); s.add_argument("text")
    a = ap.parse_args()
    {"init": cmd_init, "status": cmd_status, "next": cmd_next, "phase": cmd_phase, "step": cmd_step,
     "gate": cmd_gate, "decide": cmd_decide, "loop": cmd_loop, "set": cmd_set, "get": cmd_get,
     "log": cmd_log}[a.cmd](a)


if __name__ == "__main__":
    main()
