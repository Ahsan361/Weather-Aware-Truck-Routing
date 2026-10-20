from dataclasses import dataclass
from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MODERATE = 1
    HIGH = 2
    SEVERE = 3
    NO_TRAVEL = 4

    @property
    def label(self) -> str:
        return self.name.replace("_", " ").title()

@dataclass(frozen=True)
class Scale:
    moderate: float
    high: float
    severe: float
    no_travel: float
    no_travel_inclusive: bool



#assignign rules for each weather condition based on the assessment document provided.The values are in mph for wind and inches for rain and snow.

WIND = Scale(moderate=25, high=35, severe=45, no_travel=55, no_travel_inclusive=True)
RAIN = Scale(moderate=0.10, high=0.25, severe=0.50, no_travel=1.00, no_travel_inclusive=False)
SNOW = Scale(moderate=0.5, high=1.0, severe=2.0, no_travel=3.0, no_travel_inclusive=False)


#rules for load values are in pounds
HEAVY_LOAD_LB = 30_000
VERY_HEAVY_LOAD_LB = 40_000




@dataclass(frozen=True)
class Weather:
    wind_mph: float
    rain_in_hr: float
    snow_in_hr: float



@dataclass(frozen=True)
class RiskAssessment:
    level: RiskLevel
    wind: RiskLevel
    rain: RiskLevel
    snow: RiskLevel




    #Which condition is responsible for the overall level, when everything is Low there is none.
    @property
    def main_factor(self) -> str | None:
        if self.level == RiskLevel.LOW:
            return None
        for name in ("wind", "rain", "snow"):
            if getattr(self, name) == self.level:
                return name
        return None


def classify(value: float, scale: Scale) -> RiskLevel:
    if value > scale.no_travel or (scale.no_travel_inclusive and value == scale.no_travel):
        return RiskLevel.NO_TRAVEL
    if value >= scale.severe:
        return RiskLevel.SEVERE
    if value >= scale.high:
        return RiskLevel.HIGH
    if value >= scale.moderate:
        return RiskLevel.MODERATE
    return RiskLevel.LOW



def wind_level(wind_mph: float, load_lb: float) -> RiskLevel:
    """Wind risk including the load rules: heavy trucks are hit harder by crosswind."""
    level = classify(wind_mph, WIND)
    if level == RiskLevel.SEVERE and load_lb > HEAVY_LOAD_LB:
        return RiskLevel.NO_TRAVEL
    if level == RiskLevel.HIGH and load_lb > VERY_HEAVY_LOAD_LB:
        return RiskLevel.SEVERE
    return level



def assess(weather: Weather, load_lb: float) -> RiskAssessment:
    wind = wind_level(weather.wind_mph, load_lb)
    rain = classify(weather.rain_in_hr, RAIN)
    snow = classify(weather.snow_in_hr, SNOW)
    return RiskAssessment(level=max(wind, rain, snow), wind=wind, rain=rain, snow=snow)