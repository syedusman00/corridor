"""Unit tests for risk thresholds, Unknown weather, and recommendation logic."""

from django.test import SimpleTestCase

from routing.risk import (
    aggregate_route_risk,
    apply_load_rules,
    classify_checkpoint,
    rain_risk,
    recommend_route,
    snow_risk,
    unknown_classification,
    wind_risk,
)


class WindRiskTests(SimpleTestCase):
    def test_thresholds(self):
        self.assertEqual(wind_risk(24.9), "Low")
        self.assertEqual(wind_risk(25), "Moderate")
        self.assertEqual(wind_risk(34), "Moderate")
        self.assertEqual(wind_risk(35), "High")
        self.assertEqual(wind_risk(44), "High")
        self.assertEqual(wind_risk(45), "Severe")
        self.assertEqual(wind_risk(54), "Severe")
        self.assertEqual(wind_risk(55), "No Travel")
        self.assertEqual(wind_risk(80), "No Travel")


class RainRiskTests(SimpleTestCase):
    def test_thresholds(self):
        self.assertEqual(rain_risk(0.09), "Low")
        self.assertEqual(rain_risk(0.10), "Moderate")
        self.assertEqual(rain_risk(0.25), "High")
        self.assertEqual(rain_risk(0.50), "Severe")
        self.assertEqual(rain_risk(1.00), "Severe")
        self.assertEqual(rain_risk(1.01), "No Travel")


class SnowRiskTests(SimpleTestCase):
    def test_thresholds(self):
        self.assertEqual(snow_risk(0.49), "Low")
        self.assertEqual(snow_risk(0.5), "Moderate")
        self.assertEqual(snow_risk(1.0), "High")
        self.assertEqual(snow_risk(2.0), "Severe")
        self.assertEqual(snow_risk(3.0), "Severe")
        self.assertEqual(snow_risk(3.1), "No Travel")


class LoadRuleTests(SimpleTestCase):
    def test_55_mph_any_load(self):
        self.assertEqual(apply_load_rules(55, 0, "No Travel"), "No Travel")
        self.assertEqual(apply_load_rules(60, 10000, "No Travel"), "No Travel")

    def test_45_54_heavy_load(self):
        self.assertEqual(apply_load_rules(50, 30001, "Severe"), "No Travel")
        self.assertEqual(apply_load_rules(50, 30000, "Severe"), "Severe")

    def test_35_44_very_heavy(self):
        self.assertEqual(apply_load_rules(40, 40001, "High"), "Severe")
        self.assertEqual(apply_load_rules(40, 40000, "High"), "High")


class ClassifyTests(SimpleTestCase):
    def test_overall_takes_max(self):
        result = classify_checkpoint(
            wind_mph=20, rain_in_hr=0.6, snow_in_hr=0, load_lbs=10000
        )
        self.assertEqual(result["overall_risk"], "Severe")
        self.assertTrue(result["weather_valid"])

    def test_load_elevates_to_no_travel(self):
        result = classify_checkpoint(
            wind_mph=50, rain_in_hr=0, snow_in_hr=0, load_lbs=35000
        )
        self.assertEqual(result["overall_risk"], "No Travel")

    def test_invalid_weather_is_unknown_not_low(self):
        result = classify_checkpoint(
            None, None, None, 10000, weather_valid=False, weather_error="API down"
        )
        self.assertEqual(result["overall_risk"], "Unknown")
        self.assertFalse(result["weather_valid"])
        self.assertNotEqual(result["overall_risk"], "Low")

    def test_unknown_helper(self):
        u = unknown_classification("timeout")
        self.assertEqual(u["overall_risk"], "Unknown")
        self.assertEqual(u["wind_risk"], "Unknown")


class RecommendTests(SimpleTestCase):
    def _route(self, rid, severe, high, avg, duration, no_travel=False, incomplete=False):
        return {
            "id": rid,
            "severe_miles": severe,
            "high_miles": high,
            "average_risk": avg,
            "duration_seconds": duration,
            "has_no_travel": no_travel,
            "weather_incomplete": incomplete,
        }

    def test_excludes_no_travel(self):
        routes = [
            self._route("a", 0, 0, 0.1, 1000, no_travel=True),
            self._route("b", 5, 10, 1.5, 2000),
        ]
        rec = recommend_route(routes)
        self.assertEqual(rec["route_id"], "b")

    def test_excludes_incomplete_weather(self):
        routes = [
            self._route("a", 0, 0, 0.0, 1000, incomplete=True),
            self._route("b", 5, 10, 1.5, 2000),
        ]
        self.assertEqual(recommend_route(routes)["route_id"], "b")

    def test_all_incomplete_returns_none(self):
        routes = [self._route("a", 0, 0, 0, 1000, incomplete=True)]
        self.assertIsNone(recommend_route(routes))

    def test_prefers_fewest_severe(self):
        routes = [
            self._route("a", 20, 0, 0.5, 1000),
            self._route("b", 5, 50, 2.0, 5000),
        ]
        self.assertEqual(recommend_route(routes)["route_id"], "b")

    def test_then_fewest_high(self):
        routes = [
            self._route("a", 5, 40, 1.0, 1000),
            self._route("b", 5, 10, 2.0, 5000),
        ]
        self.assertEqual(recommend_route(routes)["route_id"], "b")

    def test_then_average_then_time(self):
        routes = [
            self._route("a", 5, 10, 1.5, 5000),
            self._route("b", 5, 10, 1.0, 8000),
        ]
        self.assertEqual(recommend_route(routes)["route_id"], "b")

        routes2 = [
            self._route("a", 5, 10, 1.0, 5000),
            self._route("b", 5, 10, 1.0, 8000),
        ]
        self.assertEqual(recommend_route(routes2)["route_id"], "a")

    def test_all_no_travel_returns_none(self):
        routes = [self._route("a", 0, 0, 0, 1000, no_travel=True)]
        self.assertIsNone(recommend_route(routes))


class AggregateTests(SimpleTestCase):
    def test_segment_miles(self):
        checkpoints = [
            {"distance_miles": 0, "overall_risk": "Low", "weather_valid": True},
            {"distance_miles": 25, "overall_risk": "High", "weather_valid": True},
            {"distance_miles": 50, "overall_risk": "Severe", "weather_valid": True},
        ]
        agg = aggregate_route_risk(checkpoints, 25)
        self.assertEqual(agg["high_miles"], 25.0)
        self.assertEqual(agg["severe_miles"], 25.0)
        self.assertFalse(agg["has_no_travel"])

    def test_origin_no_travel_is_flagged(self):
        checkpoints = [
            {"distance_miles": 0, "overall_risk": "No Travel", "weather_valid": True},
            {"distance_miles": 25, "overall_risk": "Low", "weather_valid": True},
        ]
        agg = aggregate_route_risk(checkpoints, 25)
        self.assertTrue(agg["has_no_travel"])
        self.assertGreater(agg["no_travel_miles"], 0)

    def test_unknown_not_counted_as_low(self):
        checkpoints = [
            {"distance_miles": 0, "overall_risk": "Low", "weather_valid": True},
            {
                "distance_miles": 25,
                "overall_risk": "Unknown",
                "weather_valid": False,
            },
        ]
        agg = aggregate_route_risk(checkpoints, 25)
        self.assertTrue(agg["weather_incomplete"])
        self.assertEqual(agg["low_miles"], 0.0)
        self.assertEqual(agg["unknown_miles"], 25.0)
        self.assertNotEqual(agg["max_risk"], "Low")
