from concurrent.futures import ThreadPoolExecutor

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from ..geo import Point
from . import osrm
from .alternatives import select_distinct, via_points
from .base import Route, RoutingError

PROVIDERS = {"osrm": osrm.fetch_routes}

__all__ = ["Route", "RoutingError", "find_routes"]


def find_routes(origin: Point, destination: Point, count: int = 3) -> list[Route]:
    """Up to `count` distinct routes, fastest first. May return fewer on short trips."""
    try:
        fetch = PROVIDERS[settings.ROUTING_PROVIDER]
    except KeyError:
        raise ImproperlyConfigured(f"unknown ROUTING_PROVIDER {settings.ROUTING_PROVIDER!r}") from None

    candidates = fetch([origin, destination], alternatives=True)
    if not candidates:
        raise RoutingError("no route found between those places")

    detours = via_points(origin, destination, min(r.total_miles for r in candidates))
    with ThreadPoolExecutor(max_workers=4) as pool:
        for routes in pool.map(lambda via: _try(fetch, [origin, via, destination]), detours):
            candidates.extend(routes[:1])

    return select_distinct(candidates, count)


def _try(fetch, points: list[Point]) -> list[Route]:
    # a via-point that can't be routed through is just a candidate we don't get
    try:
        return fetch(points, alternatives=False)
    except RoutingError:
        return []
