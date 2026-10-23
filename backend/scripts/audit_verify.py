"""
Live audit verification against assessment requirements.
Does not fabricate data — calls the running API / Open-Meteo / risk engine.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import django
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from routing.risk import (  # noqa: E402
    classify_checkpoint,
    rain_risk,
    recommend_route,
    snow_risk,
    wind_risk,
)
from routing.services import analyze_trip  # noqa: E402

PASS = []
FAIL = []
NOTES = []


def check(name: str, ok: bool, detail: str = ""):
    (PASS if ok else FAIL).append(f"{name}: {detail}" if detail else name)
    print(("PASS" if ok else "FAIL"), "-", name, detail)


def main():
    # --- Threshold unit checks (deterministic) ---
    check("Wind <25 Low", wind_risk(24.9) == "Low")
    check("Wind 25 Moderate", wind_risk(25) == "Moderate")
    check("Wind 35 High", wind_risk(35) == "High")
    check("Wind 45 Severe", wind_risk(45) == "Severe")
    check("Wind 55 No Travel", wind_risk(55) == "No Travel")
    check("Rain 0.10 Moderate", rain_risk(0.10) == "Moderate")
    check("Rain 0.25 High", rain_risk(0.25) == "High")
    check("Rain 0.50 Severe", rain_risk(0.50) == "Severe")
    check("Rain >1 No Travel", rain_risk(1.01) == "No Travel")
    check("Snow 0.5 Moderate", snow_risk(0.5) == "Moderate")
    check("Snow 1.0 High", snow_risk(1.0) == "High")
    check("Snow 2.0 Severe", snow_risk(2.0) == "Severe")
    check("Snow >3 No Travel", snow_risk(3.1) == "No Travel")

    # Load rules
    c1 = classify_checkpoint(50, 0, 0, 30001)
    check("Load 45-54mph + >30k => No Travel", c1["overall_risk"] == "No Travel")
    c2 = classify_checkpoint(40, 0, 0, 40001)
    check("Load 35-44mph + >40k => Severe", c2["overall_risk"] == "Severe")
    c3 = classify_checkpoint(55, 0, 0, 0)
    check("Wind >=55 any load => No Travel", c3["overall_risk"] == "No Travel")

    # Recommendation order
    routes = [
        {
            "id": "a",
            "severe_miles": 10,
            "high_miles": 0,
            "average_risk": 0.1,
            "duration_seconds": 100,
            "has_no_travel": False,
        },
        {
            "id": "b",
            "severe_miles": 0,
            "high_miles": 50,
            "average_risk": 2.0,
            "duration_seconds": 9999,
            "has_no_travel": False,
        },
        {
            "id": "c",
            "severe_miles": 0,
            "high_miles": 0,
            "average_risk": 0,
            "duration_seconds": 50,
            "has_no_travel": True,
        },
    ]
    rec = recommend_route(routes)
    check("Recommend fewest Severe (not No Travel)", rec and rec["route_id"] == "b")

    # --- Live Chicago → Denver ---
    departure = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    print("\nRunning live analyze Chicago → Denver (interval 50 mi, load 35000)...")
    result = analyze_trip(
        "Chicago, IL",
        "Denver, CO",
        departure,
        load_lbs=35000,
        interval_miles=50,
    )

    n_routes = len(result["routes"])
    check(
        "Up to 3 route options returned",
        1 <= n_routes <= 3,
        f"got {n_routes} via {result.get('routing_provider')}",
    )
    check(
        "Assessment asks for 3 options — got 3",
        n_routes == 3,
        f"got {n_routes} (provider={result.get('routing_provider')})",
    )

    for route in result["routes"]:
        cps = route["checkpoints"]
        check(
            f"{route['id']} has checkpoints",
            len(cps) >= 2,
            f"count={len(cps)} interval≈50",
        )
        # ETA monotonic
        etas = [datetime.fromisoformat(c["eta"]) for c in cps]
        mono = all(etas[i] <= etas[i + 1] for i in range(len(etas) - 1))
        check(f"{route['id']} ETAs monotonic with distance", mono)
        # ETA ≈ departure + fraction * duration
        dep = datetime.fromisoformat(result["departure"])
        last = cps[-1]
        expected = dep + timedelta(seconds=route["duration_seconds"])
        delta = abs((datetime.fromisoformat(last["eta"]) - expected).total_seconds())
        check(
            f"{route['id']} final ETA matches duration",
            delta < 120,
            f"delta_s={delta:.0f}",
        )
        # Weather fields present from Open-Meteo
        wx = cps[len(cps) // 2]["weather"]
        check(
            f"{route['id']} midpoint weather has wind/rain/snow",
            "wind_mph" in wx and "rain_in_hr" in wx and "snow_in_hr" in wx,
            f"wind={wx['wind_mph']} rain={wx['rain_in_hr']} snow={wx['snow_in_hr']}",
        )
        # Risk classification applied
        mid = cps[len(cps) // 2]
        recomputed = classify_checkpoint(
            mid["weather"]["wind_mph"],
            mid["weather"]["rain_in_hr"],
            mid["weather"]["snow_in_hr"],
            35000,
        )
        check(
            f"{route['id']} risk matches engine",
            mid["overall_risk"] == recomputed["overall_risk"],
            f"{mid['overall_risk']}",
        )

    # Heatmap 0–48
    heat = result["heatmap"]
    check("Heatmap has points", len(heat.get("points") or []) > 0, str(len(heat.get("points") or [])))
    check("Heatmap hours include 0..48", heat.get("hours") == list(range(49)))
    if heat.get("grid"):
        row = heat["grid"][0]
        check("Heatmap grid depth 49 hours", len(row) == 49, str(len(row)))
        check("Heatmap cells have risk_score", "risk_score" in row[0] and "overall_risk" in row[0])

    if result.get("recommendation"):
        rid = result["recommendation"]["route_id"]
        chosen = next(r for r in result["routes"] if r["id"] == rid)
        check(
            "Recommended route has no No Travel",
            not chosen["has_no_travel"],
            rid,
        )
    else:
        NOTES.append("No recommendation — all routes have No Travel (valid if weather warrants)")

    # Persist sample evidence
    evidence = {
        "routing_provider": result.get("routing_provider"),
        "route_count": n_routes,
        "routes": [
            {
                "id": r["id"],
                "distance_miles": r["distance_miles"],
                "duration_hours": r["duration_hours"],
                "severe_miles": r["severe_miles"],
                "high_miles": r["high_miles"],
                "average_risk": r["average_risk"],
                "has_no_travel": r["has_no_travel"],
                "checkpoints": r["checkpoint_count"],
                "sample_checkpoint": r["checkpoints"][min(1, len(r["checkpoints"]) - 1)],
            }
            for r in result["routes"]
        ],
        "recommendation": result.get("recommendation"),
        "heatmap_points": len(heat.get("points") or []),
        "heatmap_hours": len(heat.get("hours") or []),
    }
    out = ROOT / "scripts" / "audit_evidence.json"
    out.write_text(json.dumps(evidence, indent=2, default=str), encoding="utf-8")
    print(f"\nEvidence written to {out}")
    print(f"\nSUMMARY: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILURES:")
        for f in FAIL:
            print(" -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
