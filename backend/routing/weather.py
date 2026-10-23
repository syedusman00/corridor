"""Open-Meteo weather forecasts for route checkpoints and corridor heatmap."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .geo import sample_polyline

logger = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Reject forecast hours farther than this from the requested ETA
MAX_FORECAST_SKEW_SECONDS = 2 * 3600


def fetch_hourly_forecast(lat: float, lon: float) -> dict[str, Any]:
    """Fetch hourly weather for a point (wind mph, precip inch, snow cm→in)."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(
            [
                "temperature_2m",
                "precipitation",
                "snowfall",
                "rain",
                "showers",
                "wind_speed_10m",
                "weather_code",
            ]
        ),
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "forecast_days": 3,
    }
    resp = requests.get(FORECAST_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def weather_at_time(forecast: dict[str, Any], when: datetime) -> dict[str, Any]:
    """
    Pick the hourly slot closest to `when` (UTC-aware).

    Returns weather_valid=False when data is missing or the closest hour
    is outside MAX_FORECAST_SKEW_SECONDS (out-of-range). Never invents Low.
    """
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    else:
        when = when.astimezone(timezone.utc)

    hourly = forecast.get("hourly") or {}
    times = hourly.get("time") or []
    if not times:
        return _invalid_weather(when, "Forecast has no hourly data")

    target = when.replace(minute=0, second=0, microsecond=0)
    best_idx = None
    best_delta = None
    for i, t in enumerate(times):
        try:
            ht = datetime.fromisoformat(t).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        delta = abs((ht - target).total_seconds())
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = i

    if best_idx is None or best_delta is None:
        return _invalid_weather(when, "Could not parse forecast times")

    if best_delta > MAX_FORECAST_SKEW_SECONDS:
        return _invalid_weather(
            when,
            f"Requested time outside forecast range (skew={int(best_delta)}s)",
        )

    wind, wind_ok = _optional_float(hourly.get("wind_speed_10m"), best_idx)
    rain_v, rain_ok = _optional_float(hourly.get("rain"), best_idx)
    showers_v, showers_ok = _optional_float(hourly.get("showers"), best_idx)
    precip, precip_ok = _optional_float(hourly.get("precipitation"), best_idx)
    snow_raw, snow_ok = _optional_float(hourly.get("snowfall"), best_idx)

    # Wind is required for classification; missing wind ⇒ Unknown
    if not wind_ok:
        return _invalid_weather(when, "Missing wind_speed_10m for hour")

    rain = 0.0
    if rain_ok or showers_ok:
        rain = (rain_v or 0.0) + (showers_v or 0.0)
    elif precip_ok:
        rain = precip or 0.0
    else:
        # Treat missing precip series as 0 only when wind exists (dry hour)
        rain = 0.0

    # Open-Meteo snowfall is cm regardless of precipitation_unit
    snow_in = (snow_raw / 2.54) if snow_ok and snow_raw is not None else 0.0

    temp, _ = _optional_float(hourly.get("temperature_2m"), best_idx)
    code = None
    codes = hourly.get("weather_code") or []
    if best_idx < len(codes):
        code = codes[best_idx]

    return {
        "time": times[best_idx],
        "temperature_c": temp,
        "wind_mph": round(float(wind), 2),
        "rain_in_hr": round(float(rain), 4),
        "snow_in_hr": round(float(snow_in), 4),
        "weather_code": code,
        "weather_valid": True,
        "weather_error": None,
        "forecast_skew_seconds": int(best_delta),
    }


def fetch_batch_forecasts(
    points: list[dict[str, float]],
) -> list[dict[str, Any]]:
    """Fetch forecasts for many points (batched Open-Meteo multi-location)."""
    if not points:
        return []

    results: list[dict[str, Any] | None] = [None] * len(points)
    batch_size = 40

    for start in range(0, len(points), batch_size):
        batch = points[start : start + batch_size]
        lats = ",".join(str(p["lat"]) for p in batch)
        lons = ",".join(str(p["lon"]) for p in batch)
        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": (
                "temperature_2m,precipitation,snowfall,rain,showers,"
                "wind_speed_10m,weather_code"
            ),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "UTC",
            "forecast_days": 3,
        }
        try:
            resp = requests.get(FORECAST_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            items = data if isinstance(data, list) else [data]
            for offset, item in enumerate(items):
                results[start + offset] = item
        except Exception as exc:
            logger.warning(
                "Batch weather fetch failed: %s — falling back per-point.", exc
            )
            for offset, point in enumerate(batch):
                try:
                    results[start + offset] = fetch_hourly_forecast(
                        point["lat"], point["lon"]
                    )
                except Exception as inner:
                    logger.error("Weather failed for %s: %s", point, inner)
                    results[start + offset] = _empty_forecast()

    return [r or _empty_forecast() for r in results]


def build_corridor_heatmap(
    geometry: list[list[float]],
    sample_count: int = 24,
    hours: int = 49,
    load_lbs: float = 0.0,
    departure: datetime | None = None,
) -> dict[str, Any]:
    """
    Sample points evenly by distance along the corridor and return risk
    for each hour offset 0..48 from the trip departure (not wall-clock now).
    """
    from .risk import RISK_RANK, classify_checkpoint

    if not geometry:
        return {
            "points": [],
            "hours": list(range(hours)),
            "grid": [],
            "base_time": None,
        }

    if departure is None:
        departure = datetime.now(timezone.utc)
    if departure.tzinfo is None:
        departure = departure.replace(tzinfo=timezone.utc)
    else:
        departure = departure.astimezone(timezone.utc)

    base = departure.replace(minute=0, second=0, microsecond=0)

    # Distance-based sampling via shared polyline sampler
    total_mi = 0.0
    for a, b in zip(geometry, geometry[1:]):
        from .geo import haversine_miles

        total_mi += haversine_miles(a[1], a[0], b[1], b[0])

    if sample_count <= 1 or total_mi <= 0:
        interval = max(total_mi, 1.0)
    else:
        interval = total_mi / (sample_count - 1)

    samples = sample_polyline(geometry, max(interval, 0.01))
    points = [{"lat": s["lat"], "lon": s["lon"]} for s in samples]
    forecasts = fetch_batch_forecasts(points)

    grid: list[list[dict[str, Any]]] = []
    for forecast in forecasts:
        row: list[dict[str, Any]] = []
        for h in range(hours):
            when = base + timedelta(hours=h)
            try:
                wx = weather_at_time(forecast, when)
            except Exception as exc:
                wx = _invalid_weather(when, str(exc))

            classified = classify_checkpoint(
                wx.get("wind_mph") if wx.get("weather_valid") else None,
                wx.get("rain_in_hr") if wx.get("weather_valid") else None,
                wx.get("snow_in_hr") if wx.get("weather_valid") else None,
                load_lbs=load_lbs,
                weather_valid=bool(wx.get("weather_valid")),
                weather_error=wx.get("weather_error"),
            )
            row.append(
                {
                    "hour_offset": h,
                    "time": wx.get("time"),
                    "wind_mph": wx.get("wind_mph"),
                    "rain_in_hr": wx.get("rain_in_hr"),
                    "snow_in_hr": wx.get("snow_in_hr"),
                    "overall_risk": classified["overall_risk"],
                    "risk_score": RISK_RANK[classified["overall_risk"]],
                    "weather_valid": classified.get("weather_valid", False),
                }
            )
        grid.append(row)

    return {
        "points": [
            {
                "lat": p["lat"],
                "lon": p["lon"],
                "index": i,
                "distance_miles": samples[i].get("distance_miles"),
            }
            for i, p in enumerate(points)
        ],
        "hours": list(range(hours)),
        "grid": grid,
        "base_time": base.isoformat(),
    }


def _invalid_weather(when: datetime, reason: str) -> dict[str, Any]:
    return {
        "time": when.astimezone(timezone.utc).isoformat(),
        "temperature_c": None,
        "wind_mph": None,
        "rain_in_hr": None,
        "snow_in_hr": None,
        "weather_code": None,
        "weather_valid": False,
        "weather_error": reason,
        "forecast_skew_seconds": None,
    }


def _empty_forecast() -> dict[str, Any]:
    return {
        "hourly": {
            "time": [],
            "temperature_2m": [],
            "precipitation": [],
            "snowfall": [],
            "rain": [],
            "showers": [],
            "wind_speed_10m": [],
            "weather_code": [],
        }
    }


def _optional_float(
    series: list | None, idx: int
) -> tuple[float | None, bool]:
    """Return (value, ok). ok=False when missing/null — not coerced to 0."""
    if not series or idx >= len(series) or series[idx] is None:
        return None, False
    try:
        return float(series[idx]), True
    except (TypeError, ValueError):
        return None, False
