"""Data quality: what the warehouse holds, how clean it is, and how the last pipeline run went.

Counts come live from PostgreSQL. Reconciliation, the pipeline run summary and the dbt test
result are files written by scripts/run_all.py under artifacts/ (mounted read-only in Docker).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import fetch_all, fetch_one, get_db
from app.schemas.quality import (
    ColumnMissing,
    DbtTests,
    LoadBatch,
    PipelineRun,
    PipelineStep,
    QualitySummary,
    Reconcile,
    ReconcileSide,
    SourceCount,
    StatusCount,
    WarehouseCounts,
)

router = APIRouter(prefix="/quality", tags=["quality"])

KEEP_NULL = "Giữ NULL + cờ, không nội suy"
FILL_OM = "Lấp từ Open-Meteo (ERA5)"

# (fact column, label, kind, *_source column or None, treatment) — see docs/DATA_PREPROCESSING.md.
COLUMNS: list[tuple[str, str, str, str | None, str]] = [
    ("pm25_ug_m3", "PM2.5", "Chất ô nhiễm", None, KEEP_NULL),
    ("pm10_ug_m3", "PM10", "Chất ô nhiễm", None, KEEP_NULL),
    ("so2_ug_m3", "SO₂", "Chất ô nhiễm", None, KEEP_NULL),
    ("no2_ug_m3", "NO₂", "Chất ô nhiễm", None, KEEP_NULL),
    ("co_ug_m3", "CO", "Chất ô nhiễm", None, KEEP_NULL),
    ("o3_ug_m3", "O₃", "Chất ô nhiễm", None, KEEP_NULL),
    ("temperature_c", "Nhiệt độ", "Thời tiết", "temperature_source", FILL_OM),
    ("pressure_hpa", "Áp suất", "Thời tiết", "pressure_source", FILL_OM),
    ("dew_point_c", "Điểm sương", "Thời tiết", "dew_point_source", FILL_OM),
    ("rain_mm", "Lượng mưa", "Thời tiết", "rain_source", FILL_OM),
    ("wind_speed_m_s", "Tốc độ gió", "Thời tiết", "wind_speed_source", FILL_OM),
    ("wind_direction", "Hướng gió", "Thời tiết", "wind_direction_source", f"{FILL_OM}; còn thiếu → UNKNOWN"),
]

DATASET_VI = {
    "air_quality_hourly": "Chất lượng không khí (UCI)",
    "weather_openmeteo_hourly": "Thời tiết (Open-Meteo)",
    "station_reference": "Danh mục trạm",
}


def _artifacts() -> Path:
    configured = get_settings().artifacts_dir
    # Outside Docker the API runs from the repo: dashboard/api/app/routers → repo/artifacts.
    return Path(configured) if configured else Path(__file__).resolve().parents[4] / "artifacts"


# The artifact files this endpoint reads, relative to the artifacts directory.
RECONCILE = "staging/reconcile.json"
LAST_RUN = "run_all/run_summary.json"
LAST_FULL_RUN = "run_all/run_summary_full.json"
DBT_TEST_LOG = "run_all/logs/dbt_test.log"


def artifacts_fingerprint() -> str:
    """Size + mtime of those files, so the response cache drops /quality when a run rewrites them."""
    parts = []
    for rel in (RECONCILE, LAST_RUN, LAST_FULL_RUN, DBT_TEST_LOG):
        try:
            st = (_artifacts() / rel).stat()
            parts.append(f"{rel}:{st.st_size}:{st.st_mtime_ns}")
        except OSError:
            parts.append(f"{rel}:-")
    return "|".join(parts)


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _run(summary: dict | None) -> PipelineRun | None:
    if not summary:
        return None
    opts = summary.get("options") or {}
    if opts.get("from_step"):
        scope = f"từ bước {opts['from_step']}"
    elif opts.get("only"):
        scope = f"chỉ {opts['only']}"
    else:
        scope = "toàn bộ"
    return PipelineRun(
        ok=bool(summary.get("ok")),
        finished_at=summary.get("finished_at"),
        total_seconds=summary.get("total_seconds"),
        scope=scope,
        steps=[
            PipelineStep(step=s["step"], status=s.get("status", "?"), seconds=s.get("seconds"), error=s.get("error"))
            for s in summary.get("steps", [])
        ],
    )


def _reconcile(data: dict | None) -> Reconcile | None:
    if not data:
        return None
    sides = [
        ReconcileSide(
            dataset=DATASET_VI.get(name, name),
            source_rows=data[name].get("source_row_count"),
            target_rows=data[name].get("target_row_count"),
            stations=data[name].get("station_count"),
        )
        for name in ("air_quality_hourly", "weather_openmeteo_hourly")
        if isinstance(data.get(name), dict)
    ]
    return Reconcile(ok=bool(data.get("ok")), errors=[str(e) for e in data.get("errors", [])], datasets=sides)


def _dbt_tests(log: Path) -> DbtTests | None:
    try:
        text = log.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    found = re.findall(r"PASS=(\d+) WARN=\d+ ERROR=(\d+) SKIP=\d+ TOTAL=(\d+)", text)
    if not found:
        return None
    passed, errors, total = (int(x) for x in found[-1])
    finished = datetime.fromtimestamp(log.stat().st_mtime, tz=timezone.utc)
    return DbtTests(passed=passed, errors=errors, total=total, finished_at=finished)


@router.get("/summary", response_model=QualitySummary)
def quality_summary(db: Session = Depends(get_db)) -> QualitySummary:
    missing_sql = ",\n".join(
        f"COUNT(*) FILTER (WHERE {col} IS NULL) AS miss_{col}"
        + (f", COUNT(*) FILTER (WHERE {src} = 'openmeteo') AS fill_{col}" if src else "")
        for col, _label, _kind, src, _t in COLUMNS
    )
    fact = fetch_one(
        db,
        f"""
        SELECT
            COUNT(*) AS fact_rows,
            COUNT(DISTINCT (station_key, event_time_local)) AS distinct_keys,
            COUNT(DISTINCT station_key) AS stations,
            MIN(event_time_local) AS first_hour,
            MAX(event_time_local) AS last_hour,
            {missing_sql}
        FROM dwh.fact_air_quality_hourly
        """,
    ) or {}
    status_counts = fetch_all(
        db,
        """
        SELECT data_quality_status AS status, COUNT(*) AS rows
        FROM dwh.fact_air_quality_hourly
        GROUP BY 1
        ORDER BY 2 DESC
        """,
    )
    sources = fetch_all(
        db,
        """
        SELECT source_system, COUNT(*) AS rows
        FROM staging.air_quality_hourly
        GROUP BY 1
        ORDER BY 2 DESC
        """,
    )
    loads = fetch_all(
        db,
        """
        SELECT dataset, COUNT(*) AS files, SUM(row_count) AS rows, MAX(loaded_at) AS last_loaded_at
        FROM staging.load_registry
        GROUP BY 1
        ORDER BY SUM(row_count) DESC, 1
        """,
    )

    columns = []
    for col, label, kind, src, treatment in COLUMNS:
        remaining = int(fact.get(f"miss_{col}") or 0)
        filled = int(fact.get(f"fill_{col}") or 0) if src else 0
        columns.append(
            ColumnMissing(
                column=col,
                label=label,
                kind=kind,
                missing_at_source=remaining + filled,
                filled=filled,
                remaining=remaining,
                treatment=treatment,
            )
        )

    art = _artifacts()
    return QualitySummary(
        warehouse=WarehouseCounts(
            fact_rows=int(fact.get("fact_rows") or 0),
            distinct_keys=int(fact.get("distinct_keys") or 0),
            stations=int(fact.get("stations") or 0),
            first_hour=fact.get("first_hour"),
            last_hour=fact.get("last_hour"),
        ),
        status_counts=[StatusCount(status=r["status"] or "—", rows=int(r["rows"])) for r in status_counts],
        sources=[SourceCount(source_system=r["source_system"] or "—", rows=int(r["rows"])) for r in sources],
        loads=[
            LoadBatch(
                dataset=DATASET_VI.get(r["dataset"], r["dataset"]),
                files=int(r["files"]),
                rows=int(r["rows"] or 0),
                last_loaded_at=r["last_loaded_at"],
            )
            for r in loads
        ],
        columns=columns,
        reconcile=_reconcile(_read_json(art / RECONCILE)),
        last_run=_run(_read_json(art / LAST_RUN)),
        last_full_run=_run(_read_json(art / LAST_FULL_RUN)),
        dbt_tests=_dbt_tests(art / DBT_TEST_LOG),
    )
