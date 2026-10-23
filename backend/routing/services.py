"""Orchestrate geocode → routes → checkpoints → weather → risk → recommend."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from django.conf import settings

from .geo import geocode, sample_polyline
from .here_routing import fetch_routes
from .risk import aggregate_route_risk, classify_checkpoint, recommend_route
from .weather import build_corridor_heatmap, fetch_batch_forecasts, weather_at_time

logger = logging.getLogger(__name__)

VALID_INTERVALS = {10, 25, 50}


def analyze_trip(
    origin_query: str,
    destination_query: str,
    departure_iso: str,
    load_lbs: float,
    interval_miles: int = 25,
) -> dict[str, Any]:
    if interval_miles not in VALID_INTERVALS:
        raise ValueError("interval_miles must be 10, 25, or 50.")
    if load_lbs < 0:
        raise ValueError("load_lbs must be non-negative.")

    departure = _parse_departure(departure_iso)
    here_key = getattr(settings, "HERE_API_KEY", "") or ""
    provider = getattr(settings, "ROUTING_PROVIDER", "here")

    origin = geocode(origin_query, here_key)
    destination = geocode(destination_query, here_key)

    raw_routes = fetch_routes(
        origin,
        destination,
        api_key=here_key,
        provider=provider,
        alternatives=2,
        departure_iso=departure.isoformat(),
        load_lbs=load_lbs,
    )

    analyzed: list[dict[str, Any]] = []
    for route in raw_routes:
        analyzed.append(
            _analyze_single_route(route, departure, load_lbs, interval_miles)
        )

    recommendation = recommend_route(analyzed)

    heat_route = None
    if recommendation:
        heat_route = next(
            (r for r in analyzed if r["id"] == recommendation["route_id"]), None
        )
    if heat_route is None and analyzed:
        # Prefer a complete route for heatmap corridor when nothing is recommended
        heat_route = next(
            (r for r in analyzed if not r.get("weather_incomplete")),
            analyzed[0],
        )

    heatmap = (
        build_corridor_heatmap(
            heat_route["geometry"],
            sample_count=16,
            hours=49,
            load_lbs=load_lbs,
            departure=departure,
        )
        if heat_route
        else {"points": [], "hours": [], "grid": [], "base_time": None}
    )

    return {
        "origin": origin,
        "destination": destination,
        "departure": departure.isoformat(),
        "load_lbs": load_lbs,
        "interval_miles": interval_miles,
        "routes": analyzed,
        "recommendation": recommendation,
        "heatmap": heatmap,
        "routing_provider": analyzed[0]["provider"] if analyzed else None,
    }


def _analyze_single_route(
    route: dict[str, Any],
    departure: datetime,
    load_lbs: float,
    interval_miles: int,
) -> dict[str, Any]:
    samples = sample_polyline(route["geometry"], float(interval_miles))
    duration_s = route["duration_seconds"] or 1
    total_miles = route["distance_miles"] or 1.0

    for sample in samples:
        frac = sample["fraction"]
        eta = departure + timedelta(seconds=duration_s * frac)
        sample["eta"] = eta.isoformat()
        sample["_eta_dt"] = eta

    forecasts = fetch_batch_forecasts(
        [{"lat": s["lat"], "lon": s["lon"]} for s in samples]
    )

    checkpoints: list[dict[str, Any]] = []
    for sample, forecast in zip(samples, forecasts):
        try:
            wx = weather_at_time(forecast, sample["_eta_dt"])
        except Exception as exc:
            logger.warning("Weather lookup failed at checkpoint: %s", exc)
            wx = {
                "time": sample["eta"],
                "temperature_c": None,
                "wind_mph": None,
                "rain_in_hr": None,
                "snow_in_hr": None,
                "weather_code": None,
                "weather_valid": False,
                "weather_error": str(exc),
            }

        classified = classify_checkpoint(
            wx.get("wind_mph") if wx.get("weather_valid") else None,
            wx.get("rain_in_hr") if wx.get("weather_valid") else None,
            wx.get("snow_in_hr") if wx.get("weather_valid") else None,
            load_lbs,
            weather_valid=bool(wx.get("weather_valid")),
            weather_error=wx.get("weather_error"),
        )
        checkpoints.append(
            {
                "index": sample["index"],
                "lat": sample["lat"],
                "lon": sample["lon"],
                "distance_miles": sample["distance_miles"],
                "fraction": sample["fraction"],
                "eta": sample["eta"],
                "weather": {
                    k: v
                    for k, v in wx.items()
                    if k
                    not in (
                        "weather_valid",
                        "weather_error",
                        "forecast_skew_seconds",
                    )
                }
                | {
                    "weather_valid": wx.get("weather_valid", False),
                    "weather_error": wx.get("weather_error"),
                },
                **classified,
            }
        )

    agg = aggregate_route_risk(checkpoints, float(interval_miles))

    return {
        **{k: v for k, v in route.items() if k != "geometry"},
        "geometry": route["geometry"],
        "checkpoints": checkpoints,
        "checkpoint_count": len(checkpoints),
        **agg,
        "total_miles": total_miles,
        "eta_destination": (
            departure + timedelta(seconds=duration_s)
        ).isoformat(),
    }


def _parse_departure(value: str) -> datetime:
    if not value:
        raise ValueError("departure is required (ISO-8601).")
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("Invalid departure datetime. Use ISO-8601.") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
