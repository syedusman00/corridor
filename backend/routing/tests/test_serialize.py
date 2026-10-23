from django.test import SimpleTestCase

from routing.serialize import compact_analyze_response


class SerializeTests(SimpleTestCase):
    def test_geometry_downsampled_and_heatmap_compact(self):
        geometry = [[-87.0 + i * 0.01, 41.0] for i in range(2000)]
        result = {
            "origin": {"lat": 41.0, "lon": -87.0, "label": "A"},
            "destination": {"lat": 41.0, "lon": -67.0, "label": "B"},
            "departure": "2026-10-23T01:00:00+00:00",
            "load_lbs": 35000,
            "interval_miles": 25,
            "recommendation": None,
            "routing_provider": "osrm",
            "routes": [
                {
                    "id": "route-1",
                    "provider": "osrm",
                    "distance_miles": 1000,
                    "duration_seconds": 36000,
                    "geometry": geometry,
                    "checkpoints": [
                        {
                            "index": 0,
                            "lat": 41.123456,
                            "lon": -87.123456,
                            "distance_miles": 0,
                            "fraction": 0,
                            "eta": "2026-10-23T01:00:00+00:00",
                            "weather": {
                                "time": "x",
                                "wind_mph": 5,
                                "rain_in_hr": 0,
                                "snow_in_hr": 0,
                                "temperature_c": 10,
                                "weather_valid": True,
                            },
                            "overall_risk": "Low",
                            "wind_risk": "Low",
                            "rain_risk": "Low",
                            "snow_risk": "Low",
                            "risk_score": 0,
                            "weather_valid": True,
                        }
                    ],
                }
            ],
            "heatmap": {
                "points": [{"lat": 41.0, "lon": -87.0, "index": 0}],
                "hours": [0, 1],
                "base_time": "2026-10-23T01:00:00+00:00",
                "grid": [
                    [
                        {
                            "hour_offset": 0,
                            "overall_risk": "Low",
                            "risk_score": 0,
                            "wind_mph": 5,
                            "rain_in_hr": 0,
                            "snow_in_hr": 0,
                            "weather_valid": True,
                        },
                        {
                            "hour_offset": 1,
                            "overall_risk": "Moderate",
                            "risk_score": 1,
                            "wind_mph": 30,
                            "rain_in_hr": 0,
                            "snow_in_hr": 0,
                            "weather_valid": True,
                        },
                    ]
                ],
            },
        }
        compact = compact_analyze_response(result, max_geometry_points=400)
        self.assertLessEqual(len(compact["routes"][0]["geometry"]), 400)
        self.assertEqual(compact["heatmap"]["format"], "compact_v1")
        self.assertEqual(compact["heatmap"]["risk"][0][1], "Moderate")
        self.assertNotIn("grid", compact["heatmap"])
