import shutil
import subprocess
from pathlib import Path

import pytest

RUN = Path(__file__).resolve().parents[2] / "supabase" / "tests" / "run.sh"


@pytest.mark.skipif(shutil.which("psql") is None or not list(Path("/usr/lib/postgresql").glob("*/bin/initdb"))
                    if Path("/usr/lib/postgresql").exists() else True, reason="local postgres not available")
def test_migrations_enforce_gate_audit_rls_countdown():
    r = subprocess.run(["bash", str(RUN)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    assert "ALL SQL CHECKS PASSED" in r.stdout
