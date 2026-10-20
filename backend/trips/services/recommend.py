from collections.abc import Sequence
from dataclasses import dataclass

from .risk import RiskLevel


@dataclass(frozen=True)
class RouteSummary:
    total_miles: float
    duration_minutes: float
    miles_by_level: dict[RiskLevel, float]
    avg_risk: float  # 0 (Low) to 4 (No Travel), weighted by miles

    @property
    def no_travel_miles(self) -> float:
        return self.miles_by_level[RiskLevel.NO_TRAVEL]

    @property
    def severe_or_worse_miles(self) -> float:
        # No Travel is the far end of the same scale, so its miles count as Severe ones
        return self.severe_miles + self.no_travel_miles

    @property
    def severe_miles(self) -> float:
        return self.miles_by_level[RiskLevel.SEVERE]

    @property
    def high_miles(self) -> float:
        return self.miles_by_level[RiskLevel.HIGH]


def checkpoint_spans(checkpoint_miles: Sequence[float], total_miles: float) -> list[float]:
    edges = [0.0]
    for before, after in zip(checkpoint_miles, checkpoint_miles[1:]):
        edges.append((before + after) / 2)
    edges.append(total_miles)
    return [max(end - start, 0.0) for start, end in zip(edges, edges[1:])]




def summarize_route( checkpoint_miles: Sequence[float], levels: Sequence[RiskLevel], total_miles: float, duration_minutes: float,) -> RouteSummary:
    if not checkpoint_miles or len(checkpoint_miles) != len(levels):
        raise ValueError("need one risk level per checkpoint, and at least one checkpoint")

    spans = checkpoint_spans(checkpoint_miles, total_miles)
    miles_by_level = {level: 0.0 for level in RiskLevel}
    for span, level in zip(spans, levels):
        miles_by_level[level] += span

    covered = sum(spans)
    if covered > 0:
        avg_risk = sum(span * level for span, level in zip(spans, levels)) / covered
    else:  # zero-length trip, fall back to a plain average
        avg_risk = sum(levels) / len(levels)

    return RouteSummary(total_miles, duration_minutes, miles_by_level, avg_risk)




# Sort by fewer Severe-or-worse miles, then fewer High miles, then lower average risk, then shorter duration.
def ranking_key(summary: RouteSummary) -> tuple:
    return (
        round(summary.severe_or_worse_miles, 2),
        round(summary.high_miles, 2),
        round(summary.avg_risk, 3),
        summary.duration_minutes,
    )



# Assigning Indexes to the routes based on their ranking. The best route gets index 0, the next best gets index 1, and so on.
def rank_routes(summaries: Sequence[RouteSummary]) -> list[int]:
    return sorted(range(len(summaries)), key=lambda i: (ranking_key(summaries[i]), i))


def _miles(amount: float) -> str:
    return f"{amount:.0f}" if amount >= 1 else f"{amount:.1f}"



# Reason for the recommendation, based on the best route and the next best route.
def recommendation_reason(best: RouteSummary, runner_up: RouteSummary | None) -> str:
    if runner_up is None: # if there is no runner up, then the best route is the only one.
        return "Only one route was available."

    extra_minutes = round(best.duration_minutes - runner_up.duration_minutes)
    cost = f" ({extra_minutes} min longer)" if extra_minutes > 0 else ""

    checks = (
        ("severe", best.severe_or_worse_miles, runner_up.severe_or_worse_miles),
        ("high-risk", best.high_miles, runner_up.high_miles),
    )
    for name, mine, theirs in checks:
        if round(mine, 2) < round(theirs, 2):
            return f"Avoids {_miles(theirs - mine)} miles of {name} weather compared with the next best route{cost}."

    if round(best.avg_risk, 3) < round(runner_up.avg_risk, 3):
        return f"Lowest average weather risk of the options{cost}."
    if extra_minutes < 0:
        return f"Same weather exposure as the next best route, but {-extra_minutes} min faster."
    return "Same weather exposure and travel time as the next best route."