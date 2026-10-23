"""Compact API payloads for /analyze without dropping required fields."""

from __future__ import annotations

from typing import Any

from .geo import simplify_polyline


def compact_analyze_response(result: dict[str, Any], max_geometry_points: int = 400) -> dict[str, Any]:
    """
    Shrink JSON size:
      - simplify route geometries
      - trim checkpoint weather noise
      - compress heatmap grid to risk scores + compact weather
    """
    routes = []
    for route in result.get("routes") or []:
        geometry = simplify_polyline(route.get("geometry") or [], max_geometry_points)
        checkpoints = [_compact_checkpoint(cp) for cp in route.get("checkpoints") or []]
        routes.append(
            {
                **{k: v for k, v in route.items() if k not in ("geometry", "checkpoints")},
                "geometry": geometry,
                "checkpoints": checkpoints,
            }
        )

    heatmap = _compact_heatmap(result.get("heatmap") or {})

    return {
        "origin": result.get("origin"),
        "destination": result.get("destination"),
        "departure": result.get("departure"),
        "load_lbs": result.get("load_lbs"),
        "interval_miles": result.get("interval_miles"),
        "routes": routes,
        "recommendation": result.get("recommendation"),
        "heatmap": heatmap,
        "routing_provider": result.get("routing_provider"),
    }


def _compact_checkpoint(cp: dict[str, Any]) -> dict[str, Any]:
    wx = cp.get("weather") or {}
    return {
        "index": cp.get("index"),
        "lat": round(float(cp["lat"]), 5) if cp.get("lat") is not None else None,
        "lon": round(float(cp["lon"]), 5) if cp.get("lon") is not None else None,
        "distance_miles": cp.get("distance_miles"),
        "fraction": cp.get("fraction"),
        "eta": cp.get("eta"),
        "weather": {
            "time": wx.get("time"),
            "temperature_c": wx.get("temperature_c"),
            "wind_mph": wx.get("wind_mph"),
            "rain_in_hr": wx.get("rain_in_hr"),
            "snow_in_hr": wx.get("snow_in_hr"),
            "weather_valid": wx.get("weather_valid", cp.get("weather_valid", True)),
            "weather_error": wx.get("weather_error") or cp.get("weather_error"),
        },
        "wind_risk": cp.get("wind_risk"),
        "rain_risk": cp.get("rain_risk"),
        "snow_risk": cp.get("snow_risk"),
        "overall_risk": cp.get("overall_risk"),
        "risk_score": cp.get("risk_score"),
        "weather_valid": cp.get("weather_valid", wx.get("weather_valid", True)),
        "weather_error": cp.get("weather_error") or wx.get("weather_error"),
    }


def _compact_heatmap(heatmap: dict[str, Any]) -> dict[str, Any]:
    """
    Replace verbose grid cells with parallel arrays:
      risk[point][hour], wind/rain/snow optional sparse — keep risk + valid flags.
    Frontend expands this back for rendering.
    """
    points = []
    for p in heatmap.get("points") or []:
        points.append(
            {
                "lat": round(float(p["lat"]), 5),
                "lon": round(float(p["lon"]), 5),
                "index": p.get("index"),
                "distance_miles": p.get("distance_miles"),
            }
        )

    grid = heatmap.get("grid") or []
    risk: list[list[str]] = []
    wind: list[list[float | None]] = []
    rain: list[list[float | None]] = []
    snow: list[list[float | None]] = []
    valid: list[list[bool]] = []

    for row in grid:
        r_risk: list[str] = []
        r_wind: list[float | None] = []
        r_rain: list[float | None] = []
        r_snow: list[float | None] = []
        r_valid: list[bool] = []
        for cell in row:
            r_risk.append(cell.get("overall_risk") or "Unknown")
            r_wind.append(cell.get("wind_mph"))
            r_rain.append(cell.get("rain_in_hr"))
            r_snow.append(cell.get("snow_in_hr"))
            r_valid.append(bool(cell.get("weather_valid", True)))
        risk.append(r_risk)
        wind.append(r_wind)
        rain.append(r_rain)
        snow.append(r_snow)
        valid.append(r_valid)

    return {
        "points": points,
        "hours": heatmap.get("hours") or list(range(49)),
        "base_time": heatmap.get("base_time"),
        "format": "compact_v1",
        "risk": risk,
        "wind": wind,
        "rain": rain,
        "snow": snow,
        "valid": valid,
    }
