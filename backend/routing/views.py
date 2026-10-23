"""API views for weather-aware truck routing."""

from __future__ import annotations

import logging
import traceback

from django.conf import settings
from django.http import JsonResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .geo import geocode
from .serialize import compact_analyze_response
from .services import analyze_trip

logger = logging.getLogger(__name__)


@api_view(["GET"])
def health(request: Request) -> Response:
    here_key = bool(getattr(settings, "HERE_API_KEY", ""))
    return Response(
        {
            "status": "ok",
            "here_configured": here_key,
            # Preferred provider from env — actual per-request provider is in /analyze/
            "routing_provider": getattr(settings, "ROUTING_PROVIDER", "here"),
            "here_key_present": here_key,
            "note": (
                "If HERE_API_KEY is invalid, /analyze/ falls back to OSRM driving "
                "and sets routing_provider=osrm on the response."
            ),
        }
    )


@api_view(["GET"])
def geocode_view(request: Request) -> Response:
    q = request.query_params.get("q", "").strip()
    if not q:
        return Response({"detail": "Query parameter 'q' is required."}, status=400)
    try:
        result = geocode(q, getattr(settings, "HERE_API_KEY", "") or "")
        return Response(result)
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=404)
    except Exception as exc:
        logger.exception("Geocode failed")
        return Response({"detail": str(exc)}, status=502)


@api_view(["POST"])
def analyze(request: Request) -> Response:
    """
    Body:
      origin: str
      destination: str
      departure: ISO-8601 datetime
      load_lbs: number
      interval_miles: 10 | 25 | 50
    """
    data = request.data or {}
    origin = (data.get("origin") or "").strip()
    destination = (data.get("destination") or "").strip()
    departure = data.get("departure") or ""
    try:
        load_lbs = float(data.get("load_lbs", 0))
    except (TypeError, ValueError):
        return Response({"detail": "load_lbs must be a number."}, status=400)
    try:
        interval_miles = int(data.get("interval_miles", 25))
    except (TypeError, ValueError):
        return Response({"detail": "interval_miles must be 10, 25, or 50."}, status=400)

    if not origin or not destination:
        return Response(
            {"detail": "origin and destination are required."},
            status=400,
        )

    try:
        result = analyze_trip(
            origin_query=origin,
            destination_query=destination,
            departure_iso=str(departure),
            load_lbs=load_lbs,
            interval_miles=interval_miles,
        )
        return Response(compact_analyze_response(result))
    except ValueError as exc:
        return Response({"detail": str(exc)}, status=400)
    except Exception as exc:
        logger.error("Analyze failed: %s\n%s", exc, traceback.format_exc())
        return Response(
            {"detail": f"Unable to analyze trip: {exc}"},
            status=status.HTTP_502_BAD_GATEWAY,
        )


def root(_request):
    return JsonResponse(
        {
            "name": "Weather-Aware Truck Routing API",
            "endpoints": {
                "GET /api/health/": "Service health",
                "GET /api/geocode/?q=": "Geocode a place",
                "POST /api/analyze/": "Full route + weather + risk analysis",
            },
        }
    )
