from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Result
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_db() -> Generator[Session, None, None]:
    get_engine()
    assert _SessionLocal is not None
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def fetch_all(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    result: Result = db.execute(text(sql), params or {})
    return [dict(row) for row in result.mappings().all()]


def fetch_one(db: Session, sql: str, params: dict | None = None) -> dict | None:
    result: Result = db.execute(text(sql), params or {})
    row = result.mappings().first()
    return dict(row) if row else None
