from datetime import datetime, timedelta, timezone

import pytest

from trips.services import analysis
from trips.services.analysis import TripRequest, analyze_trip
from trips.services.checkpoints import build_checkpoints
from trips.services.weather import HourlyForecast, OutsideForecast

from .factories import east_west_line, make_route

DEPARTURE = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)  # forecast runs to 16 Nov 23:00
ORIGIN, DESTINATION = (0.0, 40.0), (1.9, 40.0)

STORMY, MIDDLE, SOUTH = 40.0, 40.5, 39.5


def routes():
    return [make_route(east_west_line(lat, 0, 1.9, 100), mph=60) for lat in (STORMY, MIDDLE, SOUTH)]


def forecast_for(start: datetime, end: datetime, wind=5.0, wind_at=None, rain_at=None, snow_at=None):
    """Hourly forecast from `start` to `end` inclusive. Keys of the *_at dicts are hours after `start`."""
    hours = int((end - start).total_seconds() // 3600) + 1
    wind_list = [wind] * hours
    for hour, value in (wind_at or {}).items():
        wind_list[hour] = value
    rain = [0.0] * hours
    for hour, value in (rain_at or {}).items():
        rain[hour] = value
    snow = [0.0] * hours
    for hour, value in (snow_at or {}).items():
        snow[hour] = value
    return HourlyForecast(start, wind_list, rain, snow)


@pytest.fixture
def run(monkeypatch):
    """Runs an analysis with fake routes and a forecast made by `make_forecast(lat, start, end)`."""
    calls = []

    def go(make_forecast=None, load_lb=20_000, interval=25, departure=DEPARTURE, now=NOW):
        make_forecast = make_forecast or (lambda lat, start, end: forecast_for(start, end))

        def fake_fetch(points, start, end):
            calls.append((len(points), start, end))
            return [make_forecast(lat, start, end) for _, lat in points]

        monkeypatch.setattr(analysis, "find_routes", lambda origin, destination: routes())
        monkeypatch.setattr(analysis, "fetch_forecasts", fake_fetch)
        request = TripRequest(ORIGIN, DESTINATION, departure, load_lb, interval)
        return analyze_trip(request, now=now)

    go.calls = calls
    return go


def storm_on_first_route(lat, start, end):
    return forecast_for(start, end, wind_at={2: 60.0} if abs(lat - STORMY) < 0.2 else None)


def test_response_has_everything_the_map_needs(run):
    result = run()
    assert [r["id"] for r in result["routes"]] == [0, 1, 2]
    assert sorted(r["rank"] for r in result["routes"]) == [1, 2, 3]
    assert result["departure"] == "2026-11-03T06:00:00Z"
    assert [lvl["label"] for lvl in result["risk_levels"]] == ["Low", "Moderate", "High", "Severe", "No Travel"]

    route = result["routes"][0]
    assert {"distance_miles", "duration_minutes", "arrival", "summary", "segments", "checkpoints"} <= set(route)
    checkpoint = route["checkpoints"][0]
    assert checkpoint["mile"] == 0
    assert checkpoint["eta"] == "2026-11-03T06:00:00Z"
    assert set(checkpoint["weather"]) == {"wind_mph", "rain_in_hr", "snow_in_hr"}
    assert set(checkpoint["risk"]) == {"level", "factor", "wind", "rain", "snow"}


def test_checkpoints_follow_the_requested_interval(run):
    miles = [cp["mile"] for cp in run(interval=25)["routes"][0]["checkpoints"]]
    assert miles[:5] == [0, 25, 50, 75, 100]
    assert len(run(interval=10)["routes"][0]["checkpoints"]) > len(miles)


def test_a_storm_only_affects_checkpoints_reached_during_that_hour(run):
    stormy = run(storm_on_first_route)["routes"][0]
    levels = [cp["risk"]["level"] for cp in stormy["checkpoints"]]
    # ETAs are 06:00, 06:25, 06:50, 07:15 and then 07:39 and 07:41, so only the last two
    # are closest to the 08:00 reading
    assert levels == [0, 0, 0, 0, 4, 4]
    assert stormy["checkpoints"][-1]["risk"]["factor"] == "wind"


def test_the_route_that_avoids_the_storm_is_recommended(run):
    result = run(storm_on_first_route)
    best = result["recommendation"]["route_id"]
    assert best != 0
    assert next(r for r in result["routes"] if r["id"] == best)["rank"] == 1
    assert next(r for r in result["routes"] if r["id"] == 0)["rank"] == 3
    # the reason compares the winner with the runner-up, and those two are both clear of the storm
    assert "Same weather exposure" in result["recommendation"]["reason"]


def test_summary_counts_the_miles_in_each_risk_level(run):
    summary = run(storm_on_first_route)["routes"][0]["summary"]
    no_travel_miles = summary["miles_by_level"][4]
    assert 0 < no_travel_miles < 40
    assert sum(summary["miles_by_level"]) == pytest.approx(run()["routes"][0]["distance_miles"], abs=0.5)
    assert summary["worst_level"] == 4


def test_calm_weather_is_low_everywhere(run):
    for route in run()["routes"]:
        assert route["summary"]["worst_level"] == 0
        assert route["summary"]["avg_risk"] == 0


def test_heavier_loads_make_the_same_wind_worse(run):
    windy = lambda lat, start, end: forecast_for(start, end, wind=40.0)  # noqa: E731
    light = run(windy, load_lb=20_000)["routes"][0]["checkpoints"][1]["risk"]
    heavy = run(windy, load_lb=45_000)["routes"][0]["checkpoints"][1]["risk"]
    assert (light["level"], heavy["level"]) == (2, 3)
    assert heavy["factor"] == "wind"


def test_rain_and_snow_are_judged_too(run):
    wet = lambda lat, start, end: forecast_for(start, end, rain_at={h: 0.6 for h in range(24)}, snow_at={h: 1.2 for h in range(24)})  # noqa: E731
    risk = run(wet)["routes"][0]["checkpoints"][0]["risk"]
    assert (risk["rain"], risk["snow"], risk["level"]) == (3, 2, 3)


class TestHeatmap:
    def test_covers_forty_eight_hours_for_every_checkpoint(self, run):
        result = run()
        heatmap = result["heatmap"]
        assert heatmap["start"] == "2026-11-03T06:00:00Z"
        assert heatmap["hours"] == 48
        assert len(heatmap["points"]) == sum(len(r["checkpoints"]) for r in result["routes"])
        assert all(len(p["levels"]) == 49 for p in heatmap["points"])

    def test_hour_zero_is_the_departure_hour(self, run):
        heatmap = run(storm_on_first_route)["heatmap"]
        stormy_points = [p for p in heatmap["points"] if abs(p["lat"] - STORMY) < 0.2]
        calm_points = [p for p in heatmap["points"] if abs(p["lat"] - STORMY) >= 0.2]
        assert all(p["levels"][2] == 4 for p in stormy_points)
        assert all(p["levels"][1] == 0 and p["levels"][3] == 0 for p in stormy_points)
        assert all(max(p["levels"]) == 0 for p in calm_points)

    def test_departing_mid_hour_still_starts_on_the_hour(self, run):
        heatmap = run(departure=DEPARTURE + timedelta(minutes=40))["heatmap"]
        assert heatmap["start"] == "2026-11-03T06:00:00Z"

    def test_is_cut_short_where_the_forecast_runs_out(self, run):
        late = datetime(2026, 11, 16, 8, 0, tzinfo=timezone.utc)  # forecast ends 23:00 that day
        heatmap = run(departure=late)["heatmap"]
        assert heatmap["hours"] == 15
        assert all(len(p["levels"]) == 16 for p in heatmap["points"])


class TestForecastWindow:
    def test_asks_for_exactly_the_hours_the_trip_and_heatmap_need(self, run):
        run()
        ((count, start, end),) = run.calls
        assert count == sum(len(build_checkpoints(r, DEPARTURE, 25)) for r in routes())
        assert start == datetime(2026, 11, 3, 6, tzinfo=timezone.utc)
        assert end == datetime(2026, 11, 5, 6, tzinfo=timezone.utc)  # 48 hours after departure

    def test_starts_on_the_hour_even_when_departing_mid_hour(self, run):
        run(departure=DEPARTURE + timedelta(minutes=40))
        assert run.calls[0][1] == datetime(2026, 11, 3, 6, tzinfo=timezone.utc)

    def test_a_long_trip_extends_the_window(self, monkeypatch, run):
        slow = [make_route(east_west_line(40, 0, 1.9, 100), mph=2)]  # about 50 hours
        run()
        monkeypatch.setattr(analysis, "find_routes", lambda o, d: slow)
        analyze_trip(TripRequest(ORIGIN, DESTINATION, DEPARTURE, 20_000, 50), now=NOW)
        end = run.calls[-1][2]
        assert end > datetime(2026, 11, 5, 6, tzinfo=timezone.utc)
        assert end.minute == 0

    def test_trip_ending_after_the_forecast_is_rejected(self, run):
        with pytest.raises(OutsideForecast):
            run(departure=datetime(2026, 11, 16, 22, 0, tzinfo=timezone.utc))


class TestSegments:
    def test_pieces_join_up_and_span_the_whole_route(self, run):
        for route in run(storm_on_first_route)["routes"]:
            segments = route["segments"]
            assert segments
            for before, after in zip(segments, segments[1:]):
                assert before["coordinates"][-1] == after["coordinates"][0]
            assert segments[0]["coordinates"][0][0] == pytest.approx(0.0)
            assert segments[-1]["coordinates"][-1][0] == pytest.approx(1.9)

    def test_pieces_carry_the_risk_of_their_checkpoint(self, run):
        stormy = run(storm_on_first_route)["routes"][0]["segments"]
        assert [s["level"] for s in stormy] == [0, 4]
        assert all(len(s["coordinates"]) >= 2 for s in stormy)

    def test_calm_route_is_a_single_piece(self, run):
        calm = run()["routes"][1]["segments"]
        assert len(calm) == 1 and calm[0]["level"] == 0

    def test_straight_roads_are_simplified_to_few_points(self, run):
        assert len(run()["routes"][0]["segments"][0]["coordinates"]) <= 5
