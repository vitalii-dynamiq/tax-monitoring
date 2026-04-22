import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import (
    api_keys,
    approvals,
    audit,
    auth,
    jurisdictions,
    monitoring,
    tax_calculation,
    tax_rates,
    tax_rules,
)
from app.middleware import setup_middleware
from app.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        start_scheduler()
    except Exception as e:
        logging.getLogger("taxlens").error(
            "Failed to start monitoring scheduler: %s (API will still work, but scheduled monitoring is disabled)", e
        )
    yield
    stop_scheduler()


app = FastAPI(
    title="TaxLens API",
    description="Global Accommodation Tax Intelligence Platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

setup_middleware(app)

app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(jurisdictions.router)
app.include_router(tax_rates.router)
app.include_router(tax_rules.router)
app.include_router(tax_calculation.router)
app.include_router(monitoring.router)
app.include_router(audit.router)
app.include_router(approvals.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logging.getLogger("taxlens").error(
        "Unhandled error on %s %s: %s", request.method, request.url.path, exc, exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/health")
async def health():
    from sqlalchemy import text

    from app.config import settings
    from app.db.session import async_session_factory
    from app.services.scheduler import scheduler

    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "version": "0.1.0",
        "database": db_status,
        "scheduler": "running" if scheduler.running else "stopped",
        "ai_configured": bool(settings.anthropic_api_key),
    }
