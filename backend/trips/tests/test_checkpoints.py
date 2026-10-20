from datetime import datetime, timedelta, timezone

import pytest

from trips.services.checkpoints import build_checkpoints

from .factories import simple_route

DEPARTURE = datetime(2026, 11, 3, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def hundred_miles():
    # four 25 mile segments, the second and fourth are slow
    return simple_route([25, 25, 25, 25], [1800, 3600, 1800, 3600])


def test_checkpoints_every_interval_with_etas(hundred_miles):
    points = build_checkpoints(hundred_miles, DEPARTURE, 25)
    assert [p.mile for p in points] == [0, 25, 50, 75, 100]
    assert [p.eta - DEPARTURE for p in points] == [
        timedelta(0),
        timedelta(minutes=30),
        timedelta(minutes=90),
        timedelta(minutes=120),
        timedelta(minutes=180),
    ]


def test_first_is_the_origin_and_last_is_the_destination(hundred_miles):
    points = build_checkpoints(hundred_miles, DEPARTURE, 10)
    assert (points[0].lon, points[0].lat) == (0.0, 0.0)
    assert points[-1].mile == pytest.approx(100)
    assert (points[-1].lon, points[-1].lat) == pytest.approx((4.0, 0.0))


def test_destination_is_added_when_the_trip_is_not_a_multiple_of_the_interval(hundred_miles):
    points = build_checkpoints(hundred_miles, DEPARTURE, 30)
    assert [p.mile for p in points] == [0, 30, 60, 90, 100]


def test_exact_multiple_does_not_duplicate_the_destination(hundred_miles):
    points = build_checkpoints(hundred_miles, DEPARTURE, 50)
    assert [p.mile for p in points] == [0, 50, 100]


def test_trip_shorter_than_the_interval_has_just_the_two_ends():
    route = simple_route([8], [600])
    points = build_checkpoints(route, DEPARTURE, 25)
    assert [p.mile for p in points] == [0, 8]
    assert points[-1].eta - DEPARTURE == timedelta(seconds=600)


def test_position_and_time_are_interpolated_inside_a_segment(hundred_miles):
    # mile 10 is 40% into the first segment
    point = build_checkpoints(hundred_miles, DEPARTURE, 10)[1]
    assert point.lon == pytest.approx(0.4)
    assert point.eta - DEPARTURE == timedelta(seconds=720)

    # mile 40 is 60% into the second (slow) segment: 1800 + 0.6 * 3600
    point = build_checkpoints(hundred_miles, DEPARTURE, 40)[1]
    assert point.eta - DEPARTURE == timedelta(seconds=1800 + 2160)


def test_slow_stretches_push_later_checkpoints_back(hundred_miles):
    points = build_checkpoints(hundred_miles, DEPARTURE, 10)
    etas = [p.eta for p in points]
    assert etas == sorted(etas)
    assert len(set(etas)) == len(etas)


def test_etas_keep_the_timezone_of_the_departure(hundred_miles):
    assert build_checkpoints(hundred_miles, DEPARTURE, 25)[-1].eta.tzinfo == timezone.utc


def test_zero_length_segments_are_survivable():
    route = simple_route([10, 0, 10], [600, 0, 600])
    points = build_checkpoints(route, DEPARTURE, 5)
    assert [p.mile for p in points] == [0, 5, 10, 15, 20]
    assert points[-1].eta - DEPARTURE == timedelta(seconds=1200)


@pytest.mark.parametrize("interval", [0, -5])
def test_rejects_a_non_positive_interval(hundred_miles, interval):
    with pytest.raises(ValueError):
        build_checkpoints(hundred_miles, DEPARTURE, interval)
