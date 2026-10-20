import pytest

from trips.services.recommend import (
    RouteSummary,
    checkpoint_spans,
    rank_routes,
    recommendation_reason,
    summarize_route,
)
from trips.services.risk import RiskLevel

L, M, H, S, N = (
    RiskLevel.LOW,
    RiskLevel.MODERATE,
    RiskLevel.HIGH,
    RiskLevel.SEVERE,
    RiskLevel.NO_TRAVEL,
)


def route(miles_and_levels, total, minutes):
    miles = [m for m, _ in miles_and_levels]
    levels = [lvl for _, lvl in miles_and_levels]
    return summarize_route(miles, levels, total, minutes)


def exposed(total, minutes, no_travel=0.0, severe=0.0, high=0.0, moderate=0.0):
    """A route summary built straight from miles of exposure, so a test can isolate one criterion."""
    clear = total - no_travel - severe - high - moderate
    miles_by_level = {L: clear, M: moderate, H: high, S: severe, N: no_travel}
    avg_risk = (moderate + 2 * high + 3 * severe + 4 * no_travel) / total
    return RouteSummary(total, minutes, miles_by_level, avg_risk)


def haul(total, minutes, **levels_at):
    """A long trip with a checkpoint every 25 miles, all Low except where `m<mile>=level` says so.

    Each checkpoint stands for 25 miles of road (half that at the very ends).
    """
    miles = list(range(0, int(total) + 1, 25))
    levels = [levels_at.get(f"m{mile}", L) for mile in miles]
    return summarize_route(miles, levels, total, minutes)


class TestSpans:
    def test_spans_add_up_to_the_whole_route(self):
        spans = checkpoint_spans([0, 25, 50, 75, 90], 90)
        assert sum(spans) == pytest.approx(90)

    def test_each_checkpoint_covers_half_way_to_its_neighbours(self):
        assert checkpoint_spans([0, 25, 50], 50) == [12.5, 25, 12.5]

    def test_single_checkpoint_covers_everything(self):
        assert checkpoint_spans([0], 40) == [40]


class TestSummary:
    def test_miles_are_attributed_to_the_right_level(self):
        summary = route([(0, L), (25, S), (50, S), (75, H), (100, L)], total=100, minutes=120)
        # edges sit halfway between checkpoints: 12.5, 37.5, 62.5, 87.5
        assert summary.severe_miles == pytest.approx(50)  # miles 12.5 to 62.5
        assert summary.high_miles == pytest.approx(25)  # miles 62.5 to 87.5
        assert sum(summary.miles_by_level.values()) == pytest.approx(100)

    def test_average_risk_is_weighted_by_miles(self):
        # checkpoints at 25 and 75 split a 100 mile route in half: 50 miles Low (0), 50 Severe (3)
        summary = route([(25, L), (75, S)], total=100, minutes=60)
        assert summary.avg_risk == pytest.approx(1.5)

    def test_last_checkpoint_covers_the_road_to_the_destination(self):
        summary = route([(0, L), (50, S)], total=100, minutes=60)
        assert summary.severe_miles == pytest.approx(75)

    def test_all_low_route(self):
        summary = route([(0, L), (25, L), (50, L)], total=50, minutes=45)
        assert summary.avg_risk == 0
        assert summary.severe_miles == summary.high_miles == summary.no_travel_miles == 0

    def test_zero_length_trip_does_not_divide_by_zero(self):
        summary = route([(0, M)], total=0, minutes=0)
        assert summary.avg_risk == 1

    def test_mismatched_inputs_are_rejected(self):
        with pytest.raises(ValueError):
            summarize_route([0, 25], [L], 25, 30)
        with pytest.raises(ValueError):
            summarize_route([], [], 0, 0)


