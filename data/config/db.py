"""App DB (MySQL or PostgreSQL) + optional RADIUS engine."""

from __future__ import annotations

import os
from collections.abc import Generator
from functools import lru_cache
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()


class Base(DeclarativeBase):
    pass


def db_driver() -> str:
    """mysql | postgresql"""
    raw = (os.getenv("DB_DRIVER") or os.getenv("DB_DIALECT") or "mysql").strip().lower()
    if raw in {"postgres", "postgresql", "pgsql", "psql"}:
        return "postgresql"
    return "mysql"


def is_postgres() -> bool:
    return db_driver() == "postgresql"


def _build_url(
    *,
    driver: str,
    host: str,
    port: str,
    user: str,
    password: str,
    database: str,
) -> str:
    user_q = quote_plus(user)
    pass_q = quote_plus(password)
    if driver == "postgresql":
        # psycopg v3
        return f"postgresql+psycopg://{user_q}:{pass_q}@{host}:{port}/{database}"
    return f"mysql+pymysql://{user_q}:{pass_q}@{host}:{port}/{database}?charset=utf8mb4"


@lru_cache
def get_app_engine() -> Engine:
    driver = db_driver()
    default_port = "5432" if driver == "postgresql" else "3306"
    default_user = "postgres" if driver == "postgresql" else "radius"
    default_db = "moowifi"
    return create_engine(
        _build_url(
            driver=driver,
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", default_port),
            user=os.getenv("DB_USER", default_user),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", default_db),
        ),
        pool_pre_ping=True,
        pool_recycle=280,
        pool_size=10,
        max_overflow=5,
    )


@lru_cache
def get_radius_engine() -> Engine:
    """RADIUS stays MySQL in production; for local PG tests you can point it at app DB
    or set RADIUS_ENABLED=false.
    """
    if os.getenv("RADIUS_ENABLED", "true").lower() in {"0", "false", "no", "off"}:
        # Reuse app engine so imports don't crash; queries may still fail if tables missing
        return get_app_engine()

    radius_driver = (os.getenv("RADIUS_DB_DRIVER") or db_driver()).strip().lower()
    if radius_driver in {"postgres", "postgresql", "pgsql", "psql"}:
        radius_driver = "postgresql"
    else:
        radius_driver = "mysql"

    default_port = "5432" if radius_driver == "postgresql" else "3306"
    return create_engine(
        _build_url(
            driver=radius_driver,
            host=os.getenv("RADIUS_DB_HOST", os.getenv("DB_HOST", "localhost")),
            port=os.getenv("RADIUS_DB_PORT", os.getenv("DB_PORT", default_port)),
            user=os.getenv("RADIUS_DB_USER", os.getenv("DB_USER", "postgres")),
            password=os.getenv("RADIUS_DB_PASSWORD", os.getenv("DB_PASSWORD", "")),
            database=os.getenv("RADIUS_DB_NAME", os.getenv("DB_NAME", "moowifi")),
        ),
        pool_pre_ping=True,
        pool_recycle=280,
        pool_size=5,
        max_overflow=5,
    )


SessionLocal = sessionmaker(
    bind=get_app_engine(),
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def _ensure_columns(engine: Engine) -> None:
    """Add columns introduced on models after initial table creation."""
    if not is_postgres():
        return

    statements = [
        "ALTER TABLE service_sales ADD COLUMN IF NOT EXISTS location_id INTEGER",
        "ALTER TABLE service_sales ADD COLUMN IF NOT EXISTS product_id INTEGER",
        "ALTER TABLE service_sales ADD COLUMN IF NOT EXISTS taahhut_suresi VARCHAR(30)",
        "ALTER TABLE service_sales ADD COLUMN IF NOT EXISTS catalog_price_key VARCHAR(100)",
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def init_schema() -> None:
    """Create ORM tables and ensure missing columns exist."""
    import data.models  # noqa: F401

    engine = get_app_engine()
    Base.metadata.create_all(bind=engine)
    _ensure_columns(engine)

def init_engines() -> None:
    """Warm pools and verify connectivity."""
    with get_app_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    if os.getenv("INIT_SCHEMA", "false").lower() in {"1", "true", "yes", "on"}:
        init_schema()
        print(f"[db] schema ensured ({db_driver()})")
    if os.getenv("RADIUS_ENABLED", "true").lower() in {"0", "false", "no", "off"}:
        print("[db] RADIUS disabled (local mode)")
        return
    try:
        with get_radius_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        print(f"[db] RADIUS bağlantısı atlandı: {exc}")


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
