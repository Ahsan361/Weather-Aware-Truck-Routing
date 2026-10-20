"""Address search for the trip form, using openrouteservice's autocomplete."""

import hashlib
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache

API_URL = "https://api.openrouteservice.org/geocode/autocomplete"
MIN_QUERY_LENGTH = 3
RESULT_LIMIT = 6
TIMEOUT_SECONDS = 10
CACHE_SECONDS = 10 * 60


class GeocodingError(Exception):
    """The address search failed."""


class GeocodingNotConfigured(GeocodingError):
    """There is no API token to search with."""


@dataclass(frozen=True)
class Place:
    label: str
    lat: float
    lon: float


def search_places(query: str) -> list[Place]:
    query = " ".join(query.split())
    if len(query) < MIN_QUERY_LENGTH:
        return []

    key = "geocode:" + hashlib.sha1(query.lower().encode()).hexdigest()
    cached = cache.get(key)
    if cached is not None:
        return cached

    if not settings.ROUTING_KEY:
        raise GeocodingNotConfigured("address search needs ROUTING_KEY (an openrouteservice token)")

    try:
        response = requests.get(
            API_URL,
            params={"text": query, "size": RESULT_LIMIT},
            headers={"Authorization": settings.ROUTING_KEY},
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise GeocodingError(f"address search unreachable: {exc}") from exc

    if response.status_code != 200:
        raise GeocodingError(f"address search answered {response.status_code}")

    places = [_parse(feature) for feature in response.json().get("features", [])]
    cache.set(key, places, CACHE_SECONDS)
    return places


def _parse(feature: dict) -> Place:
    lon, lat = feature["geometry"]["coordinates"][:2]
    return Place(label=feature["properties"]["label"], lat=lat, lon=lon)
