import pytest

from trips.services.risk import RAIN, SNOW, WIND, RiskLevel, Weather, assess, classify, wind_level

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


@pytest.mark.parametrize(
    "mph, expected",
    [
        (0, L),
        (24.9, L),
        (25, M),
        (34.9, M),
        (35, H),
        (44.9, H),
        (45, S),
        (54.9, S),
        (55, N),  # according to the assessment document if >= 55
        (80, N),
    ],
)
def test_wind_bands(mph, expected):
    assert classify(mph, WIND) == expected


@pytest.mark.parametrize(
    "rain, expected",
    [
        (0, L),
        (0.09, L),
        (0.10, M),
        (0.24, M),
        (0.25, H),
        (0.49, H),
        (0.50, S),
        (1.00, S),  # according to the assessment document if > 1.00 for No Travel
        (1.01, N),
    ],
)
def test_rain_bands(rain, expected):
    assert classify(rain, RAIN) == expected


@pytest.mark.parametrize(
    "snow, expected",
    [
        (0, L),
        (0.4, L),
        (0.5, M),
        (0.99, M),
        (1.0, H),
        (1.99, H),
        (2.0, S),
        (3.0, S),  # according to the assessment document if > 3.0 for No Travel
        (3.1, N),
    ],
)
def test_snow_bands(snow, expected):
    assert classify(snow, SNOW) == expected


class TestLoadRules:
    def test_gale_force_wind_is_no_travel_for_any_load(self):
        assert wind_level(55, 0) == N
        assert wind_level(60, 5_000) == N

    def test_severe_wind_with_heavy_load_is_no_travel(self):
        assert wind_level(45, 30_001) == N
        assert wind_level(54, 80_000) == N

    def test_severe_wind_with_light_load_stays_severe(self):
        assert wind_level(50, 30_000) == S  # rule is "more than" 30,000
        assert wind_level(50, 10_000) == S

    def test_high_wind_with_very_heavy_load_is_severe(self):
        assert wind_level(35, 40_001) == S
        assert wind_level(44, 80_000) == S

    def test_high_wind_with_ordinary_load_stays_high(self):
        assert wind_level(40, 40_000) == H  # rule is "more than" 40,000
        assert wind_level(40, 25_000) == H

    def test_load_does_not_matter_below_the_wind_bands(self):
        assert wind_level(30, 80_000) == M
        assert wind_level(10, 80_000) == L

    def test_empty_truck_boundary(self):
        assert wind_level(44.9, 0) == H
        assert wind_level(45, 0) == S


class TestAssess:
    def test_calm_weather_is_low(self):
        result = assess(Weather(wind_mph=5, rain_in_hr=0, snow_in_hr=0), load_lb=20_000)
        assert result.level == L
        assert result.main_factor is None

    def test_worst_condition_wins(self):
        result = assess(Weather(wind_mph=10, rain_in_hr=0.3, snow_in_hr=0.6), load_lb=20_000)
        assert (result.wind, result.rain, result.snow) == (L, H, M)
        assert result.level == H
        assert result.main_factor == "rain"

    def test_load_rule_can_lift_the_overall_level(self):
        weather = Weather(wind_mph=40, rain_in_hr=0.1, snow_in_hr=0)
        assert assess(weather, load_lb=20_000).level == H
        heavy = assess(weather, load_lb=45_000)
        assert heavy.level == S
        assert heavy.main_factor == "wind"

    def test_snow_can_be_no_travel_on_its_own(self):
        result = assess(Weather(wind_mph=0, rain_in_hr=0, snow_in_hr=3.5), load_lb=1_000)
        assert result.level == N
        assert result.main_factor == "snow"

    def test_level_labels(self):
        assert N.label == "No Travel"
        assert L.label == "Low"
