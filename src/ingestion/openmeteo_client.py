"""Open-Meteo Historical Weather API client (Phase 5)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from typing import Any, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

SOURCE_IDENTIFIER = "openmeteo_historical"
DEFAULT_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"
DEFAULT_TIMEZONE = "Asia/Shanghai"

# Hourly variables for enrichment + UCI overlap fill (DATA_GUIDE §24)
DEFAULT_HOURLY_VARIABLES: tuple[str, ...] = (
    "temperature_2m",
    "dew_point_2m",
    "rain",
    "wind_speed_10m",
    "wind_direction_10m",
    "surface_pressure",
    "cloud_cover",
)

# Explicit units: wind m/s (UCI WSPM), temp °C, precip mm
DEFAULT_UNITS: dict[str, str] = {
    "temperature_unit": "celsius",
    "wind_speed_unit": "ms",
    "precipitation_unit": "mm",
}


@dataclass(frozen=True)
class OpenMeteoRequestMeta:
    station: str
    requested_latitude: float
    requested_longitude: float
    returned_latitude: float | None
    returned_longitude: float | None
    timezone: str
    start_date: str
    end_date: str
    weather_model: str | None
    hourly_variables: list[str]
    units: dict[str, str]
    request_url: str
    request_time: str
    http_status: int
    source: str = SOURCE_IDENTIFIER

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OpenMeteoFetchResult:
    payload: dict[str, Any]
    meta: OpenMeteoRequestMeta
    raw_bytes: bytes

    def to_dict(self) -> dict[str, Any]:
        return {
            "meta": self.meta.to_dict(),
            "byte_size": len(self.raw_bytes),
            "hourly_keys": sorted((self.payload.get("hourly") or {}).keys()),
        }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _normalize_day(value: str | date) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return value


def build_archive_url(
    *,
    latitude: float,
    longitude: float,
    start_date: str | date,
    end_date: str | date,
    hourly: Sequence[str] = DEFAULT_HOURLY_VARIABLES,
    timezone: str = DEFAULT_TIMEZONE,
    base_url: str = DEFAULT_BASE_URL,
    units: dict[str, str] | None = None,
) -> str:
    unit_params = dict(DEFAULT_UNITS if units is None else units)
    params: dict[str, str] = {
        "latitude": f"{latitude:.6f}",
        "longitude": f"{longitude:.6f}",
        "start_date": _normalize_day(start_date),
        "end_date": _normalize_day(end_date),
        "hourly": ",".join(hourly),
        "timezone": timezone,
        **unit_params,
    }
    return f"{base_url}?{urlencode(params)}"


def fetch_historical_weather(
    *,
    station: str,
    latitude: float,
    longitude: float,
    start_date: str | date,
    end_date: str | date,
    hourly: Sequence[str] = DEFAULT_HOURLY_VARIABLES,
    timezone: str = DEFAULT_TIMEZONE,
    base_url: str = DEFAULT_BASE_URL,
    units: dict[str, str] | None = None,
    timeout_s: float = 120.0,
) -> OpenMeteoFetchResult:
    """GET archive API; return JSON payload + request metadata (DATA_GUIDE §28)."""
    url = build_archive_url(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        hourly=hourly,
        timezone=timezone,
        base_url=base_url,
        units=units,
    )
    request_time = _utc_now_iso()
    req = Request(url, headers={"User-Agent": "air-quality-analytics-platform/phase5"})
    try:
        with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — fixed HTTPS API
            status = getattr(resp, "status", 200) or 200
            raw = resp.read()
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise RuntimeError(f"Open-Meteo HTTP {exc.code}: {body[:500]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Open-Meteo request failed: {exc}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Open-Meteo response is not JSON: {exc}") from exc

    hourly_units = payload.get("hourly_units") or {}
    model = payload.get("model")
    meta = OpenMeteoRequestMeta(
        station=station,
        requested_latitude=latitude,
        requested_longitude=longitude,
        returned_latitude=payload.get("latitude"),
        returned_longitude=payload.get("longitude"),
        timezone=str(payload.get("timezone") or timezone),
        start_date=_normalize_day(start_date),
        end_date=_normalize_day(end_date),
        weather_model=model if isinstance(model, str) else None,
        hourly_variables=list(hourly),
        units={
            **(units or DEFAULT_UNITS),
            **{f"hourly.{k}": str(v) for k, v in hourly_units.items()},
        },
        request_url=url,
        request_time=request_time,
        http_status=int(status),
    )

    return OpenMeteoFetchResult(payload=payload, meta=meta, raw_bytes=raw)


def hourly_to_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten Open-Meteo hourly block into list of dict rows."""
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    keys = [k for k in hourly.keys() if k != "time"]
    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(times):
        row: dict[str, Any] = {"time": ts}
        for key in keys:
            values = hourly.get(key) or []
            row[key] = values[i] if i < len(values) else None
        rows.append(row)
    return rows
