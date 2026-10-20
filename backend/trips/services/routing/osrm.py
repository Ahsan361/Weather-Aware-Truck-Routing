import requests
from django.conf import settings

from ..geo import METERS_PER_MILE, Point
from .base import Route, RoutingError

# OSRM only has a car profile, and cars are allowed to go faster than a loaded truck.
# Capping each segment keeps the ETAs (and so the forecast hour we look up) realistic.
TRUCK_MAX_MPH = 62

TIMEOUT_SECONDS = 25


def fetch_routes(points: list[Point], alternatives: bool = False) -> list[Route]:
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in points)
    url = f"{settings.OSRM_BASE_URL}/route/v1/driving/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "annotations": "distance,duration",
        "steps": "false",
        "alternatives": 3 if alternatives else "false",
    }

    try:
        response = requests.get(url, params=params, timeout=TIMEOUT_SECONDS)
    except requests.RequestException as exc:
        raise RoutingError(f"routing service unreachable: {exc}") from exc

    if response.status_code != 200:
        raise RoutingError(f"routing service answered {response.status_code}")

    body = response.json()
    if body.get("code") != "Ok":
        raise RoutingError(body.get("message") or f"routing service said {body.get('code')}")

    return [_parse_route(raw) for raw in body["routes"]]


def _parse_route(raw: dict) -> Route:
    meters: list[float] = []
    seconds: list[float] = []
    for leg in raw["legs"]:
        meters.extend(leg["annotation"]["distance"])
        seconds.extend(leg["annotation"]["duration"])

    miles = [m / METERS_PER_MILE for m in meters]
    seconds = [max(s, mi / TRUCK_MAX_MPH * 3600) for mi, s in zip(miles, seconds)]

    coordinates = [(lon, lat) for lon, lat in raw["geometry"]["coordinates"]]
    return Route(coordinates, miles, seconds)
