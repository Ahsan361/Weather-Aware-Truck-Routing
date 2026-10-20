import pytest

from trips.services.geo import haversine_miles, sideways_point
from trips.services.routing.alternatives import _Sketch, overlap, select_distinct, via_points

from .factories import east_west_line, make_route


class TestGeo:
    def test_haversine_known_distance(self):
        # Los Angeles to Dallas is roughly 1,235 miles as the crow flies
        assert haversine_miles((-118.2437, 34.0522), (-96.7970, 32.7767)) == pytest.approx(1235, abs=15)

    def test_left_of_an_eastbound_trip_is_north(self):
        point = sideways_point((0, 40), (2, 40), 0.5, 30)
        assert point[0] == pytest.approx(1.0)
        assert point[1] > 40

    def test_negative_offset_goes_to_the_right(self):
        assert sideways_point((0, 40), (2, 40), 0.5, -30)[1] < 40

    def test_offset_distance_is_about_right(self):
        midpoint = (1.0, 40.0)
        point = sideways_point((0, 40), (2, 40), 0.5, 30)
        assert haversine_miles(midpoint, point) == pytest.approx(30, abs=1)


def test_via_points_cover_both_sides_of_the_corridor():
    points = via_points((0, 40), (2, 40), trip_miles=100)
    assert len(points) == 4
    assert any(lat > 40 for _, lat in points) and any(lat < 40 for _, lat in points)


class TestOverlap:
    def test_same_road_overlaps_completely(self):
        sketch = _Sketch(make_route(east_west_line(40)))
        assert overlap(sketch, sketch) == 1

    def test_parallel_roads_far_apart_do_not_overlap(self):
        a = _Sketch(make_route(east_west_line(40.0)))
        b = _Sketch(make_route(east_west_line(40.5)))  # about 35 miles north
        assert overlap(a, b) == 0

    def test_roads_a_mile_apart_count_as_the_same_road(self):
        a = _Sketch(make_route(east_west_line(40.0)))
        b = _Sketch(make_route(east_west_line(40.012)))  # about 0.8 miles north
        assert overlap(a, b) > 0.95

    def test_short_route_inside_a_long_one_is_still_a_duplicate(self):
        long_road = _Sketch(make_route(east_west_line(40, 0, 2, 100)))
        inside = _Sketch(make_route(east_west_line(40, 0.5, 1.0, 25)))
        assert overlap(long_road, inside) > 0.9


class TestSelectDistinct:
    def test_keeps_three_different_corridors_fastest_first(self):
        north = make_route(east_west_line(40.5), mph=55)
        middle = make_route(east_west_line(40.0), mph=60)
        south = make_route(east_west_line(39.5), mph=50)
        chosen = select_distinct([south, north, middle])
        assert chosen == [middle, north, south]

    def test_drops_near_duplicates(self):
        main = make_route(east_west_line(40.0), mph=60)
        copy = make_route(east_west_line(40.01), mph=59)
        other = make_route(east_west_line(40.5), mph=55)
        chosen = select_distinct([main, copy, other])
        assert chosen == [main, other]

    def test_drops_silly_detours(self):
        main = make_route(east_west_line(40.0), mph=60)
        crawl = make_route(east_west_line(40.5), mph=30)  # twice as slow
        assert select_distinct([main, crawl]) == [main]

    def test_never_returns_more_than_asked(self):
        routes = [make_route(east_west_line(39 + i * 0.5), mph=60 - i) for i in range(5)]
        assert len(select_distinct(routes, count=3)) == 3

    def test_prefers_the_most_different_candidate_over_the_fastest(self):
        main = make_route(east_west_line(40.0), mph=60)
        # shares roughly half its length with main, but is faster
        half = make_route(east_west_line(40.0, 0, 1.0, 50) + east_west_line(40.5, 1.0, 2.0, 50), mph=58)
        far = make_route(east_west_line(41.0), mph=45)
        chosen = select_distinct([main, half, far], count=2)
        assert far in chosen

    def test_single_candidate_and_empty_input(self):
        only = make_route(east_west_line(40.0))
        assert select_distinct([only]) == [only]
        assert select_distinct([]) == []
