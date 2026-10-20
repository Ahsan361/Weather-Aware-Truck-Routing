from bisect import bisect_right
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .checkpoints import Checkpoint, build_checkpoints
from .geo import Point, simplify
from .recommend import (
    RouteSummary,
    checkpoint_spans,
    rank_routes,
    recommendation_reason,
    summarize_route,
)
from .risk import RiskAssessment, RiskLevel, Weather, assess
from .routing import Route, find_routes
from .weather import HourlyForecast, OutsideForecast, fetch_forecasts, last_forecast_hour

HEATMAP_HOURS = 48
GEOMETRY_TOLERANCE_MILES = 0.02  # about 30 metres, invisible at normal map zoom


@dataclass(frozen=True)
class TripRequest:
    origin: Point  # (lon, lat)
    destination: Point
    departure: datetime  # timezone-aware, UTC
    load_lb: float
    interval_miles: float


@dataclass(frozen=True)
class _RouteResult:
    route: Route
    checkpoints: list[Checkpoint]
    weather: list[Weather]
    assessments: list[RiskAssessment]
    summary: RouteSummary


def analyze_trip(request: TripRequest, now: datetime | None = None) -> dict:
    routes = find_routes(request.origin, request.destination)
    checkpoint_sets = [build_checkpoints(r, request.departure, request.interval_miles) for r in routes]

    horizon = last_forecast_hour(now)
    latest_arrival = max(cps[-1].eta for cps in checkpoint_sets)
    if latest_arrival > horizon:
        raise OutsideForecast(
            f"this trip would end after {horizon:%d %b}, which is past the end of the weather forecast"
        )

    departure_hour = request.departure.replace(minute=0, second=0, microsecond=0)
    heatmap_end = min(departure_hour + timedelta(hours=HEATMAP_HOURS), horizon)
    # rain and snow are looked up in the hour after arrival, so round the end of the window up
    forecast_end = _round_up_to_hour(max(latest_arrival, heatmap_end))

    all_checkpoints = [cp for cps in checkpoint_sets for cp in cps]
    forecasts = fetch_forecasts([(cp.lon, cp.lat) for cp in all_checkpoints], departure_hour, forecast_end)

    results = []
    start = 0
    for route, checkpoints in zip(routes, checkpoint_sets):
        route_forecasts = forecasts[start : start + len(checkpoints)]
        start += len(checkpoints)
        weather = [forecast.at(cp.eta) for forecast, cp in zip(route_forecasts, checkpoints)]
        assessments = [assess(w, request.load_lb) for w in weather]
        summary = summarize_route(
            [cp.mile for cp in checkpoints],
            [a.level for a in assessments],
            route.total_miles,
            route.total_seconds / 60,
        )
        results.append(_RouteResult(route, checkpoints, weather, assessments, summary))

    order = rank_routes([r.summary for r in results])
    best = results[order[0]].summary
    runner_up = results[order[1]].summary if len(order) > 1 else None

    return {
        "departure": _iso(request.departure),
        "load_lb": request.load_lb,
        "interval_miles": request.interval_miles,
        "risk_levels": [{"value": int(level), "label": level.label} for level in RiskLevel],
        "recommendation": {
            "route_id": order[0],
            "reason": recommendation_reason(best, runner_up),
        },
        "routes": [
            _route_payload(i, result, rank=order.index(i) + 1, recommended=(i == order[0]))
            for i, result in enumerate(results)
        ],
        "heatmap": _heatmap_payload(all_checkpoints, forecasts, departure_hour, heatmap_end, request.load_lb),
    }


def _route_payload(route_id: int, result: _RouteResult, rank: int, recommended: bool) -> dict:
    route, checkpoints = result.route, result.checkpoints
    summary = result.summary
    levels = [a.level for a in result.assessments]

    return {
        "id": route_id,
        "rank": rank,
        "recommended": recommended,
        "distance_miles": round(route.total_miles, 1),
        "duration_minutes": round(route.total_seconds / 60),
        "arrival": _iso(checkpoints[-1].eta),
        "summary": {
            "miles_by_level": [round(summary.miles_by_level[level], 1) for level in RiskLevel],
            "avg_risk": round(summary.avg_risk, 2),
            "worst_level": int(max(levels)),
        },
        "segments": _risk_segments(route, [cp.mile for cp in checkpoints], levels),
        "checkpoints": [
            _checkpoint_payload(cp, w, a) for cp, w, a in zip(checkpoints, result.weather, result.assessments)
        ],
    }


def _checkpoint_payload(checkpoint: Checkpoint, weather: Weather, assessment: RiskAssessment) -> dict:
    return {
        "mile": round(checkpoint.mile, 1),
        "lat": round(checkpoint.lat, 5),
        "lon": round(checkpoint.lon, 5),
        "eta": _iso(checkpoint.eta),
        "weather": {
            "wind_mph": round(weather.wind_mph, 1),
            "rain_in_hr": round(weather.rain_in_hr, 3),
            "snow_in_hr": round(weather.snow_in_hr, 3),
        },
        "risk": {
            "level": int(assessment.level),
            "factor": assessment.main_factor,
            "wind": int(assessment.wind),
            "rain": int(assessment.rain),
            "snow": int(assessment.snow),
        },
    }


def _risk_segments(route: Route, checkpoint_miles: list[float], levels: list[RiskLevel]) -> list[dict]:
    edges = [0.0]
    for span in checkpoint_spans(checkpoint_miles, route.total_miles):
        edges.append(edges[-1] + span)

    pieces: list[list] = []  # [level, from_mile, to_mile]
    for level, start, end in zip(levels, edges, edges[1:]):
        if pieces and pieces[-1][0] == level:
            pieces[-1][2] = end
        else:
            pieces.append([level, start, end])

    last_vertex = len(route.coordinates) - 1

    def vertex_at(mile: float) -> int:
        return min(max(bisect_right(route.cumulative_miles, mile) - 1, 0), last_vertex)

    segments = []
    for level, start, end in pieces:
        first = vertex_at(start)
        last = max(vertex_at(end), min(first + 1, last_vertex))
        coords = simplify(route.coordinates[first : last + 1], GEOMETRY_TOLERANCE_MILES)
        if len(coords) >= 2:
            segments.append(
                {"level": int(level), "coordinates": [[round(lon, 5), round(lat, 5)] for lon, lat in coords]}
            )
    return segments


def _heatmap_payload( checkpoints: list[Checkpoint], forecasts: list[HourlyForecast], first_hour: datetime, last_hour: datetime, load_lb: float,) -> dict:
    hours = int((last_hour - first_hour).total_seconds() // 3600)
    points = []
    for checkpoint, forecast in zip(checkpoints, forecasts):
        base = round(forecast.index_of(first_hour))
        levels = [int(assess(forecast.at_hour(base + h), load_lb).level) for h in range(hours + 1)]
        points.append({"lat": round(checkpoint.lat, 4), "lon": round(checkpoint.lon, 4), "levels": levels})
    return {"start": _iso(first_hour), "hours": hours, "points": points}


def _round_up_to_hour(moment: datetime) -> datetime:
    floored = moment.replace(minute=0, second=0, microsecond=0)
    return floored if floored == moment else floored + timedelta(hours=1)


def _iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