class TestRankingFollowsTheBrief:
    """Fewest Severe miles, then fewest High miles, then lowest average risk, then shortest time."""

    def test_fewest_severe_miles_beats_a_faster_route(self):
        fast_but_severe = route([(0, L), (50, S), (100, L)], total=100, minutes=90)
        slow_but_safe = route([(0, L), (50, H), (100, L)], total=100, minutes=150)
        assert rank_routes([fast_but_severe, slow_but_safe]) == [1, 0]

    def test_severe_miles_are_compared_before_high_miles(self):
        # one Severe mile loses to forty High miles, because Severe is looked at first
        a_little_severe = exposed(1000, 100, severe=1)
        a_lot_of_high = exposed(1000, 200, high=40)
        assert rank_routes([a_little_severe, a_lot_of_high]) == [1, 0]

    def test_high_miles_break_a_severe_tie(self):
        a = route([(0, L), (50, H), (100, L)], total=100, minutes=100)
        b = route([(0, L), (50, M), (100, L)], total=100, minutes=140)
        assert rank_routes([a, b]) == [1, 0]

    def test_average_risk_breaks_a_tie_on_severe_and_high_miles(self):
        a = route([(0, M), (50, M), (100, M)], total=100, minutes=100)
        b = route([(0, L), (50, L), (100, L)], total=100, minutes=140)
        assert rank_routes([a, b]) == [1, 0]

    def test_travel_time_decides_when_the_weather_is_the_same(self):
        slow = route([(0, M), (100, M)], total=100, minutes=200)
        fast = route([(0, M), (100, M)], total=100, minutes=150)
        assert rank_routes([slow, fast]) == [1, 0]

    def test_no_travel_miles_count_as_severe_miles(self):
        # a route you can't drive must not beat one with only a little Severe weather
        blocked = exposed(1000, 100, no_travel=30)
        a_little_severe = exposed(1000, 400, severe=5)
        assert rank_routes([blocked, a_little_severe]) == [1, 0]

    def test_no_travel_and_severe_miles_are_added_together(self):
        mixed = exposed(1000, 100, severe=10, no_travel=10)  # 20 miles of Severe or worse
        only_severe = exposed(1000, 400, severe=15)
        assert rank_routes([mixed, only_severe]) == [1, 0]

    def test_no_travel_miles_count_exactly_like_severe_ones_and_are_not_a_step_of_their_own(self):
        # the order taken at its word: fewer Severe-or-worse miles wins, so 10 miles of
        # No Travel beats 15 miles of Severe. Not weighted more heavily, and not checked first.
        ten_no_travel = exposed(1000, 400, no_travel=10)
        fifteen_severe = exposed(1000, 100, severe=15)
        assert rank_routes([fifteen_severe, ten_no_travel]) == [1, 0]
        assert rank_routes([ten_no_travel, fifteen_severe]) == [0, 1]

    def test_with_the_same_severe_or_worse_miles_the_later_steps_decide(self):
        blocked = exposed(1000, 100, no_travel=20)
        severe = exposed(1000, 400, severe=20)
        # same miles, but No Travel pushes the average risk up, so the Severe route is better
        assert rank_routes([blocked, severe]) == [1, 0]

    def test_equal_routes_keep_their_original_order(self):
        a = route([(0, L), (100, L)], total=100, minutes=90)
        b = route([(0, L), (100, L)], total=100, minutes=90)
        assert rank_routes([a, b]) == [0, 1]

    def test_every_route_gets_a_place_from_cleanest_to_worst(self):
        # the worse the weather, the faster the route, so only the weather can explain the order
        clean = haul(200, 180)
        high = haul(200, 170, m100=H)
        severe = haul(200, 160, m100=S)
        no_travel = haul(200, 150, m100=N)

        assert rank_routes([clean, high, severe, no_travel]) == [0, 1, 2, 3]
        assert rank_routes([no_travel, severe, high, clean]) == [3, 2, 1, 0]


