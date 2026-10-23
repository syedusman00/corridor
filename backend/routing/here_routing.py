"""HERE Routing API (truck mode) with OSRM fallback (up to 3 real alternatives)."""

from __future__ import annotations

import logging
import math
from typing import Any

import flexpolyline
import requests

from .geo import decode_osrm_polyline, haversine_miles

logger = logging.getLogger(__name__)

HERE_ROUTES_URL = "https://router.hereapi.com/v8/routes"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
TARGET_ROUTE_COUNT = 3
# Geometry overlap above this ⇒ duplicate corridor
GEOMETRY_OVERLAP_REJECT = 0.88
# Secondary similarity (only when overlap is moderate)
MIN_ROUTE_DISTANCE_DELTA_MI = 40.0
MIN_ROUTE_DURATION_DELTA_S = 1200
# Typical empty tractor+trailer tare (lbs); load_lbs is cargo
TRACTOR_TRAILER_TARE_LBS = 32_000
# HERE vehicle[grossWeight] clamp (kg)
GROSS_WEIGHT_KG_MIN = 3_500
GROSS_WEIGHT_KG_MAX = 60_000


def truck_gross_weight_kg(load_lbs: float | None) -> int:
    """
    HERE vehicle[grossWeight] in kg = empty tractor+trailer tare + cargo.

    Assessment `load_lbs` is cargo only — do not treat it as GVW by itself.
    """
    cargo_lbs = max(float(load_lbs or 0), 0.0)
    gross_lbs = TRACTOR_TRAILER_TARE_LBS + cargo_lbs
    gross_kg = int(round(gross_lbs / 2.20462))
    return max(GROSS_WEIGHT_KG_MIN, min(gross_kg, GROSS_WEIGHT_KG_MAX))


def fetch_routes(
    origin: dict,
    destination: dict,
    api_key: str = "",
    provider: str = "here",
    alternatives: int = 2,
    departure_iso: str | None = None,
    load_lbs: float | None = None,
) -> list[dict[str, Any]]:
    """
    Return up to 3 route alternatives from a real routing API.

    HERE: alternatives=N means N routes *in addition to* the optimal route,
    so alternatives=2 requests up to 3 truck routes.
    OSRM: native alternatives plus via-point queries when fewer than 3 exist.
    """
    if provider == "here" and api_key:
        try:
            routes = _here_truck_routes(
                origin,
                destination,
                api_key,
                alternatives=alternatives,
                departure_iso=departure_iso,
                load_lbs=load_lbs,
            )
            if routes:
                return routes[:TARGET_ROUTE_COUNT]
            logger.warning("HERE returned no routes; falling back to OSRM.")
        except Exception as exc:
            logger.warning("HERE routing failed (%s); falling back to OSRM.", exc)

    return _osrm_routes(origin, destination, alternatives)[:TARGET_ROUTE_COUNT]


def _here_truck_routes(
    origin: dict,
    destination: dict,
    api_key: str,
    alternatives: int,
    departure_iso: str | None = None,
    load_lbs: float | None = None,
) -> list[dict[str, Any]]:
    """
    Request truck routes from HERE.

    Primary call: transportMode=truck, alternatives=2 → up to 3 routes.
    If fewer than 3, also request routingMode=short and merge distinct results.
    """
    collected: list[dict[str, Any]] = []

    # alternatives=2 → optimal + 2 alts = up to 3
    alt_count = max(alternatives, TARGET_ROUTE_COUNT - 1)
    primary = _here_request(
        origin,
        destination,
        api_key,
        alternatives=alt_count,
        routing_mode="fast",
        departure_iso=departure_iso,
        load_lbs=load_lbs,
    )
    for route in primary:
        _merge_distinct_route(collected, route)

    if len(collected) < TARGET_ROUTE_COUNT:
        short_routes = _here_request(
            origin,
            destination,
            api_key,
            alternatives=0,
            routing_mode="short",
            departure_iso=departure_iso,
            load_lbs=load_lbs,
        )
        for route in short_routes:
            _merge_distinct_route(collected, route)

    # Re-id sequentially
    for i, route in enumerate(collected[:TARGET_ROUTE_COUNT]):
        route["id"] = f"route-{i + 1}"
        route["summary"] = f"Truck route {i + 1}"

    return collected[:TARGET_ROUTE_COUNT]


