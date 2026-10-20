from ..geo import Point, haversine_miles, sideways_point
from .base import Route

# (where along the trip, how far sideways as a share of the trip length), left then right
VIA_SHAPES = [(0.5, 0.09), (0.5, 0.175)]

SAMPLE_SPACING_MILES = 2.0
SAME_ROAD_MILES = 3.0
GRID_DEGREES = 0.1  # roughly 7 miles, wider than SAME_ROAD_MILES so a 3x3 lookup is enough


MAX_DETOUR = 1.6  # slowest allowed candidate, as a multiple of the fastest
MAX_OVERLAP = 0.8  # more shared road than this and two routes count as the same route


def via_points(origin: Point, destination: Point, trip_miles: float) -> list[Point]:
    points = []
    for fraction, share in VIA_SHAPES:
        for side in (1, -1):
            points.append(sideways_point(origin, destination, fraction, side * share * trip_miles))
    return points


class _Sketch:

    def __init__(self, route: Route):
        self.points = _sample(route)
        self._grid: dict[tuple[int, int], list[Point]] = {}
        for point in self.points:
            self._grid.setdefault(_cell(point), []).append(point)

    def is_near(self, point: Point) -> bool:
        row, col = _cell(point)
        for r in (row - 1, row, row + 1):
            for c in (col - 1, col, col + 1):
                for other in self._grid.get((r, c), ()):
                    if haversine_miles(point, other) <= SAME_ROAD_MILES:
                        return True
        return False

    def share_near(self, other: "_Sketch") -> float:
        near = sum(1 for point in self.points if other.is_near(point))
        return near / len(self.points)


def _cell(point: Point) -> tuple[int, int]:
    return int(point[1] // GRID_DEGREES), int(point[0] // GRID_DEGREES)


def _sample(route: Route) -> list[Point]:
    points = [route.coordinates[0]]
    next_mile = SAMPLE_SPACING_MILES
    for point, mile in zip(route.coordinates[1:], route.cumulative_miles[1:]):
        if mile >= next_mile:
            points.append(point)
            next_mile = mile + SAMPLE_SPACING_MILES
    if points[-1] != route.coordinates[-1]:
        points.append(route.coordinates[-1])
    return points


def overlap(a: _Sketch, b: _Sketch) -> float:
    return max(a.share_near(b), b.share_near(a))


def select_distinct(candidates: list[Route], count: int = 3) -> list[Route]:
    if not candidates:
        return []

    by_speed = sorted(candidates, key=lambda r: r.total_seconds)
    time_limit = by_speed[0].total_seconds * MAX_DETOUR
    pool = [r for r in by_speed if r.total_seconds <= time_limit]

    sketches = {id(r): _Sketch(r) for r in pool}
    chosen = [pool[0]]
    remaining = pool[1:]

    while remaining and len(chosen) < count:
        scored = [
            (max(overlap(sketches[id(r)], sketches[id(c)]) for c in chosen), r.total_seconds, i)
            for i, r in enumerate(remaining)
        ]
        worst_overlap, _, index = min(scored)
        if worst_overlap > MAX_OVERLAP:
            break
        chosen.append(remaining.pop(index))

    return sorted(chosen, key=lambda r: r.total_seconds)
