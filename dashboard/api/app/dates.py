from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db import fetch_one


def data_date_bounds(db: Session) -> tuple[date, date]:
    row = fetch_one(
        db,
        """
        SELECT MIN(date_day)::date AS min_day, MAX(date_day)::date AS max_day
        FROM mart.mart_station_daily
        """,
    )
    if not row or row["min_day"] is None or row["max_day"] is None:
        raise ValueError("mart.mart_station_daily is empty")
    return row["min_day"], row["max_day"]


def resolve_date_range(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    *,
    default_days: int = 90,
) -> tuple[date, date]:
    min_day, max_day = data_date_bounds(db)
    end = date_to or max_day
    start = date_from or (end - timedelta(days=default_days - 1))
    if start < min_day:
        start = min_day
    if end > max_day:
        end = max_day
    if start > end:
        start = end
    return start, end