def _here_request(
    origin: dict,
    destination: dict,
    api_key: str,
    alternatives: int,
    routing_mode: str,
    departure_iso: str | None,
    load_lbs: float | None,
) -> list[dict[str, Any]]:
    gross_kg = truck_gross_weight_kg(load_lbs)

    params: dict[str, Any] = {
        "transportMode": "truck",
        "origin": f"{origin['lat']},{origin['lon']}",
        "destination": f"{destination['lat']},{destination['lon']}",
        "return": "polyline,summary,actions",
        "alternatives": alternatives,
        "routingMode": routing_mode,
        "spans": "length,duration",
        "apiKey": api_key,
        # HERE v8 truck: grossWeight in kg (includes trailers)
        "vehicle[grossWeight]": gross_kg,
        "vehicle[height]": 400,  # cm
        "vehicle[width]": 260,  # cm (~102 in)
        "vehicle[length]": 1600,  # cm
        "vehicle[axleCount]": 5,
    }
    if departure_iso:
        # HERE expects RFC3339; strip microseconds if present
        params["departureTime"] = departure_iso.replace(" ", "T")

    resp = requests.get(HERE_ROUTES_URL, params=params, timeout=45)
    if resp.status_code >= 400:
        logger.error("HERE error %s: %s", resp.status_code, resp.text[:500])
        resp.raise_for_status()

    payload = resp.json()
    routes_raw = payload.get("routes") or []
    routes: list[dict[str, Any]] = []

    for i, route in enumerate(routes_raw[: alternatives + 1]):
        parsed = _parse_here_route(route, index=i, routing_mode=routing_mode)
        if parsed:
            routes.append(parsed)

    return routes


def _parse_here_route(
    route: dict[str, Any],
    index: int,
    routing_mode: str,
) -> dict[str, Any] | None:
    sections = route.get("sections") or []
    if not sections:
        return None

    coords: list[list[float]] = []
    distance_m = 0
    duration_s = 0

    for section in sections:
        poly = section.get("polyline")
        if poly:
            decoded = flexpolyline.decode(poly)
            section_coords = [[lon, lat] for lat, lon in decoded]
            if coords and section_coords:
                if (
                    abs(coords[-1][0] - section_coords[0][0]) < 1e-8
                    and abs(coords[-1][1] - section_coords[0][1]) < 1e-8
                ):
                    section_coords = section_coords[1:]
            coords.extend(section_coords)

        summary = section.get("summary") or {}
        distance_m += int(summary.get("length") or 0)
        duration_s += int(summary.get("duration") or 0)

    if not coords:
        return None

    if distance_m <= 0:
        distance_m = int(
            sum(
                haversine_miles(a[1], a[0], b[1], b[0])
                for a, b in zip(coords, coords[1:])
            )
            * 1609.344
        )

    return {
        "id": f"route-{index + 1}",
        "provider": "here",
        "transport_mode": "truck",
        "routing_mode": routing_mode,
        "distance_meters": distance_m,
        "duration_seconds": duration_s,
        "distance_miles": round(distance_m / 1609.344, 1),
        "duration_hours": round(duration_s / 3600, 2),
        "geometry": coords,
        "summary": f"Truck route {index + 1}",
    }


def _osrm_routes(
    origin: dict,
    destination: dict,
    alternatives: int,
) -> list[dict[str, Any]]:
    """
    Public OSRM driving routes as fallback.

    1) Native alternatives (often ≤2 for long US corridors)
    2) Additional real routes via corridor-offset via points until 3 distinct
    """
    collected: list[dict[str, Any]] = []

    native = _osrm_request(
        [origin, destination],
        alternatives=max(alternatives, TARGET_ROUTE_COUNT - 1),
    )
    for route in native:
        _merge_distinct_route(collected, route)

    if len(collected) < TARGET_ROUTE_COUNT:
        for via in _corridor_via_candidates(origin, destination):
            if len(collected) >= TARGET_ROUTE_COUNT:
                break
            via_routes = _osrm_request([origin, via, destination], alternatives=0)
            for route in via_routes:
                route["summary"] = (
                    f"Driving route via offset corridor "
                    f"({via['lat']:.2f},{via['lon']:.2f}) (OSRM fallback)"
                )
                if _merge_distinct_route(collected, route):
                    break

    if not collected:
        raise RuntimeError("No routes found between origin and destination.")

    for i, route in enumerate(collected[:TARGET_ROUTE_COUNT]):
        route["id"] = f"route-{i + 1}"
        if "warning" not in route:
            route["warning"] = (
                "HERE truck routing unavailable — using OSRM driving profile. "
                "OSRM routes are NOT truck-restricted. "
                "Set a valid HERE_API_KEY for truck-mode routes."
            )
        if i == 0 and "summary" not in route:
            route["summary"] = f"Driving route {i + 1} (OSRM fallback)"
        elif not route.get("summary", "").startswith("Driving"):
            route["summary"] = f"Driving route {i + 1} (OSRM fallback)"

    return collected[:TARGET_ROUTE_COUNT]


