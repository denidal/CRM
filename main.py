"""
Müşteri Takip CRM — FastAPI entrypoint.

Layers:
  data/     → SQLAlchemy models, repositories, migrations
  system/   → domain, services, API, auth, workers
  visuals/  → Jinja2 templates + HTML page routes
"""

from __future__ import annotations

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Project root on sys.path (allows `python main.py` from any cwd)
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Register ORM metadata
import data.models  # noqa: F401
from system.api import build_api_router
from visuals.routes.pages import router as pages_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks."""
    # Ensure runtime folders exist
    (BASE_DIR / "uploads" / "btk_logs").mkdir(parents=True, exist_ok=True)
    (BASE_DIR / ".locks").mkdir(parents=True, exist_ok=True)

    # Optional DB ping (app continues even if DB is down — pages will error later)
    try:
        from data.config.db import init_engines

        init_engines()
        print("[startup] DB bağlantıları hazır")
    except Exception as exc:  # noqa: BLE001
        print(f"[startup] DB uyarı: {exc}")

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Müşteri Takip CRM",
        description=(
            "Customer → N ServiceSale hiyerarşisi. "
            "API: /api/* · UI: /customers, /radius, /finance, /btk"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS (same-origin UI + optional external clients)
    origins = [
        o.strip()
        for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
        if o.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Static assets (CSS/JS)
    static_dir = BASE_DIR / "visuals" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # --- API (JSON) ---
    # /api/auth/*, /api/customers, /api/services, /api/abone,
    # /api/pops, /api/radius-*, /api/iss-aboneler, /api/finance/*,
    # /api/btk/*, /api/internet-contracts, /api/hotspot-contracts, /api/customer-files
    app.include_router(build_api_router())

    # --- HTML pages (Jinja2) ---
    # /, /login, /customers, /pops, /radius, /finance/*, /btk, /services/{id}/radius
    app.include_router(pages_router)

    @app.get("/health", tags=["meta"])
    def health():
        return {
            "ok": True,
            "app": "musteri-takip-crm",
            "hierarchy": "Customer → N ServiceSale",
            "pop_required_on_abone": False,
            "layers": ["data", "system", "visuals"],
        }

    @app.get("/api", tags=["meta"])
    def api_index():
        """Quick map of mounted API groups."""
        return {
            "auth": "/api/auth/login",
            "customers": "/api/customers",
            "services": "/api/services",
            "abone": "/api/abone",
            "pops": "/api/pops",
            "radius": "/api/radius-users",
            "iss": "/api/iss-aboneler",
            "contracts": ["/api/internet-contracts", "/api/hotspot-contracts"],
            "finance": "/api/finance/invoices",
            "btk": "/api/btk/operations",
            "docs": "/docs",
        }

    @app.exception_handler(ValueError)
    async def value_error_handler(_request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"success": False, "detail": str(exc)})

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("APP_HOST", "0.0.0.0")
    port = int(os.getenv("APP_PORT", "8000"))
    reload = os.getenv("DEBUG", "true").lower() in {"1", "true", "yes", "on"}

    print(f"[main] http://{host}:{port}  (docs: /docs)")
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=[str(BASE_DIR)] if reload else None,
    )
