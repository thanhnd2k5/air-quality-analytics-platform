"""Phase 10 kickoff smoke checks against DWH / mart."""

from __future__ import annotations

from typing import Any

from src.eda.db import fetch_dicts
from src.forecasting.constants import (
    EXPECTED_CLUSTERS,
    EXPECTED_STATIONS,
    ML_END,
    ML_START,
    TEST_END,
    TEST_START,
    TRAIN_END,
    VAL_END,
    VAL_START,
)


def smoke_forecasting_prereqs() -> dict[str, Any]:
    """Gate P10a: fact in ML window, 12 stations, cluster mart joinable."""
    fact_sql = """
        select
            count(*)::bigint as row_count,
            count(distinct station_key)::int as station_count,
            min(event_time_local) as min_event_time,
            max(event_time_local) as max_event_time,
            count(pm25_ug_m3)::bigint as pm25_non_null
        from dwh.fact_air_quality_hourly
        where event_time_local >= %(start)s::timestamp
          and event_time_local <= %(end)s::timestamp
    """
    params = {"start": ML_START, "end": ML_END}
    fact_rows = fetch_dicts(fact_sql, params)
    fact = fact_rows[0] if fact_rows else {}

    split_sql = """
        select
            count(*) filter (
                where event_time_local >= %(ml_start)s::timestamp
                  and event_time_local <= %(train_end)s::timestamp
            )::bigint as train_rows,
            count(*) filter (
                where event_time_local >= %(val_start)s::timestamp
                  and event_time_local <= %(val_end)s::timestamp
            )::bigint as val_rows,
            count(*) filter (
                where event_time_local >= %(test_start)s::timestamp
                  and event_time_local <= %(test_end)s::timestamp
            )::bigint as test_rows
        from dwh.fact_air_quality_hourly
        where event_time_local >= %(ml_start)s::timestamp
          and event_time_local <= %(ml_end)s::timestamp
    """
    split_params = {
        "ml_start": ML_START,
        "ml_end": ML_END,
        "train_end": TRAIN_END,
        "val_start": VAL_START,
        "val_end": VAL_END,
        "test_start": TEST_START,
        "test_end": TEST_END,
    }
    split_rows = fetch_dicts(split_sql, split_params)
    split_counts = split_rows[0] if split_rows else {}

    cluster_sql = """
        select
            count(*)::int as cluster_row_count,
            count(distinct station_key)::int as station_count,
            count(distinct cluster_id)::int as cluster_id_count
        from mart.mart_station_cluster
    """
    cluster_rows = fetch_dicts(cluster_sql)
    cluster = cluster_rows[0] if cluster_rows else {}

    join_sql = """
        select count(*)::bigint as joined_rows
        from dwh.fact_air_quality_hourly as fact
        inner join mart.mart_station_cluster as cl
            on fact.station_key = cl.station_key
        where fact.event_time_local >= %(start)s::timestamp
          and fact.event_time_local <= %(end)s::timestamp
    """
    join_rows = fetch_dicts(join_sql, params)
    joined = join_rows[0].get("joined_rows") if join_rows else None

    station_count = int(fact.get("station_count") or 0)
    row_count = int(fact.get("row_count") or 0)
    cluster_stations = int(cluster.get("station_count") or 0)
    cluster_ids = int(cluster.get("cluster_id_count") or 0)
    train_rows = int(split_counts.get("train_rows") or 0)
    val_rows = int(split_counts.get("val_rows") or 0)
    test_rows = int(split_counts.get("test_rows") or 0)
    joined_n = int(joined) if joined is not None else 0

    ok = (
        station_count == EXPECTED_STATIONS
        and row_count > 0
        and cluster_stations == EXPECTED_STATIONS
        and cluster_ids == EXPECTED_CLUSTERS
        and joined_n == row_count
        and train_rows > 0
        and val_rows > 0
        and test_rows > 0
    )

    def _ser(v: Any) -> Any:
        return v.isoformat(sep=" ") if hasattr(v, "isoformat") else v

    return {
        "ok": ok,
        "phase": "P10a",
        "target": "pm25_ug_m3(t+1h)",
        "ml_window": {"start": ML_START, "end": ML_END},
        "split": {
            "train": {"start": ML_START, "end": TRAIN_END},
            "val": {"start": VAL_START, "end": VAL_END},
            "test": {"start": TEST_START, "end": TEST_END},
            "exclude_from_primary": "2017 (partial / winter-biased)",
        },
        "expected_station_count": EXPECTED_STATIONS,
        "expected_cluster_id_count": EXPECTED_CLUSTERS,
        "fact_in_ml_window": {k: _ser(v) for k, v in fact.items()},
        "split_row_counts": {
            "train_rows": train_rows,
            "val_rows": val_rows,
            "test_rows": test_rows,
        },
        "mart_station_cluster": {
            "row_count": int(cluster.get("cluster_row_count") or 0),
            "station_count": cluster_stations,
            "cluster_id_count": cluster_ids,
        },
        "fact_cluster_join_rows": joined_n,
    }
