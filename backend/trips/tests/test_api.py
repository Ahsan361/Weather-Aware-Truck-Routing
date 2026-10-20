from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from rest_framework.test import APIClient

from trips import views
from trips.services.routing import RoutingError
from trips.services.weather import OutsideForecast, RateLimited, WeatherError

URL = "/api/trips/analyze/"
DALLAS = {"lat": 32.7767, "lon": -96.7970, "label": "Dallas, TX"}
HOUSTON = {"lat": 29.7604, "lon": -95.3698, "label": "Houston, TX"}


def in_days(days, hour=6, fmt="%Y-%m-%dT%H:%M"):
    moment = datetime.now(timezone.utc) + timedelta(days=days)
    return moment.replace(hour=hour, minute=0).strftime(fmt)


def body(**overrides):
    base = {
        "origin": DALLAS,
        "destination": HOUSTON,
        "departure": in_days(2),
        "load_lb": 42_000,
        "interval_miles": 25,
    }
    return {**base, **overrides}


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def trips(monkeypatch):
    """Captures the TripRequest the view builds instead of running a real analysis."""
    seen = []

    def fake_analyze(trip):
        seen.append(trip)
        return {"routes": []}

    monkeypatch.setattr(views, "analyze_trip", fake_analyze)
    return seen


def post(client, payload):
    return client.post(URL, payload, format="json")


class TestHappyPath:
    def test_valid_request_reaches_the_analysis(self, client, trips):
        response = post(client, body())
        assert response.status_code == 200
        (trip,) = trips
        assert trip.origin == (DALLAS["lon"], DALLAS["lat"])
        assert trip.destination == (HOUSTON["lon"], HOUSTON["lat"])
        assert trip.load_lb == 42_000
        assert trip.interval_miles == 25

    def test_interval_defaults_to_25(self, client, trips):
        payload = body()
        del payload["interval_miles"]
        assert post(client, payload).status_code == 200
        assert trips[0].interval_miles == 25

    def test_response_carries_the_places_and_origin_timezone(self, client, trips):
        data = post(client, body()).json()
        assert data["origin"]["label"] == "Dallas, TX"
        assert data["origin"]["timezone"] == "America/Chicago"
        assert data["destination"]["label"] == "Houston, TX"

    def test_places_do_not_need_labels(self, client, trips):
        origin = {"lat": DALLAS["lat"], "lon": DALLAS["lon"]}
        assert post(client, body(origin=origin)).status_code == 200


class TestDepartureTime:
    def test_a_time_without_an_offset_is_local_time_at_the_origin(self, client, trips):
        local = in_days(2, hour=6)
        post(client, body(departure=local))
        expected = datetime.fromisoformat(local).replace(tzinfo=ZoneInfo("America/Chicago")).astimezone(timezone.utc)
        assert trips[0].departure == expected
        assert trips[0].departure.tzinfo is not None

    def test_an_explicit_offset_is_respected(self, client, trips):
        stamp = in_days(2, hour=6) + "-08:00"
        post(client, body(departure=stamp))
        assert trips[0].departure == datetime.fromisoformat(stamp).astimezone(timezone.utc)

    def test_z_suffix_means_utc(self, client, trips):
        stamp = in_days(2, hour=14, fmt="%Y-%m-%dT%H:%M:00Z")
        post(client, body(departure=stamp))
        assert trips[0].departure.hour == 14

    def test_leaving_now_is_fine(self, client, trips):
        assert post(client, body(departure=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))).status_code == 200


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"origin": {"lat": 95, "lon": -96.8}}, "origin"),
        ({"origin": {"lat": 32.7}}, "origin"),
        ({"destination": None}, "destination"),
        ({"load_lb": -1}, "load_lb"),
        ({"load_lb": 500_000}, "load_lb"),
        ({"load_lb": "heavy"}, "load_lb"),
        ({"interval_miles": 30}, "interval_miles"),
        ({"departure": "next tuesday"}, "departure"),
        ({"departure": in_days(-3)}, "departure"),
        ({"departure": in_days(30)}, "departure"),
        ({"destination": DALLAS}, "destination"),
    ],
)
def test_bad_input_is_a_400_that_names_the_field(client, trips, overrides, field):
    response = post(client, body(**overrides))
    assert response.status_code == 400
    assert field in response.json()
    assert trips == []


def test_missing_fields_are_reported(client, trips):
    response = post(client, {})
    assert response.status_code == 400
    assert {"origin", "destination", "departure", "load_lb"} <= set(response.json())


class TestUpstreamFailures:
    @pytest.mark.parametrize(
        "error, status",
        [
            (RoutingError("service down"), 502),
            (WeatherError("service down"), 502),
            (OutsideForecast("too far ahead"), 400),
            (RateLimited("busy"), 503),
        ],
    )
    def test_errors_become_clear_responses(self, client, monkeypatch, error, status):
        def explode(trip):
            raise error

        monkeypatch.setattr(views, "analyze_trip", explode)
        response = post(client, body())
        assert response.status_code == status
        assert str(error) in response.json()["detail"]

    def test_rate_limit_tells_the_client_when_to_retry(self, client, monkeypatch):
        def explode(trip):
            raise RateLimited("busy")

        monkeypatch.setattr(views, "analyze_trip", explode)
        assert post(client, body())["Retry-After"] == "60"


def test_analyze_only_accepts_post(client):
    assert client.get(URL).status_code == 405


def test_health_check(client):
    assert client.get("/api/health/").json() == {"status": "ok"}
