from django.test import SimpleTestCase

from routing.geo import haversine_miles, sample_polyline


class GeoTests(SimpleTestCase):
    def test_haversine_known_distance(self):
        # Chicago to roughly 1 degree east — should be ~50+ miles
        d = haversine_miles(41.88, -87.63, 41.88, -86.63)
        self.assertGreater(d, 45)
        self.assertLess(d, 60)

    def test_sample_includes_endpoints(self):
        # Rough line ~100 miles east
        coords = [[-87.63, 41.88], [-86.63, 41.88], [-85.63, 41.88]]
        samples = sample_polyline(coords, 50)
        self.assertEqual(samples[0]["distance_miles"], 0.0)
        self.assertAlmostEqual(
            samples[-1]["distance_miles"],
            haversine_miles(41.88, -87.63, 41.88, -85.63),
            delta=1.0,
        )
        self.assertGreaterEqual(len(samples), 3)
