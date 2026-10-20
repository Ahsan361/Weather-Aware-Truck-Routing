from datetime import datetime, timedelta, timezone

import pytest
import requests

from trips.services import weather
from trips.services.risk import Weather
from trips.services.weather import HourlyForecast, OutsideForecast, RateLimited, WeatherError

START = datetime(2026, 11, 3, tzinfo=timezone.utc)
DAY = (datetime(2026, 11, 3, 6, tzinfo=timezone.utc), datetime(2026, 11, 5, 6, tzinfo=timezone.utc))


def body_for(count, hours=48, wind=10.0, rain=0.0, showers=0.0, snow=0.0):
    def one():
        return {
            "hourly": {
                "time": ["2026-11-03T00:00"] + [f"later-{i}" for i in range(1, hours)],
                "wind_speed_10m": [wind] * hours,
                "rain": [rain] * hours,
                "showers": [showers] * hours,
                "snowfall": [snow] * hours,
            }
        }

    return [one() for _ in range(count)] if count > 1 else one()


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    monkeypatch.setattr(weather.time, "sleep", lambda seconds: None)


@pytest.fixture
def api(monkeypatch):
    """Replaces requests.get, records the params and answers every batch with calm weather."""
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params)
        return FakeResponse(body_for(len(params["latitude"].split(","))))

    monkeypatch.setattr(weather.requests, "get", fake_get)
    return calls


def forecast(wind=None, rain=None, snow=None, hours=24):
    zeros = [0.0] * hours
    return HourlyForecast(START, wind or list(zeros), rain or list(zeros), snow or list(zeros))


class TestHourlyForecast:
    def test_wind_uses_the_nearest_hour(self):
        wind = [0.0] * 24
        wind[6] = 30.0
        f = forecast(wind=wind)
        assert f.at(START + timedelta(hours=6, minutes=20)).wind_mph == 30
        assert f.at(START + timedelta(hours=5, minutes=40)).wind_mph == 30
        assert f.at(START + timedelta(hours=6, minutes=40)).wind_mph == 0

    def test_rain_uses_the_hour_that_ends_after_arrival(self):
        # the 07:00 value is the rain that fell between 06:00 and 07:00
        rain = [0.0] * 24
        rain[7] = 0.6
        f = forecast(rain=rain)
        assert f.at(START + timedelta(hours=6, minutes=20)).rain_in_hr == 0.6
        assert f.at(START + timedelta(hours=6, minutes=59)).rain_in_hr == 0.6
        assert f.at(START + timedelta(hours=7)).rain_in_hr == 0.6
        assert f.at(START + timedelta(hours=7, minutes=1)).rain_in_hr == 0

    def test_snow_follows_the_same_rule_as_rain(self):
        snow = [0.0] * 24
        snow[10] = 1.5
        assert forecast(snow=snow).at(START + timedelta(hours=9, minutes=10)).snow_in_hr == 1.5

    def test_times_outside_the_data_are_clamped(self):
        f = forecast(wind=[5.0] + [0.0] * 23)
        assert f.at(START - timedelta(hours=3)).wind_mph == 5
        assert f.at(START + timedelta(days=9)).wind_mph == 0

    def test_at_hour_reads_the_stamp_directly(self):
        f = forecast(wind=[float(h) for h in range(24)])
        assert f.at_hour(9) == Weather(9.0, 0.0, 0.0)


