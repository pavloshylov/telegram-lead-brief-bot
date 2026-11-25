"""Runs the whole test suite against a throw-away embedded PostgreSQL (no Docker needed).

    pip install pixeltable-pgserver
    python scripts/test_postgres.py            # extra arguments are passed to pytest

The same tests run on SQLite by default; this sets TEST_DATABASE_URL so tests/conftest.py uses PostgreSQL.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pixeltable_pgserver as pgserver

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="brief_bot_pg_", ignore_cleanup_errors=True) as data_dir:
        server = pgserver.get_server(Path(data_dir), cleanup_mode="stop")
        try:
            url = server.get_uri().replace("postgresql://", "postgresql+asyncpg://", 1)
            print("PostgreSQL started for the tests (temporary data directory)", flush=True)
            env = dict(os.environ, TEST_DATABASE_URL=url)
            return subprocess.call([sys.executable, "-m", "pytest", "-q", *sys.argv[1:]], env=env, cwd=ROOT)
        finally:
            server.cleanup()  # stop the server first: Windows cannot delete files it still has open


if __name__ == "__main__":
    raise SystemExit(main())
