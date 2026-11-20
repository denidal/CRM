"""Create empty local Postgres DB + ORM tables.

Usage:
  python -m data.migrations.init_postgres
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")


def main() -> int:
    os.environ.setdefault("DB_DRIVER", "postgresql")
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")
    dbname = os.getenv("DB_NAME", "moowifi")

    import psycopg

    admin_url = (
        f"postgresql://{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/postgres"
    )
    with psycopg.connect(admin_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            if cur.fetchone() is None:
                cur.execute(f'CREATE DATABASE "{dbname}"')
                print(f"[ok] database created: {dbname}")
            else:
                print(f"[ok] database exists: {dbname}")

    # Bind engines after DB exists
    from data.config.db import get_app_engine, init_schema

    get_app_engine.cache_clear()
    os.environ["DB_DRIVER"] = "postgresql"
    os.environ["INIT_SCHEMA"] = "true"
    init_schema()
    print("[ok] ORM tables created")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
