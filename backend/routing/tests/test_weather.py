"""Weather validity: missing/out-of-range forecasts must not become Low."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import SimpleTestCase

from routing.risk import classify_checkpoint
from routing.weather import (
    MAX_FORECAST_SKEW_SECONDS,
    build_corridor_heatmap,
    weather_at_time,
)


def _forecast_hours(start: datetime, values: dict, count: int = 48):
    times = []
    series = {k: [] for k in values}
    for i in range(count):
        t = start + timedelta(hours=i)
        times.append(t.strftime("%Y-%m-%dT%H:00"))
        for k, v in values.items():
            series[k].append(v)
    return {"hourly": {"time": times, **series}}


class WeatherAtTimeTests(SimpleTestCase):
    def test_empty_forecast_invalid(self):
        when = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
        wx = weather_at_time({"hourly": {"time": []}}, when)
        self.assertFalse(wx["weather_valid"])
        self.assertIsNone(wx["wind_mph"])

        classified = classify_checkpoint(
            wx["wind_mph"],
            wx["rain_in_hr"],
            wx["snow_in_hr"],
            10000,
            weather_valid=False,
            weather_error=wx["weather_error"],
        )
        self.assertEqual(classified["overall_risk"], "Unknown")

    def test_out_of_range_eta_invalid(self):
        start = datetime(2026, 10, 22, 0, tzinfo=timezone.utc)
        forecast = _forecast_hours(
            start,
            {
                "wind_speed_10m": 10.0,
                "rain": 0.0,
                "showers": 0.0,
                "precipitation": 0.0,
                "snowfall": 0.0,
                "temperature_2m": 15.0,
                "weather_code": 0,
            },
            count=12,
        )
        # Request time far beyond forecast window (12h of data, ask +22h)
        when = start + timedelta(hours=22)
        wx = weather_at_time(forecast, when)
        self.assertFalse(wx["weather_valid"])
        self.assertIn("outside forecast range", wx["weather_error"] or "")
        self.assertIsNone(wx["wind_mph"])
        self.assertGreater(22 - 11, MAX_FORECAST_SKEW_SECONDS / 3600)

    def test_valid_hour_returns_measurements(self):
        start = datetime(2026, 10, 22, 0, tzinfo=timezone.utc)
        forecast = _forecast_hours(
            start,
            {
                "wind_speed_10m": 32.0,
                "rain": 0.2,
                "showers": 0.0,
                "precipitation": 0.2,
                "snowfall": 0.0,
                "temperature_2m": 12.0,
                "weather_code": 61,
            },
            count=24,
        )
        when = start + timedelta(hours=5)
        wx = weather_at_time(forecast, when)
        self.assertTrue(wx["weather_valid"])
        self.assertEqual(wx["wind_mph"], 32.0)
        self.assertAlmostEqual(wx["rain_in_hr"], 0.2)
        classified = classify_checkpoint(
            wx["wind_mph"], wx["rain_in_hr"], wx["snow_in_hr"], 10000
        )
        self.assertEqual(classified["wind_risk"], "Moderate")
        self.assertEqual(classified["rain_risk"], "Moderate")
        self.assertEqual(classified["overall_risk"], "Moderate")

    def test_missing_wind_invalid(self):
        start = datetime(2026, 10, 22, 0, tzinfo=timezone.utc)
        forecast = {
            "hourly": {
                "time": [start.strftime("%Y-%m-%dT%H:00")],
                "wind_speed_10m": [None],
                "rain": [0.0],
                "showers": [0.0],
                "precipitation": [0.0],
                "snowfall": [0.0],
                "temperature_2m": [10.0],
                "weather_code": [0],
            }
        }
        wx = weather_at_time(forecast, start)
        self.assertFalse(wx["weather_valid"])


class ExternalApiFailureTests(SimpleTestCase):
    @patch("routing.weather.requests.get")
    def test_fetch_hourly_raises_on_http_error(self, mock_get):
        mock_get.return_value.status_code = 500
        mock_get.return_value.raise_for_status.side_effect = Exception("500 Server Error")
        from routing.weather import fetch_hourly_forecast

        with self.assertRaises(Exception):
            fetch_hourly_forecast(41.8, -87.6)

    @patch("routing.weather.fetch_batch_forecasts")
    def test_failed_batch_surfaces_as_unknown_in_heatmap(self, mock_fetch):
        mock_fetch.return_value = [{"hourly": {"time": []}}]
        departure = datetime(2026, 10, 22, 12, tzinfo=timezone.utc)
        heat = build_corridor_heatmap(
            [[-87.6, 41.8], [-86.6, 41.8]],
            sample_count=2,
            hours=3,
            load_lbs=0,
            departure=departure,
        )
        cell = heat["grid"][0][0]
        self.assertEqual(cell["overall_risk"], "Unknown")
        self.assertFalse(cell["weather_valid"])


class HeatmapDepartureTests(SimpleTestCase):
    @patch("routing.weather.fetch_batch_forecasts")
    def test_heatmap_base_is_departure_not_now(self, mock_fetch):
        start = datetime(2026, 11, 1, 15, 30, tzinfo=timezone.utc)
        mock_fetch.return_value = [
            _forecast_hours(
                start.replace(minute=0),
                {
                    "wind_speed_10m": 5.0,
                    "rain": 0.0,
                    "showers": 0.0,
                    "precipitation": 0.0,
                    "snowfall": 0.0,
                    "temperature_2m": 10.0,
                    "weather_code": 0,
                },
                count=60,
            )
        ]
        # Short eastbound line ~1 degree lon
        geometry = [[-87.6, 41.8], [-86.6, 41.8]]
        heat = build_corridor_heatmap(
            geometry,
            sample_count=2,
            hours=49,
            load_lbs=35000,
            departure=start,
        )
        self.assertEqual(heat["base_time"], "2026-11-01T15:00:00+00:00")
        self.assertEqual(heat["hours"], list(range(49)))
        self.assertTrue(heat["grid"])
        self.assertEqual(len(heat["grid"][0]), 49)
        # Hour 0 cell should be valid Moderate/Low from mock wind 5
        cell0 = heat["grid"][0][0]
        self.assertTrue(cell0["weather_valid"])
        self.assertEqual(cell0["overall_risk"], "Low")
