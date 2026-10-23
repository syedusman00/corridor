"""Geocoding and geometry helpers."""

from __future__ import annotations

import math
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HERE_GEOCODE_URL = "https://geocode.search.hereapi.com/v1/geocode"
USER_AGENT = "SpotterWeatherTruckRouting/1.0 (assessment)"


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.7613  # Earth radius in miles
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def geocode(query: str, here_api_key: str = "") -> dict[str, Any]:
    """Resolve a place name or address to lat/lon. Prefers HERE when keyed."""
    query = (query or "").strip()
    if not query:
        raise ValueError("Location query is empty.")

    # Allow "lat,lon" passthrough
    if "," in query:
        parts = [p.strip() for p in query.split(",")]
        if len(parts) == 2:
            try:
                lat, lon = float(parts[0]), float(parts[1])
                if -90 <= lat <= 90 and -180 <= lon <= 180:
                    return {
                        "label": query,
                        "lat": lat,
                        "lon": lon,
                        "source": "coordinates",
                    }
            except ValueError:
                pass

    if here_api_key:
        try:
            return _geocode_here(query, here_api_key)
        except Exception:
            pass  # fall through to Nominatim

    return _geocode_nominatim(query)


def _geocode_here(query: str, api_key: str) -> dict[str, Any]:
    resp = requests.get(
        HERE_GEOCODE_URL,
        params={"q": query, "apiKey": api_key, "limit": 1},
        timeout=20,
    )
    resp.raise_for_status()
    items = resp.json().get("items") or []
    if not items:
        raise ValueError(f"Could not geocode: {query}")
    pos = items[0]["position"]
    return {
        "label": items[0].get("title") or query,
        "lat": pos["lat"],
        "lon": pos["lng"],
        "source": "here",
    }


def _geocode_nominatim(query: str) -> dict[str, Any]:
    resp = requests.get(
        NOMINATIM_URL,
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": USER_AGENT},
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError(f"Could not geocode: {query}")
    return {
        "label": data[0].get("display_name") or query,
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"]),
        "source": "nominatim",
    }


def sample_polyline(
    coordinates: list[list[float]],
    interval_miles: float,
) -> list[dict[str, Any]]:
    """
    Sample points along a [lon, lat] polyline every `interval_miles`.

    Returns checkpoints with cumulative distance and fraction along route.
    Always includes start and end.
    """
    if not coordinates:
        return []
    if len(coordinates) == 1:
        lon, lat = coordinates[0]
        return [
            {
                "index": 0,
                "lat": lat,
                "lon": lon,
                "distance_miles": 0.0,
                "fraction": 0.0,
            }
        ]

    # Build cumulative distances
    cum: list[float] = [0.0]
    for i in range(1, len(coordinates)):
        lon1, lat1 = coordinates[i - 1]
        lon2, lat2 = coordinates[i]
        cum.append(cum[-1] + haversine_miles(lat1, lon1, lat2, lon2))

    total = cum[-1]
    if total <= 0:
        lon, lat = coordinates[0]
        return [
            {
                "index": 0,
                "lat": lat,
                "lon": lon,
                "distance_miles": 0.0,
                "fraction": 0.0,
            }
        ]

    targets = [0.0]
    d = interval_miles
    while d < total:
        targets.append(d)
        d += interval_miles
    if targets[-1] < total - 0.01:
        targets.append(total)
    else:
        targets[-1] = total

    samples: list[dict[str, Any]] = []
    seg_idx = 0
    for ti, target in enumerate(targets):
        while seg_idx < len(cum) - 2 and cum[seg_idx + 1] < target:
            seg_idx += 1

        if abs(cum[seg_idx] - target) < 1e-9:
            lon, lat = coordinates[seg_idx]
        elif target >= cum[-1]:
            lon, lat = coordinates[-1]
        else:
            d0, d1 = cum[seg_idx], cum[seg_idx + 1]
            t = 0.0 if d1 == d0 else (target - d0) / (d1 - d0)
            lon0, lat0 = coordinates[seg_idx]
            lon1, lat1 = coordinates[seg_idx + 1]
            lon = lon0 + t * (lon1 - lon0)
            lat = lat0 + t * (lat1 - lat0)

        samples.append(
            {
                "index": ti,
                "lat": round(lat, 6),
                "lon": round(lon, 6),
                "distance_miles": round(target, 2),
                "fraction": round(target / total, 6),
            }
        )

    return samples


def simplify_polyline(
    coordinates: list[list[float]],
    max_points: int = 400,
) -> list[list[float]]:
    """
    Downsample a polyline for API payloads while keeping endpoints.
    Uses even index sampling (fast, good enough for map display).
    """
    if len(coordinates) <= max_points:
        return [
            [round(float(lon), 5), round(float(lat), 5)] for lon, lat in coordinates
        ]

    n = len(coordinates)
    idxs = [0]
    step = (n - 1) / (max_points - 1)
    for i in range(1, max_points - 1):
        idxs.append(int(round(i * step)))
    idxs.append(n - 1)
    # unique preserve order
    seen = set()
    out: list[list[float]] = []
    for i in idxs:
        if i in seen:
            continue
        seen.add(i)
        lon, lat = coordinates[i]
        out.append([round(float(lon), 5), round(float(lat), 5)])
    return out


def decode_osrm_polyline(encoded: str, precision: int = 5) -> list[list[float]]:
    """Decode Google/OSRM polyline to [lon, lat] pairs."""
    coordinates: list[list[float]] = []
    index, lat, lon = 0, 0, 0
    factor = 10**precision

    while index < len(encoded):
        for result_shift in (True, False):
            result, shift = 0, 0
            while True:
                b = ord(encoded[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            delta = ~(result >> 1) if result & 1 else (result >> 1)
            if result_shift:
                lat += delta
            else:
                lon += delta
                coordinates.append([lon / factor, lat / factor])

    return coordinates
