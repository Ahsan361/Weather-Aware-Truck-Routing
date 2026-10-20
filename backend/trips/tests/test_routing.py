import pytest
import requests
from django.core.exceptions import ImproperlyConfigured

from trips.services import routing
from trips.services.geo import METERS_PER_MILE
from trips.services.routing import RoutingError, osrm

from .factories import east_west_line, make_route

ORIGIN = (0.0, 40.0)
DESTINATION = (2.0, 40.0)


class FakeResponse:
    def __init__(self, body, status=200):
        self._body = body
        self.status_code = status

    def json(self):
        return self._body


def osrm_body(legs, coordinates):
    return {
        "code": "Ok",
        "routes": [
            {
                "geometry": {"coordinates": coordinates},
                "legs": [{"annotation": {"distance": d, "duration": t}} for d, t in legs],
            }
        ],
    }


class TestOsrmClient:
    def test_legs_are_joined_end_to_end(self, monkeypatch):
        body = osrm_body(
            legs=[([METERS_PER_MILE * 10] * 2, [600, 600]), ([METERS_PER_MILE * 10], [600])],
            coordinates=[[0, 0], [1, 0], [2, 0], [3, 0]],
        )
        monkeypatch.setattr(osrm.requests, "get", lambda *a, **k: FakeResponse(body))

        (route,) = osrm.fetch_routes([(0, 0), (2, 0), (3, 0)])
        assert route.total_miles == pytest.approx(30)
        assert route.total_seconds == pytest.approx(1800)
        assert len(route.segment_miles) == len(route.coordinates) - 1

    def test_car_speeds_are_capped_at_truck_speed(self, monkeypatch):
        # one mile in 30 seconds is 120 mph
        body = osrm_body(legs=[([METERS_PER_MILE], [30])], coordinates=[[0, 0], [1, 0]])
        monkeypatch.setattr(osrm.requests, "get", lambda *a, **k: FakeResponse(body))

        (route,) = osrm.fetch_routes([(0, 0), (1, 0)])
        assert route.total_seconds == pytest.approx(3600 / osrm.TRUCK_MAX_MPH)

    def test_slow_segments_are_left_alone(self, monkeypatch):
        body = osrm_body(legs=[([METERS_PER_MILE], [600])], coordinates=[[0, 0], [1, 0]])  # 6 mph
        monkeypatch.setattr(osrm.requests, "get", lambda *a, **k: FakeResponse(body))

        (route,) = osrm.fetch_routes([(0, 0), (1, 0)])
        assert route.total_seconds == 600

    def test_unreachable_service_becomes_a_routing_error(self, monkeypatch):
        def boom(*args, **kwargs):
            raise requests.ConnectionError("no network")

        monkeypatch.setattr(osrm.requests, "get", boom)
        with pytest.raises(RoutingError, match="unreachable"):
            osrm.fetch_routes([(0, 0), (1, 0)])

    def test_http_errors_become_routing_errors(self, monkeypatch):
        monkeypatch.setattr(osrm.requests, "get", lambda *a, **k: FakeResponse({}, status=429))
        with pytest.raises(RoutingError, match="429"):
            osrm.fetch_routes([(0, 0), (1, 0)])

    def test_no_route_becomes_a_routing_error(self, monkeypatch):
        body = {"code": "NoRoute", "message": "Impossible route between points"}
        monkeypatch.setattr(osrm.requests, "get", lambda *a, **k: FakeResponse(body))
        with pytest.raises(RoutingError, match="Impossible"):
            osrm.fetch_routes([(0, 0), (1, 0)])


class TestFindRoutes:
    @pytest.fixture
    def fake_provider(self, monkeypatch):
        """Main corridor plus a few alternatives, picked by how many points are requested."""
        calls = []

        def fetch(points, alternatives=False):
            calls.append((points, alternatives))
            if len(points) == 2:
                return [make_route(east_west_line(40.0), mph=60), make_route(east_west_line(40.01), mph=59)]
            via_lat = points[1][1]
            if via_lat > 40:
                return [make_route(east_west_line(40.6), mph=55)]
            if via_lat < 40:
                return [make_route(east_west_line(39.4), mph=52)]
            raise RoutingError("no road there")

        monkeypatch.setitem(routing.PROVIDERS, "osrm", fetch)
        return calls

    def test_returns_three_distinct_routes_fastest_first(self, fake_provider):
        routes = routing.find_routes(ORIGIN, DESTINATION)
        assert len(routes) == 3
        assert [r.total_seconds for r in routes] == sorted(r.total_seconds for r in routes)

    def test_near_copies_from_the_provider_are_dropped(self, fake_provider):
        routes = routing.find_routes(ORIGIN, DESTINATION)
        latitudes = sorted(round(r.coordinates[0][1], 1) for r in routes)
        assert latitudes == [39.4, 40.0, 40.6]

    def test_asks_the_provider_for_alternatives_on_the_direct_request_only(self, fake_provider):
        routing.find_routes(ORIGIN, DESTINATION)
        direct = [alts for points, alts in fake_provider if len(points) == 2]
        via = [alts for points, alts in fake_provider if len(points) == 3]
        assert direct == [True]
        assert via and not any(via)

    def test_a_failing_via_point_is_not_fatal(self, monkeypatch):
        def fetch(points, alternatives=False):
            if len(points) == 3:
                raise RoutingError("nope")
            return [make_route(east_west_line(40.0))]

        monkeypatch.setitem(routing.PROVIDERS, "osrm", fetch)
        assert len(routing.find_routes(ORIGIN, DESTINATION)) == 1

    def test_failing_direct_request_is_fatal(self, monkeypatch):
        def fetch(points, alternatives=False):
            raise RoutingError("down")

        monkeypatch.setitem(routing.PROVIDERS, "osrm", fetch)
        with pytest.raises(RoutingError):
            routing.find_routes(ORIGIN, DESTINATION)

    def test_empty_answer_is_an_error(self, monkeypatch):
        monkeypatch.setitem(routing.PROVIDERS, "osrm", lambda points, alternatives=False: [])
        with pytest.raises(RoutingError, match="no route"):
            routing.find_routes(ORIGIN, DESTINATION)

    def test_unknown_provider_is_a_config_error(self, settings):
        settings.ROUTING_PROVIDER = "carrier-pigeon"
        with pytest.raises(ImproperlyConfigured):
            routing.find_routes(ORIGIN, DESTINATION)