def _osrm_request(
    points: list[dict],
    alternatives: int,
) -> list[dict[str, Any]]:
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    url = f"{OSRM_URL}/{coords}"
    params = {
        "overview": "full",
        "geometries": "polyline",
        "alternatives": str(max(alternatives, 0)) if alternatives else "false",
        "steps": "false",
    }
    resp = requests.get(url, params=params, timeout=45)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != "Ok":
        logger.warning("OSRM non-Ok response: %s", data.get("code"))
        return []

    routes: list[dict[str, Any]] = []
    limit = alternatives + 1 if alternatives else 1
    for i, route in enumerate((data.get("routes") or [])[:limit]):
        geometry = decode_osrm_polyline(route["geometry"])
        distance_m = float(route.get("distance") or 0)
        duration_s = float(route.get("duration") or 0)
        routes.append(
            {
                "id": f"route-{i + 1}",
                "provider": "osrm",
                "transport_mode": "driving",
                "distance_meters": int(distance_m),
                "duration_seconds": int(duration_s),
                "distance_miles": round(distance_m / 1609.344, 1),
                "duration_hours": round(duration_s / 3600, 2),
                "geometry": geometry,
                "summary": f"Driving route {i + 1} (OSRM fallback)",
                "warning": (
                    "HERE truck routing unavailable — using OSRM driving profile. "
                    "OSRM routes are NOT truck-restricted. "
                    "Set a valid HERE_API_KEY for truck-mode routes."
                ),
            }
        )
    return routes


def _corridor_via_candidates(origin: dict, destination: dict) -> list[dict]:
    """
    Build real geographic via points offset from the OD corridor midpoint.

    Distances are large enough to force alternate corridors on long US hauls
    without inventing geometry — each via is still routed by OSRM.
    """
    mid_lat = (origin["lat"] + destination["lat"]) / 2.0
    mid_lon = (origin["lon"] + destination["lon"]) / 2.0
    dlat = destination["lat"] - origin["lat"]
    dlon = destination["lon"] - origin["lon"]
    length = math.hypot(dlat, dlon) or 1.0
    # Unit perpendicular in lat/lon space
    ulat, ulon = -dlon / length, dlat / length

    candidates: list[dict] = []
    for miles in (180, 280, 360):
        deg = miles / 69.0
        # Adjust lon for latitude
        lon_scale = max(math.cos(math.radians(mid_lat)), 0.2)
        for sign in (1, -1):
            candidates.append(
                {
                    "lat": mid_lat + sign * ulat * deg,
                    "lon": mid_lon + sign * ulon * (deg / lon_scale),
                }
            )
    return candidates


def _merge_distinct_route(
    collected: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> bool:
    """
    Append candidate if it is a genuinely different corridor.

    Primary signal: geometry overlap. Secondary: distance+duration only when
    geometries already look similar (avoids rejecting distinct long corridors
    that happen to have similar total miles).
    """
    if len(collected) >= TARGET_ROUTE_COUNT:
        return False
    for existing in collected:
        overlap = _geometry_overlap_ratio(
            existing["geometry"], candidate["geometry"]
        )
        if overlap >= GEOMETRY_OVERLAP_REJECT:
            return False
        dist_delta = abs(
            existing["distance_miles"] - candidate["distance_miles"]
        )
        dur_delta = abs(
            existing["duration_seconds"] - candidate["duration_seconds"]
        )
        if (
            overlap >= 0.55
            and dist_delta < MIN_ROUTE_DISTANCE_DELTA_MI
            and dur_delta < MIN_ROUTE_DURATION_DELTA_S
        ):
            return False
    collected.append(candidate)
    return True


def _geometry_overlap_ratio(
    a: list[list[float]],
    b: list[list[float]],
    samples: int = 12,
) -> float:
    """
    Rough similarity: fraction of sampled points on A that are within
    ~15 miles of some sampled point on B.
    """
    if not a or not b:
        return 0.0

    def sample(coords: list[list[float]]) -> list[list[float]]:
        if len(coords) <= samples:
            return coords
        step = (len(coords) - 1) / (samples - 1)
        return [coords[int(round(i * step))] for i in range(samples)]

    sa, sb = sample(a), sample(b)
    hits = 0
    for lon, lat in sa:
        if any(haversine_miles(lat, lon, p[1], p[0]) <= 15 for p in sb):
            hits += 1
    return hits / len(sa)
