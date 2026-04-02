"""One-off: drop Django test DB. Run: py scripts/drop_test_db.py"""
import os
import sys

import psycopg

# Load password from backend .env if present
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DB_") and "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k == "DB_PASSWORD" and v and k not in os.environ:
                os.environ["DB_PASSWORD"] = v

pw = os.environ.get("DB_PASSWORD", "")
conn = psycopg.connect(
    f"host=localhost port=5432 dbname=postgres user=postgres password={pw}"
)
conn.autocommit = True
cur = conn.cursor()
cur.execute(
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
    "WHERE datname = 'test_fastforms' AND pid <> pg_backend_pid()"
)
cur.execute("DROP DATABASE IF EXISTS test_fastforms")
conn.close()
print("Dropped database test_fastforms")