class TestNothingIsForgiven:
    """Weather always outranks time, however small the weather and however big the time saving."""

    def test_a_single_high_checkpoint_loses_to_a_clean_route_hours_slower(self):
        quick_with_a_shower = haul(1400, 1500, m700=H)  # 25 miles out of 1,400
        slow_and_clean = haul(1400, 1900)
        assert rank_routes([quick_with_a_shower, slow_and_clean]) == [1, 0]
        assert rank_routes([slow_and_clean, quick_with_a_shower]) == [0, 1]

    def test_a_single_mile_of_severe_weather_loses_to_ten_hours(self):
        assert rank_routes([exposed(1400, 1000, severe=1), exposed(1400, 1600)]) == [1, 0]

    def test_a_sliver_of_moderate_weather_still_counts_through_average_risk(self):
        assert rank_routes([exposed(1400, 1000, moderate=10), exposed(1400, 1600)]) == [1, 0]

    def test_the_real_los_angeles_to_dallas_case(self):
        # numbers from a live run: two near-identical routes, one with a single High checkpoint,
        # and a long clean detour. By the brief the clean detour beats the one with the rain.
        direct = haul(1438, 1494)
        direct_with_rain = haul(1434, 1500, m500=H)
        long_detour = haul(1628, 1884)
        assert rank_routes([direct, direct_with_rain, long_detour]) == [0, 2, 1]

    def test_only_floating_point_noise_is_ignored(self):
        # a very long route, so the average risk is identical and only the Severe miles can decide
        base = exposed(100_000, 1500, severe=10.0)
        noise = exposed(100_000, 1300, severe=10.004)  # a hundredth of a mile is rounding error
        real = exposed(100_000, 1300, severe=10.1)  # a tenth of a mile is real
        assert round(base.avg_risk, 3) == round(real.avg_risk, 3)

        assert rank_routes([base, noise]) == [1, 0]  # a tie on Severe miles, so the quicker one wins
        assert rank_routes([real, base]) == [1, 0]  # just as quick, but it has more Severe miles

    def test_high_miles_get_the_same_treatment(self):
        base = exposed(100_000, 1500, high=10.0)
        noise = exposed(100_000, 1300, high=10.004)
        real = exposed(100_000, 1300, high=10.1)
        assert round(base.avg_risk, 3) == round(real.avg_risk, 3)

        assert rank_routes([base, noise]) == [1, 0]
        assert rank_routes([real, base]) == [1, 0]


class TestReason:
    def test_mentions_avoided_severe_miles_and_time_cost(self):
        safe = route([(0, L), (50, H), (100, L)], total=100, minutes=150)
        risky = route([(0, L), (50, S), (100, L)], total=100, minutes=90)
        reason = recommendation_reason(safe, risky)
        assert "50 miles of severe" in reason
        assert "60 min longer" in reason

    def test_faster_route_with_the_same_weather(self):
        fast = route([(0, M), (100, M)], total=100, minutes=100)
        slow = route([(0, M), (100, M)], total=100, minutes=130)
        assert "30 min faster" in recommendation_reason(fast, slow)

    def test_a_small_difference_is_named_along_with_what_it_costs(self):
        reason = recommendation_reason(haul(1400, 1900), haul(1400, 1500, m700=H))
        assert reason == "Avoids 25 miles of high-risk weather compared with the next best route (400 min longer)."

    def test_less_than_a_mile_is_shown_with_a_decimal(self):
        reason = recommendation_reason(exposed(1000, 100), exposed(1000, 100, severe=0.4))
        assert "Avoids 0.4 miles of severe" in reason

    def test_lowest_average_risk_is_reported_when_that_decides_it(self):
        mild = route([(0, L), (100, L)], total=100, minutes=140)
        moderate = route([(0, M), (100, M)], total=100, minutes=100)
        assert "Lowest average weather risk" in recommendation_reason(mild, moderate)

    def test_identical_routes(self):
        a = route([(0, L), (100, L)], total=100, minutes=100)
        assert recommendation_reason(a, a).startswith("Same weather exposure and travel time")

    def test_single_route(self):
        only = route([(0, L), (100, L)], total=100, minutes=100)
        assert "Only one route" in recommendation_reason(only, None)
