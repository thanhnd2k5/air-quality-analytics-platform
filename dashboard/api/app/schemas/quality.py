from datetime import datetime

from pydantic import BaseModel


class WarehouseCounts(BaseModel):
    fact_rows: int
    distinct_keys: int
    stations: int
    first_hour: datetime | None = None
    last_hour: datetime | None = None


class StatusCount(BaseModel):
    status: str
    rows: int


class SourceCount(BaseModel):
    source_system: str
    rows: int


class LoadBatch(BaseModel):
    dataset: str
    files: int
    rows: int
    last_loaded_at: datetime | None = None


class ColumnMissing(BaseModel):
    column: str
    label: str
    kind: str
    missing_at_source: int
    filled: int
    remaining: int
    treatment: str


class ReconcileSide(BaseModel):
    dataset: str
    source_rows: int | None = None
    target_rows: int | None = None
    stations: int | None = None


class Reconcile(BaseModel):
    ok: bool
    errors: list[str]
    datasets: list[ReconcileSide]


class PipelineStep(BaseModel):
    step: str
    status: str
    seconds: float | None = None
    error: str | None = None


class PipelineRun(BaseModel):
    ok: bool
    finished_at: datetime | None = None
    total_seconds: float | None = None
    scope: str
    steps: list[PipelineStep]


class DbtTests(BaseModel):
    passed: int
    errors: int
    total: int
    finished_at: datetime | None = None


class QualitySummary(BaseModel):
    warehouse: WarehouseCounts
    status_counts: list[StatusCount]
    sources: list[SourceCount]
    loads: list[LoadBatch]
    columns: list[ColumnMissing]
    # Read from artifacts/ (written by scripts/run_all.py); None when the file is absent.
    reconcile: Reconcile | None = None
    last_run: PipelineRun | None = None
    last_full_run: PipelineRun | None = None
    dbt_tests: DbtTests | None = None
