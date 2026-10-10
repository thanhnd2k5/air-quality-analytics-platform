from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

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
