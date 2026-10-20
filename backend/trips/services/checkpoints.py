from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta

from .routing import Route


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    lon: float
    lat: float
    eta: datetime


def build_checkpoints(route: Route, departure: datetime, interval_miles: float) -> list[Checkpoint]:
    if interval_miles <= 0:
        raise ValueError("interval_miles must be positive")

    total = route.total_miles
    miles = [step * interval_miles for step in range(int(total // interval_miles) + 1)]
    if miles[-1] < total: 
        miles.append(total)

    return [_checkpoint_at(route, mile, departure) for mile in miles]


def _checkpoint_at(route: Route, mile: float, departure: datetime) -> Checkpoint:
    cum_miles = route.cumulative_miles
    last_segment = len(route.segment_miles) - 1
    i = min(max(bisect_right(cum_miles, mile) - 1, 0), last_segment)

    segment_length = route.segment_miles[i]
    share = (mile - cum_miles[i]) / segment_length if segment_length > 0 else 0.0
    share = min(max(share, 0.0), 1.0)

    (lon1, lat1), (lon2, lat2) = route.coordinates[i], route.coordinates[i + 1]
    seconds = route.cumulative_seconds[i] + share * route.segment_seconds[i]

    return Checkpoint(
        mile=mile,
        lon=lon1 + (lon2 - lon1) * share,
        lat=lat1 + (lat2 - lat1) * share,
        eta=departure + timedelta(seconds=seconds),
    )