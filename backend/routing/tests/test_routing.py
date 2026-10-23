"""Routing helpers: truck weight and route deduplication."""

from django.test import SimpleTestCase

from routing.here_routing import (
    GEOMETRY_OVERLAP_REJECT,
    TRACTOR_TRAILER_TARE_LBS,
    _geometry_overlap_ratio,
    _merge_distinct_route,
    truck_gross_weight_kg,
)


class TruckWeightTests(SimpleTestCase):
    def test_tare_plus_cargo(self):
        # 35000 lb cargo + 32000 tare = 67000 lb ≈ 30390 kg
        kg = truck_gross_weight_kg(35000)
        expected = int(round((TRACTOR_TRAILER_TARE_LBS + 35000) / 2.20462))
        self.assertEqual(kg, expected)

    def test_zero_load_uses_tare_only(self):
        kg = truck_gross_weight_kg(0)
        expected = int(round(TRACTOR_TRAILER_TARE_LBS / 2.20462))
        self.assertEqual(kg, expected)

    def test_none_load_uses_tare(self):
        self.assertEqual(truck_gross_weight_kg(None), truck_gross_weight_kg(0))

    def test_not_treating_cargo_as_gvw_alone(self):
        # Old bug: cargo_lbs/2.2 + 9000 — ensure we are heavier than that for 35k
        kg = truck_gross_weight_kg(35000)
        wrong_old = int(min(max((35000 / 2.20462) + 9000, 12000), 40000))
        self.assertNotEqual(kg, wrong_old)
        self.assertGreater(kg, wrong_old)


class DedupeTests(SimpleTestCase):
    def _route(self, miles, duration, geometry):
        return {
            "id": "tmp",
            "distance_miles": miles,
            "duration_seconds": duration,
            "geometry": geometry,
        }

    def test_identical_geometry_rejected(self):
        line = [[-87.0, 41.0], [-90.0, 40.0], [-100.0, 39.0]]
        collected = [self._route(1000, 60000, line)]
        added = _merge_distinct_route(
            collected, self._route(1005, 61000, list(line))
        )
        self.assertFalse(added)
        self.assertEqual(len(collected), 1)

    def test_distinct_corridor_accepted(self):
        north = [[-87.0, 42.0], [-95.0, 43.0], [-104.0, 40.0]]
        south = [[-87.0, 40.0], [-95.0, 36.0], [-104.0, 39.0]]
        collected = [self._route(1000, 60000, north)]
        added = _merge_distinct_route(
            collected, self._route(1200, 80000, south)
        )
        self.assertTrue(added)
        self.assertEqual(len(collected), 2)

    def test_overlap_ratio_high_for_same_path(self):
        line = [[i * 0.5, 40.0] for i in range(20)]
        ratio = _geometry_overlap_ratio(line, line)
        self.assertGreaterEqual(ratio, GEOMETRY_OVERLAP_REJECT)
