from dataclasses import dataclass
from functools import cached_property
from itertools import accumulate

from ..geo import Point


class RoutingError(Exception):
    """The routing provider could not give us a usable route. This is usually when a problem occurs in the provider service"""


@dataclass(frozen=True)
class Route:
    coordinates: list[Point]
    segment_miles: list[float]  # one per gap between coordinates
    segment_seconds: list[float]

    def __post_init__(self):
        gaps = len(self.coordinates) - 1
        if gaps < 1 or len(self.segment_miles) != gaps or len(self.segment_seconds) != gaps:
            raise ValueError("a route needs one distance and one duration per coordinate gap")

    @cached_property
    def cumulative_miles(self) -> list[float]:
        return [0.0, *accumulate(self.segment_miles)]

    @cached_property
    def cumulative_seconds(self) -> list[float]:
        return [0.0, *accumulate(self.segment_seconds)]

    @property
    def total_miles(self) -> float:
        return self.cumulative_miles[-1]

    @property
    def total_seconds(self) -> float:
        return self.cumulative_seconds[-1]
