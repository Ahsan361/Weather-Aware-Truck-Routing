import math
import time
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import requests
import logging
from django.core.cache import cache

from .geo import Point
from .risk import Weather


logger = logging.getLogger(__name__)
API_URL = "https://api.open-meteo.com/v1/forecast"
HOURLY_FIELDS = "wind_speed_10m,rain,showers,snowfall"

BATCH_SIZE = 15
MAX_WORKERS = 8
TIMEOUT_SECONDS = 25
RETRIES = 2
RETRY_DELAY_SECONDS = 1.0
CACHE_SECONDS = 30 * 60

# 0.1 degrees is about 7 miles, finer than the weather models behind the forecast
GRID_DECIMALS = 1
# the forecast reaches 16 days ahead, counting today
FORECAST_DAYS = 16


class WeatherError(Exception):
    """The forecast could not be fetched."""


class RateLimited(WeatherError):
    """Open-Meteo's per-minute limit was hit."""


class OutsideForecast(WeatherError):
    """The trip runs past the end of the forecast."""


@dataclass(frozen=True)
class HourlyForecast:
    start: datetime  # UTC, the first hour in the lists
    wind_mph: list[float]
    rain_in: list[float]
    snow_in: list[float]

    def at_hour(self, index: int) -> Weather:
        index = min(max(index, 0), len(self.wind_mph) - 1)
        return Weather(self.wind_mph[index], self.rain_in[index], self.snow_in[index])

    def index_of(self, when: datetime) -> float:
        return (when - self.start).total_seconds() / 3600

    def at(self, when: datetime) -> Weather:
        hours = self.index_of(when)
        last = len(self.wind_mph) - 1
        wind_hour = min(max(math.floor(hours + 0.5), 0), last)
        precip_hour = min(max(math.ceil(hours), 0), last)
        return Weather(self.wind_mph[wind_hour], self.rain_in[precip_hour], self.snow_in[precip_hour])


def last_forecast_hour(now: datetime | None = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    last_day = now.date() + timedelta(days=FORECAST_DAYS - 1)
    return datetime(last_day.year, last_day.month, last_day.day, 23, tzinfo=timezone.utc)


def snap(point: Point) -> Point:
    return round(point[0], GRID_DECIMALS), round(point[1], GRID_DECIMALS)


def fetch_forecasts(points: Sequence[Point], start: datetime, end: datetime) -> list[HourlyForecast]:
    cells = [snap(p) for p in points]

    found: dict[Point, HourlyForecast] = {}
    missing: list[Point] = []
    for cell in dict.fromkeys(cells):
        cached = cache.get(_cache_key(cell, start, end))
        if cached is not None:
            found[cell] = cached
        else:
            missing.append(cell)

    batches = [missing[i : i + BATCH_SIZE] for i in range(0, len(missing), BATCH_SIZE)]
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for batch, forecasts in zip(batches, pool.map(lambda b: _request(b, start, end), batches)):
            for cell, forecast in zip(batch, forecasts):
                found[cell] = forecast
                cache.set(_cache_key(cell, start, end), forecast, CACHE_SECONDS)

    return [found[cell] for cell in cells]


def _cache_key(cell: Point, start: datetime, end: datetime) -> str:
    return f"forecast:{cell[1]}:{cell[0]}:{start:%Y%m%d%H}:{end:%Y%m%d%H}"


def _request(cells: list[Point], start: datetime, end: datetime) -> list[HourlyForecast]:
    params = {
        "latitude": ",".join(str(lat) for _, lat in cells),
        "longitude": ",".join(str(lon) for lon, _ in cells),
        "hourly": HOURLY_FIELDS,
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",  # also makes snowfall come back in inches
        "timezone": "UTC",
        "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
        "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
    }
    body = _get_with_retries(params)
    results = body if isinstance(body, list) else [body]  # a single location comes back unwrapped
    if len(results) != len(cells):
        raise WeatherError("weather service returned the wrong number of locations")
    return [_parse(result) for result in results]


def _get_with_retries(params: dict):
    problem = ""
    for attempt in range(RETRIES + 1):
        if attempt:
            time.sleep(RETRY_DELAY_SECONDS * attempt)
        try:
            response = requests.get(API_URL, params=params, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as exc:
            problem = f"weather service unreachable: {exc}"
            continue

        if response.status_code == 200:
            return response.json()
        if response.status_code == 429:
            logger.warning("Open-Meteo refused the request with 429: %s", _reason(response))
            raise RateLimited("The weather service is busy. Please try again in a minute.")
        problem = f"weather service answered {response.status_code}"
        if response.status_code < 500:
            break
    raise WeatherError(problem)


def _reason(response) -> str:
    try:
        return str(response.json().get("reason", "no reason given"))
    except ValueError:
        return "no reason given"


def _parse(result: dict) -> HourlyForecast:
    hourly = result["hourly"]
    start = datetime.fromisoformat(hourly["time"][0]).replace(tzinfo=timezone.utc)

    def clean(values):
        return [v if v is not None else 0.0 for v in values]

    rain = [r + s for r, s in zip(clean(hourly["rain"]), clean(hourly["showers"]))]
    return HourlyForecast(start, clean(hourly["wind_speed_10m"]), rain, clean(hourly["snowfall"]))
