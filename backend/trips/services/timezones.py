from datetime import tzinfo
from functools import lru_cache
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder

from .geo import Point


@lru_cache(maxsize=1)
def _finder() -> TimezoneFinder:
    return TimezoneFinder()


def timezone_name_at(point: Point) -> str:
    return _finder().timezone_at(lng=point[0], lat=point[1]) or "UTC"


def timezone_at(point: Point) -> tzinfo:
    return ZoneInfo(timezone_name_at(point))
