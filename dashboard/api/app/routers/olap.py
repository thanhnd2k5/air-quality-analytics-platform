"""Interactive OLAP over the star schema: roll-up, drill-down, slice, dice, pivot.

Rows / columns / filters / measure are whitelisted names (never raw SQL). Totals come
from GROUPING SETS. When every attribute used lives in mart.mart_olap_cube, the query is
answered from that pre-computed cuboid instead of scanning the 420k-row fact.
"""

from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.coerce import as_float
from app.db import fetch_all, get_db
from app.schemas.olap import OlapAttribute, OlapCell, OlapMeta, OlapResponse

router = APIRouter(prefix="/olap", tags=["olap"])

# attribute → (SQL expression on the star join, label, hierarchy)
ATTRS: dict[str, tuple[str, str, str]] = {
    "year": ("calendar.year::text", "Năm", "time"),
    "quarter": ("calendar.year || '-Q' || calendar.quarter", "Quý", "time"),
    "month": ("to_char(calendar.date_day, 'YYYY-MM')", "Tháng", "time"),
    "season": ("calendar.season", "Mùa", "season"),
    "day_part": ("tod.day_part", "Buổi", "daytime"),
    "hour": ("lpad(tod.hour::text, 2, '0')", "Giờ", "daytime"),
    "district": ("station.district", "Quận", "location"),
    "station": ("station.station_name", "Trạm", "location"),
    "wind_regime": ("wind.wind_regime", "Chế độ gió", "wind"),
    "wind_quadrant": ("wind.wind_quadrant", "Phần tư hướng gió", "wind"),
    "wind_direction": ("wind.wind_direction", "Hướng gió", "wind"),
}

HIERARCHIES: dict[str, list[str]] = {
    "time": ["year", "quarter", "month"],
    "season": ["season"],
    "daytime": ["day_part", "hour"],
    "location": ["district", "station"],
    "wind": ["wind_regime", "wind_quadrant", "wind_direction"],
}

MEASURES: dict[str, tuple[str, str, str]] = {
    # name → (expression on fact, expression on cube cells, label)
    "pm25_avg": (
        "avg(fact.pm25_ug_m3)",
        "sum(cube.pm25_sum) / nullif(sum(cube.pm25_hour_count), 0)",
        "PM2.5 trung bình (µg/m³)",
    ),
    "exceed_pct": (
        "100.0 * avg((fact.pm25_ug_m3 >= 115)::int)",
        "100.0 * sum(cube.pm25_exceed_hours) / nullif(sum(cube.pm25_hour_count), 0)",
        "% giờ PM2.5 ≥ 115",
    ),
    "hours": ("count(*)", "sum(cube.hour_count)", "Số giờ quan trắc"),
}

# Order of the attributes inside mart_olap_cube.cuboid ("year,season,district,day_part,wind_quadrant").
CUBE_ATTRS = ["year", "season", "district", "day_part", "wind_quadrant"]
CUBE_EXPR = {
    "year": "cube.year::text",
    "season": "cube.season",
    "district": "cube.district",
    "day_part": "cube.day_part",
    "wind_quadrant": "cube.wind_quadrant",
}

STAR_FROM = """
    from dwh.fact_air_quality_hourly as fact
    join dwh.dim_date as calendar on fact.date_key = calendar.date_key
    join dwh.dim_time as tod on fact.time_key = tod.time_key
    join dwh.dim_station as station on fact.station_key = station.station_key
    join dwh.dim_wind_direction as wind on fact.wind_direction_key = wind.wind_direction_key
"""

SEASON_ORDER = {"spring": 1, "summer": 2, "autumn": 3, "winter": 4}
DAYPART_ORDER = {"night": 1, "morning": 2, "afternoon": 3, "evening": 4}
REGIME_ORDER = {"northerly": 1, "southerly": 2}
QUADRANT_ORDER = {"NE": 1, "SE": 2, "SW": 3, "NW": 4}
COMPASS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def _sort_key(attr: str):
    orders = {
        "season": SEASON_ORDER,
        "day_part": DAYPART_ORDER,
        "wind_regime": REGIME_ORDER,
        "wind_quadrant": QUADRANT_ORDER,
        "wind_direction": {c: i for i, c in enumerate(COMPASS)},
    }.get(attr)
    if orders:
        return lambda v: (orders.get(v, 99), str(v))
    return lambda v: str(v)


def _parse_filters(raw: list[str]) -> dict[str, list[str]]:
    """'district:Dongcheng,Xicheng' → {'district': ['Dongcheng', 'Xicheng']}."""
    out: dict[str, list[str]] = {}
    for item in raw:
        if ":" not in item:
            raise HTTPException(400, f"filter phải có dạng thuộc_tính:giá_trị (nhận '{item}')")
        attr, values = item.split(":", 1)
        if attr not in ATTRS:
            raise HTTPException(400, f"thuộc tính lọc không hợp lệ: {attr}")
        vals = [v for v in values.split(",") if v]
        if vals:
            out.setdefault(attr, []).extend(vals)
    return out


