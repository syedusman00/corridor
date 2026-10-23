"""
Weather and load-based risk classification.

Thresholds from Spotter AI Full Stack assessment:

Wind (mph):   <25 Low | 25–34 Moderate | 35–44 High | 45–54 Severe | ≥55 No Travel
Rain (in/hr): <0.10 Low | 0.10–0.25 Moderate | 0.25–0.50 High | 0.50–1.00 Severe | >1.00 No Travel
Snow (in/hr): <0.5 Low | 0.5–1.0 Moderate | 1.0–2.0 High | 2.0–3.0 Severe | >3.0 No Travel

Load rules:
  • ≥55 mph → No Travel for any load
  • 45–54 mph + >30,000 lb → No Travel
  • 35–44 mph + >40,000 lb → Severe

Unknown: used when weather is missing, failed, or out of forecast range.
Unknown is never treated as Low and blocks safe recommendation.
"""

from __future__ import annotations

from typing import Literal

RiskLevel = Literal["Low", "Moderate", "High", "Severe", "No Travel", "Unknown"]

# Numeric ranks for mile-weighted averages (Unknown excluded from averages)
RISK_RANK: dict[RiskLevel, int] = {
    "Low": 0,
    "Moderate": 1,
    "High": 2,
    "Severe": 3,
    "No Travel": 4,
    "Unknown": -1,
}

RANK_TO_RISK: dict[int, RiskLevel] = {
    0: "Low",
    1: "Moderate",
    2: "High",
    3: "Severe",
    4: "No Travel",
}

COMPARABLE_RANKS = {k: v for k, v in RISK_RANK.items() if k != "Unknown"}


def wind_risk(wind_mph: float) -> RiskLevel:
    if wind_mph >= 55:
        return "No Travel"
    if wind_mph >= 45:
        return "Severe"
    if wind_mph >= 35:
        return "High"
    if wind_mph >= 25:
        return "Moderate"
    return "Low"


def rain_risk(rain_in_hr: float) -> RiskLevel:
    if rain_in_hr > 1.00:
        return "No Travel"
    if rain_in_hr >= 0.50:
        return "Severe"
    if rain_in_hr >= 0.25:
        return "High"
    if rain_in_hr >= 0.10:
        return "Moderate"
    return "Low"


def snow_risk(snow_in_hr: float) -> RiskLevel:
    if snow_in_hr > 3.0:
        return "No Travel"
    if snow_in_hr >= 2.0:
        return "Severe"
    if snow_in_hr >= 1.0:
        return "High"
    if snow_in_hr >= 0.5:
        return "Moderate"
    return "Low"


def apply_load_rules(wind_mph: float, load_lbs: float, base_wind: RiskLevel) -> RiskLevel:
    """Elevate wind risk based on load weight rules from the assessment."""
    if base_wind == "Unknown":
        return "Unknown"
    if wind_mph >= 55:
        return "No Travel"
    if 45 <= wind_mph < 55 and load_lbs > 30_000:
        return "No Travel"
    if 35 <= wind_mph < 45 and load_lbs > 40_000:
        return "Severe"
    return base_wind


def max_risk(*levels: RiskLevel) -> RiskLevel:
    """Highest comparable risk; Unknown wins if any input is Unknown."""
    if any(level == "Unknown" for level in levels):
        return "Unknown"
    return RANK_TO_RISK[max(COMPARABLE_RANKS[level] for level in levels)]


def unknown_classification(reason: str = "Weather unavailable") -> dict:
    return {
        "wind_risk": "Unknown",
        "rain_risk": "Unknown",
        "snow_risk": "Unknown",
        "overall_risk": "Unknown",
        "risk_score": RISK_RANK["Unknown"],
        "weather_valid": False,
        "weather_error": reason,
    }


def classify_checkpoint(
    wind_mph: float | None,
    rain_in_hr: float | None,
    snow_in_hr: float | None,
    load_lbs: float,
    *,
    weather_valid: bool = True,
    weather_error: str | None = None,
) -> dict:
    """Classify a checkpoint. Invalid weather → Unknown (never Low)."""
    if (
        not weather_valid
        or wind_mph is None
        or rain_in_hr is None
        or snow_in_hr is None
    ):
        return unknown_classification(weather_error or "Weather unavailable")

    base_wind = wind_risk(float(wind_mph))
    adjusted_wind = apply_load_rules(float(wind_mph), load_lbs, base_wind)
    rain = rain_risk(float(rain_in_hr))
    snow = snow_risk(float(snow_in_hr))
    overall = max_risk(adjusted_wind, rain, snow)

    return {
        "wind_risk": adjusted_wind,
        "rain_risk": rain,
        "snow_risk": snow,
        "overall_risk": overall,
        "risk_score": RISK_RANK[overall],
        "weather_valid": True,
        "weather_error": None,
    }


