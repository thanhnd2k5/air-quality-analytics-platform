"""Locked station clusters (Phase 9): membership from the mart, profiles from daily aggregates."""

import csv
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.artifacts import artifacts_path
from app.coerce import as_float
from app.db import fetch_all, get_db
from app.errors import EmptyMartError
from app.schemas.clusters import ClusterGroup, ClusterStation, ClustersResponse, KSelectionPoint

router = APIRouter(prefix="/clusters", tags=["clusters"])

# Fit window and silhouette are the locked KMeans result, not recomputed on each request.
WINDOW_FROM = date(2013, 3, 1)
WINDOW_TO = date(2016, 12, 31)
SILHOUETTE = 0.663653697101863

# Locked grid from artifacts/clustering/k_selection_metrics.csv. Not refit per request.
K_GRID = [
    KSelectionPoint(method="kmeans", k=2, silhouette=0.663653697101863, inertia=44.445155555267654),
    KSelectionPoint(method="kmeans", k=3, silhouette=0.3449713073022196, inertia=32.32724064640235),
    KSelectionPoint(method="kmeans", k=4, silhouette=0.2774026703919882, inertia=21.480962652093716),
    KSelectionPoint(method="agglomerative_ward", k=2, silhouette=0.663653697101863),
    KSelectionPoint(method="agglomerative_ward", k=3, silhouette=0.3856086767531035),
    KSelectionPoint(method="agglomerative_ward", k=4, silhouette=0.3256200815572777),
]


def _k_grid() -> list[KSelectionPoint]:
    """Silhouette for every K (scripts/clustering_k_sweep.py); the locked grid if that file is absent."""
    try:
        with (artifacts_path() / "clustering" / "k_selection_extended.csv").open(encoding="utf-8") as fh:
            return [
                KSelectionPoint(
                    method=r["method"],
                    k=int(r["k"]),
                    silhouette=float(r["silhouette"]),
                    inertia=float(r["inertia"]) if r["inertia"] else None,
                )
                for r in csv.DictReader(fh)
            ]
    except (OSError, KeyError, ValueError):
        return K_GRID


LABEL_VI = {
    "elevated_core": "Nhóm A · ô nhiễm nặng",
    "cleaner_outskirts": "Nhóm B · ô nhiễm nhẹ hơn",
}


@router.get("", response_model=ClustersResponse)
def list_clusters(db: Session = Depends(get_db)) -> ClustersResponse:
    stations = fetch_all(
        db,
        """
        SELECT station_key, station_name, district, cluster_id, cluster_label, method, k
        FROM mart.mart_station_cluster
        ORDER BY cluster_id, station_name
        """,
    )
    if not stations:
        raise EmptyMartError("mart.mart_station_cluster is empty")

    profiles = fetch_all(
        db,
        """
        SELECT
            c.cluster_id,
            SUM(d.pm25_ug_m3_avg * d.pm25_hour_count)
                / NULLIF(SUM(d.pm25_hour_count), 0) AS pm25_avg,
            SUM(d.no2_ug_m3_avg * d.no2_hour_count)
                / NULLIF(SUM(d.no2_hour_count), 0) AS no2_avg,
            SUM(d.co_ug_m3_avg * d.co_hour_count)
                / NULLIF(SUM(d.co_hour_count), 0) AS co_avg
        FROM mart.mart_station_cluster AS c
        JOIN mart.mart_station_daily AS d ON d.station_key = c.station_key
        WHERE d.date_day >= :window_from
          AND d.date_day <= :window_to
        GROUP BY c.cluster_id
        """,
        {"window_from": WINDOW_FROM, "window_to": WINDOW_TO},
    )
    by_id = {row["cluster_id"]: row for row in profiles}

    groups: dict[int, ClusterGroup] = {}
    for row in stations:
        cluster_id = row["cluster_id"]
        group = groups.get(cluster_id)
        if group is None:
            profile = by_id.get(cluster_id, {})
            label = row["cluster_label"]
            group = ClusterGroup(
                cluster_id=cluster_id,
                cluster_label=label,
                label_vi=LABEL_VI.get(label, label),
                n_stations=0,
                pm25_avg=as_float(profile.get("pm25_avg")),
                no2_avg=as_float(profile.get("no2_avg")),
                co_avg=as_float(profile.get("co_avg")),
                stations=[],
            )
            groups[cluster_id] = group
        group.stations.append(
            ClusterStation(
                station_key=row["station_key"],
                station_name=row["station_name"],
                district=row["district"],
            )
        )
        group.n_stations += 1

    return ClustersResponse(
        method=stations[0]["method"],
        k=stations[0]["k"],
        silhouette=SILHOUETTE,
        window_from=WINDOW_FROM,
        window_to=WINDOW_TO,
        k_grid=_k_grid(),
        groups=list(groups.values()),
    )