@router.get("/meta", response_model=OlapMeta)
def olap_meta(db: Session = Depends(get_db)) -> OlapMeta:
    attributes = []
    for name, (expr, label, hierarchy) in ATTRS.items():
        members = fetch_all(db, f"select distinct {expr} as v {STAR_FROM} where {expr} is not null")
        values = sorted((r["v"] for r in members), key=_sort_key(name))
        attributes.append(OlapAttribute(name=name, label=label, hierarchy=hierarchy, members=values))
    return OlapMeta(
        attributes=attributes,
        hierarchies=HIERARCHIES,
        measures={k: v[2] for k, v in MEASURES.items()},
        cube_attributes=CUBE_ATTRS,
    )


@router.get("/query", response_model=OlapResponse)
def olap_query(
    db: Session = Depends(get_db),
    rows: str = Query("year"),
    cols: str | None = Query(None),
    measure: Literal["pm25_avg", "exceed_pct", "hours"] = Query("pm25_avg"),
    filter: list[str] = Query(default_factory=list),  # noqa: A002 — public query name
) -> OlapResponse:
    if rows not in ATTRS:
        raise HTTPException(400, f"rows không hợp lệ: {rows}")
    if cols is not None and (cols not in ATTRS or cols == rows):
        raise HTTPException(400, f"cols không hợp lệ: {cols}")
    filters = _parse_filters(filter)

    used = {rows, *filters}
    if cols:
        used.add(cols)
    use_cube = used.issubset(CUBE_ATTRS)

    params: dict = {}
    where = []
    for i, (attr, values) in enumerate(filters.items()):
        expr = CUBE_EXPR[attr] if use_cube else ATTRS[attr][0]
        where.append(f"{expr} = any(:f{i})")
        params[f"f{i}"] = values

    if use_cube:
        cuboid = ",".join(a for a in CUBE_ATTRS if a in used)
        params["cuboid"] = cuboid
        where.insert(0, "cube.cuboid = :cuboid")
        source = f"mart.mart_olap_cube — khối con ({cuboid}) đã tính trước"
        r_expr, c_expr = CUBE_EXPR[rows], CUBE_EXPR[cols] if cols else None
        m_expr = MEASURES[measure][1]
        from_sql = "from mart.mart_olap_cube as cube"
    else:
        cuboid = None
        source = "dwh.fact_air_quality_hourly ⋈ 4 bảng chiều (tính trực tiếp)"
        r_expr, c_expr = ATTRS[rows][0], ATTRS[cols][0] if cols else None
        m_expr = MEASURES[measure][0]
        from_sql = STAR_FROM

    if c_expr:
        group = f"grouping sets (({r_expr}, {c_expr}), ({r_expr}), ({c_expr}), ())"
        select = f"{r_expr} as r, {c_expr} as c, grouping({r_expr}, {c_expr}) as g"
    else:
        group = f"grouping sets (({r_expr}), ())"
        select = f"{r_expr} as r, null::text as c, grouping({r_expr}) * 2 + 1 as g"
    where_sql = f"where {' and '.join(where)}" if where else ""
    sql = f"select {select}, {m_expr} as v\n{from_sql}\n{where_sql}\ngroup by {group}"

    t0 = time.perf_counter()
    result = fetch_all(db, sql, params)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    cells, row_totals, col_totals, grand = [], {}, {}, None
    for r in result:
        value = as_float(r["v"])
        g = int(r["g"])
        if g == 0:
            cells.append(OlapCell(row=str(r["r"]), col=str(r["c"]), value=value))
        elif g == 1:  # column rolled up → row total
            row_totals[str(r["r"])] = value
        elif g == 2:  # row rolled up → column total
            col_totals[str(r["c"])] = value
        else:
            grand = value
    if not cols:
        cells = [OlapCell(row=k, col="", value=v) for k, v in row_totals.items()]

    row_members = sorted(row_totals, key=_sort_key(rows))
    col_members = sorted(col_totals, key=_sort_key(cols)) if cols else []

    return OlapResponse(
        rows=rows,
        cols=cols,
        measure=measure,
        measure_label=MEASURES[measure][2],
        filters=filters,
        source=source,
        cuboid=cuboid,
        sql=sql,
        elapsed_ms=round(elapsed_ms, 1),
        row_members=row_members,
        col_members=col_members,
        cells=cells,
        row_totals=row_totals,
        col_totals=col_totals,
        grand_total=grand,
    )