def recommend_route(routes: list[dict]) -> dict | None:
    """
    Prefer:
      1. Fewest Severe miles
      2. Fewest High miles
      3. Lowest average risk
      4. Shortest travel time

    Never recommend a route with No Travel or incomplete (Unknown) weather.
    """
    eligible = [
        r
        for r in routes
        if not r.get("has_no_travel") and not r.get("weather_incomplete")
    ]
    if not eligible:
        return None

    def sort_key(route: dict) -> tuple:
        return (
            route.get("severe_miles", 0),
            route.get("high_miles", 0),
            route.get("average_risk", 0),
            route.get("duration_seconds", 0),
        )

    best = min(eligible, key=sort_key)
    return {"route_id": best["id"], "reason": _recommendation_reason(best, eligible)}


def _recommendation_reason(best: dict, pool: list[dict]) -> str:
    others = [r for r in pool if r["id"] != best["id"]]
    if not others:
        return "Only eligible route without No Travel or incomplete weather."

    runner = min(
        others,
        key=lambda r: (
            r.get("severe_miles", 0),
            r.get("high_miles", 0),
            r.get("average_risk", 0),
            r.get("duration_seconds", 0),
        ),
    )

    if best.get("severe_miles", 0) < runner.get("severe_miles", 0):
        return (
            f"Fewest Severe miles ({best['severe_miles']:.0f} vs "
            f"{runner['severe_miles']:.0f} on next-best)."
        )
    if best.get("high_miles", 0) < runner.get("high_miles", 0):
        return (
            f"Tied on Severe miles; fewest High miles "
            f"({best['high_miles']:.0f} vs {runner['high_miles']:.0f})."
        )
    if best.get("average_risk", 0) < runner.get("average_risk", 0):
        return (
            f"Tied on Severe/High miles; lowest average risk "
            f"({best['average_risk']:.2f} vs {runner['average_risk']:.2f})."
        )
    return (
        f"Tied on risk metrics; shortest travel time "
        f"({best['duration_seconds'] / 3600:.1f}h vs "
        f"{runner['duration_seconds'] / 3600:.1f}h)."
    )


def aggregate_route_risk(checkpoints: list[dict], interval_miles: float) -> dict:
    """
    Mile-weighted risk summaries.

    No Travel / Unknown at the origin and every checkpoint are considered.
    Unknown miles are tracked separately and do not count as Low.
    """
    empty = {
        "has_no_travel": False,
        "weather_incomplete": False,
        "severe_miles": 0.0,
        "high_miles": 0.0,
        "moderate_miles": 0.0,
        "low_miles": 0.0,
        "no_travel_miles": 0.0,
        "unknown_miles": 0.0,
        "average_risk": 0.0,
        "max_risk": "Low",
    }
    if not checkpoints:
        return empty

    miles_by_risk: dict[str, float] = {
        "Low": 0.0,
        "Moderate": 0.0,
        "High": 0.0,
        "Severe": 0.0,
        "No Travel": 0.0,
        "Unknown": 0.0,
    }
    score_sum = 0.0
    weight_sum = 0.0
    max_level: RiskLevel = "Low"
    has_no_travel = False
    weather_incomplete = False

    for i, cp in enumerate(checkpoints):
        risk: RiskLevel = cp.get("overall_risk") or "Unknown"
        if risk == "No Travel":
            has_no_travel = True
        if risk == "Unknown" or cp.get("weather_valid") is False:
            weather_incomplete = True

        if i == 0:
            # Origin has no preceding segment; still flag conditions.
            # Attribute a nominal stub so origin No Travel/Unknown appear in miles.
            if risk in ("No Travel", "Unknown"):
                stub = min(float(interval_miles) * 0.1, 1.0)
                miles_by_risk[risk] += stub
            continue

        prev = checkpoints[i - 1]
        seg_miles = max(
            0.0,
            float(cp.get("distance_miles", 0)) - float(prev.get("distance_miles", 0)),
        )
        if seg_miles <= 0:
            seg_miles = float(interval_miles)

        miles_by_risk[risk] = miles_by_risk.get(risk, 0.0) + seg_miles

        if risk != "Unknown":
            score_sum += COMPARABLE_RANKS[risk] * seg_miles
            weight_sum += seg_miles
            if COMPARABLE_RANKS[risk] > COMPARABLE_RANKS.get(max_level, -1):
                max_level = risk
        else:
            # Incomplete data cannot claim a comparable max below Unknown
            if max_level != "No Travel":
                max_level = "Unknown"

    # Origin-only No Travel / Unknown already set flags above
    if any(cp.get("overall_risk") == "No Travel" for cp in checkpoints):
        has_no_travel = True
    if any(
        cp.get("overall_risk") == "Unknown" or cp.get("weather_valid") is False
        for cp in checkpoints
    ):
        weather_incomplete = True

    avg = (score_sum / weight_sum) if weight_sum else 0.0

    return {
        "has_no_travel": has_no_travel,
        "weather_incomplete": weather_incomplete,
        "severe_miles": round(miles_by_risk["Severe"], 1),
        "high_miles": round(miles_by_risk["High"], 1),
        "moderate_miles": round(miles_by_risk["Moderate"], 1),
        "low_miles": round(miles_by_risk["Low"], 1),
        "no_travel_miles": round(miles_by_risk["No Travel"], 1),
        "unknown_miles": round(miles_by_risk["Unknown"], 1),
        "average_risk": round(avg, 3),
        "max_risk": max_level,
    }
