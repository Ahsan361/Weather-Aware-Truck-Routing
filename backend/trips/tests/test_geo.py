import math
import time

from trips.services.geo import haversine_miles, simplify


def test_straight_line_collapses_to_its_ends():
    line = [(i * 0.01, 40.0) for i in range(100)]
    assert simplify(line, 0.05) == [line[0], line[-1]]


def test_a_real_corner_is_kept():
    line = [(0, 40), (0.5, 40), (1.0, 40), (1.0, 40.5), (1.0, 41.0)]
    assert simplify(line, 0.05) == [(0, 40), (1.0, 40), (1.0, 41.0)]


def test_small_wiggles_inside_the_tolerance_are_dropped():
    wiggly = [(i * 0.1, 40 + (0.0001 if i % 2 else 0)) for i in range(11)]  # 0.007 miles off the line
    assert simplify(wiggly, 0.02) == [wiggly[0], wiggly[-1]]


def test_zero_tolerance_keeps_every_bend():
    line = [(0, 40), (0.1, 40.01), (0.2, 40), (0.3, 40.01)]
    assert simplify(line, 0) == line


def test_ends_are_always_kept_and_order_is_preserved():
    line = [(i * 0.05, 40 + (i % 3) * 0.02) for i in range(40)]
    result = simplify(line, 0.3)
    assert result[0] == line[0] and result[-1] == line[-1]
    positions = [line.index(p) for p in result]
    assert positions == sorted(positions)


def test_short_inputs_come_back_unchanged():
    assert simplify([], 1) == []
    assert simplify([(0, 0)], 1) == [(0, 0)]
    assert simplify([(0, 0), (1, 1)], 1) == [(0, 0), (1, 1)]


def distance_to_polyline(point, polyline):
    """Shortest distance in miles from point to the polyline, in flat miles around the point."""
    kx, ky = 69.17 * math.cos(math.radians(point[1])), 69.0
    px, py = point[0] * kx, point[1] * ky
    best = float("inf")
    for (lon1, lat1), (lon2, lat2) in zip(polyline, polyline[1:]):
        ax, ay, bx, by = lon1 * kx, lat1 * ky, lon2 * kx, lat2 * ky
        dx, dy = bx - ax, by - ay
        t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - (ax + t * dx), py - (ay + t * dy)))
    return best


def test_every_original_point_stays_within_the_tolerance_of_the_result():
    line = [(i * 0.01, 40 + math.sin(i / 8) * 0.2) for i in range(400)]
    result = simplify(line, 0.3)
    assert len(result) < len(line) / 3
    for point in line:
        assert distance_to_polyline(point, result) <= 0.3 * 1.05


def test_a_long_route_with_gentle_curves_simplifies_quickly():
    # the shape of a real highway: 19,000 points along a long lazy arc
    line = [(i * 0.001, 40 + 0.3 * math.sin(i / 3000)) for i in range(19_000)]
    started = time.time()
    result = simplify(line, 0.02)
    assert time.time() - started < 1
    assert len(result) < 1500
