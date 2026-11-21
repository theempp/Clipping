"""GPU snapshot for the dashboard heartbeat via nvidia-smi. Returns None when
there is no NVIDIA GPU or the tool is missing; never raises."""
from __future__ import annotations

import subprocess

QUERY = ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
         "--format=csv,noheader,nounits"]


def parse(line: str) -> dict | None:
    parts = [p.strip() for p in line.strip().split(",")]
    if len(parts) != 4:
        return None
    try:
        return {"name": parts[0].replace("NVIDIA GeForce ", ""), "util": int(float(parts[1])),
                "mem_used_gb": round(float(parts[2]) / 1024, 1),
                "mem_total_gb": round(float(parts[3]) / 1024, 1)}
    except ValueError:
        return None


def snapshot(run=subprocess.run) -> dict | None:
    try:
        r = run(QUERY, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return parse(r.stdout.splitlines()[0])
