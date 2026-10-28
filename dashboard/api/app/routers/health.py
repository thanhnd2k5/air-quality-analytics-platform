import re
import time
import urllib.request
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db, get_engine

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Process liveness — does not require PostgreSQL."""
    return {"status": "ok", "service": "dashboard-api"}


@router.get("/health/db")
def health_db(db: Session = Depends(get_db)) -> dict:
    """Readiness — verifies DWH connectivity."""
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "up"}


def _short(exc: Exception) -> str:
    """First line of the error without SQLAlchemy's "(psycopg2.X)" prefix and background link."""
    line = str(exc).strip().splitlines()[0] if str(exc).strip() else type(exc).__name__
    line = re.sub(r"^\([\w.]+\)\s*", "", line)
    return line[:120]


def _timed(name: str, role: str, probe) -> dict:
    start = time.perf_counter()
    try:
        probe()
        ok, detail = True, None
    except Exception as exc:  # a monitor reports the failure, it does not raise it
        ok, detail = False, _short(exc)
    return {
        "name": name,
        "role": role,
        "ok": ok,
        "latency_ms": round((time.perf_counter() - start) * 1000, 1),
        "detail": detail,
    }


def _ping_postgres() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


def _ping_minio() -> None:
    s = get_settings()
    url = f"{'https' if s.minio_secure else 'http'}://{s.minio_endpoint}/minio/health/live"
    with urllib.request.urlopen(url, timeout=3) as res:  # noqa: S310 — fixed URL from settings
        if res.status != 200:
            raise RuntimeError(f"HTTP {res.status}")


@router.get("/health/services")
def health_services() -> dict:
    """The stores the warehouse runs on, with response time. Never cached, never raises."""
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "services": [
            _timed("PostgreSQL", "Kho dữ liệu (staging, dwh, mart)", _ping_postgres),
            _timed("MinIO", "Data lake (raw, processed)", _ping_minio),
        ],
    }
