"""Machine resource detection and the build-my-app resource budget. Standard library only.

The budget limits how much heavy work (builds, test suites, simulators/emulators, dev
servers, profiling) runs at the same time:
  heavy_slots       heavy commands allowed at once (bma_heavy.py enforces it machine-wide)
  parallel_builders feature-builder agents allowed at once in a build wave
  test_workers      worker processes/threads per test run
"""
from __future__ import annotations

import os
import platform
import subprocess

GIB = 1024 ** 3


def _sysctl(name: str) -> str | None:
    try:
        out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def total_memory() -> int | None:
    if platform.system() == "Darwin":
        v = _sysctl("hw.memsize")
        return int(v) if v and v.isdigit() else None
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (ValueError, OSError, AttributeError):
        return None


def cpu_count() -> int:
    if platform.system() == "Darwin":
        v = _sysctl("hw.perflevel0.physicalcpu") or _sysctl("hw.physicalcpu")
        if v and v.isdigit():
            return int(v)
    return os.cpu_count() or 2


def memory_state() -> str:
    """'normal', 'warn', or 'critical' (unknown → 'normal')."""
    if platform.system() == "Darwin":
        v = _sysctl("kern.memorystatus_vm_pressure_level")  # 1 normal, 2 warn, 4 critical
        return {"2": "warn", "4": "critical"}.get(v or "", "normal")
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, rest = line.split(":", 1)
                info[k] = int(rest.split()[0]) * 1024
        avail, total = info.get("MemAvailable"), info.get("MemTotal")
        if avail is None or not total:
            return "normal"
        if avail < max(GIB, total * 0.07):
            return "critical"
        if avail < total * 0.15:
            return "warn"
    except (OSError, ValueError):
        pass
    return "normal"


def budget(mem: int | None = None, cpus: int | None = None) -> dict:
    """Conservative defaults. A mobile build + simulator/emulator + test run can take
    6–10 GB, so ≤16 GB machines get one heavy slot (no parallel builders)."""
    mem = mem if mem is not None else total_memory()
    cpus = cpus or cpu_count()
    gb = (mem or 8 * GIB) / GIB
    slots = 1 if gb <= 16 else 2 if gb <= 32 else 3
    slots = max(1, min(slots, cpus // 4 or 1))
    workers = max(1, min(4, cpus // (2 * slots)))
    return {
        "memory_gb": round(gb, 1),
        "cpus": cpus,
        "heavy_slots": slots,
        "parallel_builders": slots,
        "test_workers": workers,
    }