class TestFetch:
    def test_asks_for_the_right_units_and_hours(self, api):
        weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        params = api[0]
        assert params["wind_speed_unit"] == "mph"
        assert params["precipitation_unit"] == "inch"
        assert params["timezone"] == "UTC"
        assert (params["start_hour"], params["end_hour"]) == ("2026-11-03T06:00", "2026-11-05T06:00")
        assert "snowfall" in params["hourly"]

    def test_returns_one_forecast_per_point_in_order(self, monkeypatch):
        def fake_get(url, params, timeout):
            lats = [float(x) for x in params["latitude"].split(",")]
            body = body_for(len(lats))
            items = body if isinstance(body, list) else [body]
            for lat, item in zip(lats, items):
                item["hourly"]["wind_speed_10m"] = [lat] * 48  # the wind says which point this is
            return FakeResponse(body)

        monkeypatch.setattr(weather.requests, "get", fake_get)
        points = [(-96.8, 30.1), (-96.8, 31.2), (-96.8, 32.3)]
        result = weather.fetch_forecasts(points, *DAY)
        assert [f.wind_mph[0] for f in result] == [30.1, 31.2, 32.3]

    def test_single_location_response_is_not_a_list(self, api):
        (result,) = weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert result.start == START

    def test_rain_is_rain_plus_showers(self, monkeypatch):
        body = body_for(1, rain=0.1, showers=0.15, snow=0.4)
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: FakeResponse(body))
        (result,) = weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert result.rain_in[0] == pytest.approx(0.25)
        assert result.snow_in[0] == 0.4

    def test_missing_values_count_as_zero(self, monkeypatch):
        body = body_for(1, hours=3)
        body["hourly"]["wind_speed_10m"][1] = None
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: FakeResponse(body))
        (result,) = weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert result.wind_mph == [10.0, 0.0, 10.0]

    def test_nearby_points_share_one_lookup(self, api):
        points = [(-96.801, 32.801), (-96.804, 32.796), (-96.80, 32.80), (-90.0, 35.0)]
        result = weather.fetch_forecasts(points, *DAY)
        assert len(result) == 4
        assert len(api[0]["latitude"].split(",")) == 2  # two distinct grid cells
        assert result[0] is result[1] is result[2]

    def test_big_requests_are_split_into_small_batches(self, api):
        points = [(-100 + i * 0.2, 35.0) for i in range(250)]
        result = weather.fetch_forecasts(points, *DAY)
        sizes = [len(c["latitude"].split(",")) for c in api]
        assert len(result) == 250
        assert max(sizes) == weather.BATCH_SIZE
        assert sum(sizes) == 250

    def test_second_identical_request_comes_from_the_cache(self, api):
        weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert len(api) == 1

    def test_only_uncached_points_are_requested(self, api):
        weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        weather.fetch_forecasts([(-96.8, 32.8), (-90.0, 35.0)], *DAY)
        assert api[1]["latitude"] == "35.0"

    def test_a_different_time_window_is_not_a_cache_hit(self, api):
        start, end = DAY
        weather.fetch_forecasts([(-96.8, 32.8)], start, end)
        weather.fetch_forecasts([(-96.8, 32.8)], start, end + timedelta(hours=5))
        assert len(api) == 2


class TestFailures:
    def test_rate_limit_gets_its_own_error_and_is_not_retried(self, monkeypatch):
        calls = []
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: calls.append(1) or FakeResponse({}, status=429))
        with pytest.raises(RateLimited):
            weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert len(calls) == 1

    def test_server_errors_are_retried_then_reported(self, monkeypatch):
        calls = []
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: calls.append(1) or FakeResponse({}, status=503))
        with pytest.raises(WeatherError, match="503"):
            weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert len(calls) == weather.RETRIES + 1

    def test_a_blip_followed_by_success_is_invisible(self, monkeypatch):
        answers = [FakeResponse({}, status=503), FakeResponse(body_for(1))]
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: answers.pop(0))
        assert weather.fetch_forecasts([(-96.8, 32.8)], *DAY)

    def test_timeouts_are_retried_too(self, monkeypatch):
        outcomes = [requests.Timeout("slow"), FakeResponse(body_for(1))]

        def flaky(*a, **k):
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(weather.requests, "get", flaky)
        assert weather.fetch_forecasts([(-96.8, 32.8)], *DAY)

    def test_persistent_network_errors(self, monkeypatch):
        def boom(*a, **k):
            raise requests.Timeout("slow")

        monkeypatch.setattr(weather.requests, "get", boom)
        with pytest.raises(WeatherError, match="unreachable"):
            weather.fetch_forecasts([(-96.8, 32.8)], *DAY)

    def test_client_errors_are_not_retried(self, monkeypatch):
        calls = []
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: calls.append(1) or FakeResponse({}, status=400))
        with pytest.raises(WeatherError, match="400"):
            weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        assert len(calls) == 1

    def test_wrong_number_of_locations_back(self, monkeypatch):
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: FakeResponse(body_for(2)))
        with pytest.raises(WeatherError, match="wrong number"):
            weather.fetch_forecasts([(-96.8, 32.8), (-90.0, 35.0), (-80.0, 40.0)], *DAY)

    def test_failures_are_not_cached(self, monkeypatch):
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: FakeResponse({}, status=500))
        with pytest.raises(WeatherError):
            weather.fetch_forecasts([(-96.8, 32.8)], *DAY)
        monkeypatch.setattr(weather.requests, "get", lambda *a, **k: FakeResponse(body_for(1)))
        assert weather.fetch_forecasts([(-96.8, 32.8)], *DAY)


def test_forecast_horizon_is_sixteen_days_counting_today():
    now = datetime(2026, 10, 18, 14, 30, tzinfo=timezone.utc)
    assert weather.last_forecast_hour(now) == datetime(2026, 11, 2, 23, tzinfo=timezone.utc)
    assert issubclass(OutsideForecast, WeatherError)
