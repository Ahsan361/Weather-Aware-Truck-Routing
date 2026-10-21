import pytest
import requests
from rest_framework.test import APIClient

from trips.services import geocoding
from trips.services.geocoding import GeocodingError, GeocodingNotConfigured, Place

BODY = {
    "features": [
        {"geometry": {"coordinates": [-96.7970, 32.7767]}, "properties": {"label": "Dallas, TX, USA"}},
        {"geometry": {"coordinates": [-81.1773, 35.3507]}, "properties": {"label": "Dallas, NC, USA"}},
    ]
}


class FakeResponse:
    def __init__(self, body, status=200):
        self._body, self.status_code = body, status

    def json(self):
        return self._body


@pytest.fixture(autouse=True)
def token(settings):
    settings.ORS_API_KEY = "test-token"


@pytest.fixture
def api(monkeypatch):
    calls = []

    def fake_get(url, params, headers, timeout):
        calls.append({"params": params, "headers": headers})
        return FakeResponse(BODY)

    monkeypatch.setattr(geocoding.requests, "get", fake_get)
    return calls


class TestSearch:
    def test_turns_features_into_places(self, api):
        assert geocoding.search_places("Dallas") == [
            Place("Dallas, TX, USA", 32.7767, -96.7970),
            Place("Dallas, NC, USA", 35.3507, -81.1773),
        ]

    def test_sends_the_token_and_the_text(self, api):
        geocoding.search_places("  Dallas   tx ")
        assert api[0]["headers"] == {"Authorization": "test-token"}
        assert api[0]["params"]["text"] == "Dallas tx"

    def test_short_queries_do_not_hit_the_service(self, api):
        assert geocoding.search_places("Da") == []
        assert geocoding.search_places("  ") == []
        assert api == []

    def test_repeat_searches_are_cached(self, api):
        geocoding.search_places("Dallas")
        geocoding.search_places("dallas ")
        assert len(api) == 1

    def test_no_token_is_a_config_error(self, settings):
        settings.ORS_API_KEY = ""
        with pytest.raises(GeocodingNotConfigured):
            geocoding.search_places("Dallas")

    def test_http_errors(self, monkeypatch):
        monkeypatch.setattr(geocoding.requests, "get", lambda *a, **k: FakeResponse({}, status=403))
        with pytest.raises(GeocodingError, match="403"):
            geocoding.search_places("Dallas")

    def test_network_errors(self, monkeypatch):
        def boom(*a, **k):
            raise requests.ConnectionError("down")

        monkeypatch.setattr(geocoding.requests, "get", boom)
        with pytest.raises(GeocodingError, match="unreachable"):
            geocoding.search_places("Dallas")

    def test_no_matches(self, monkeypatch):
        monkeypatch.setattr(geocoding.requests, "get", lambda *a, **k: FakeResponse({"features": []}))
        assert geocoding.search_places("zzzzzz") == []


class TestEndpoint:
    def test_returns_results(self, api):
        response = APIClient().get("/api/geocode/", {"q": "Dallas"})
        assert response.status_code == 200
        assert response.json()["results"][0] == {"label": "Dallas, TX, USA", "lat": 32.7767, "lon": -96.797}

    def test_missing_query_gives_an_empty_list(self, api):
        response = APIClient().get("/api/geocode/")
        assert response.status_code == 200
        assert response.json() == {"results": []}

    def test_service_failure_is_a_502(self, monkeypatch):
        monkeypatch.setattr(geocoding.requests, "get", lambda *a, **k: FakeResponse({}, status=500))
        assert APIClient().get("/api/geocode/", {"q": "Dallas"}).status_code == 502

    def test_missing_token_is_a_503(self, settings):
        settings.ORS_API_KEY = ""
        assert APIClient().get("/api/geocode/", {"q": "Dallas"}).status_code == 503
