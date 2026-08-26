"""The numbers in the dossier.

Pure standard library on purpose: this same code runs inside the Daytona
sandbox, where nothing is installed unless the agent installs it.

Nothing here estimates. Every figure is computed from rows the agent pulled out
of Postgres, which is the whole point - a model that guesses a stockout date is
worse than useless, because it is confidently wrong in a way nobody can check.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field
from typing import Any, Sequence

# 90th percentile of the standard normal, which puts the solved edges at the
# 10th and 90th percentiles - matching what the fields are called. Using the
# 80th-percentile value here would name a p20 edge "p10" and hand adjudication a
# deadline less conservative than advertised.
_Z90 = 1.2815515655446004


@dataclass(frozen=True)
class DrawRate:
    """How fast the works actually consumes this part."""

    mean_daily: float
    stdev_daily: float
    days_observed: int
    spike_days: list[str] = field(default_factory=list)
    despiked_mean_daily: float = 0.0

    @property
    def had_spike(self) -> bool:
        return bool(self.spike_days)


@dataclass(frozen=True)
class LeadTime:
    p50: float
    p80: float
    worst: float
    promised: float
    orders_observed: int

    @property
    def runs_late(self) -> bool:
        """Does this vendor habitually miss its own promise?"""
        return self.p50 > self.promised


@dataclass(frozen=True)
class Stockout:
    days_p50: float
    # p10 is the pessimistic tail: draw runs hot, stock goes sooner.
    days_p10: float
    days_p90: float


def percentile(values: Sequence[float], fraction: float) -> float:
    """Empirical percentile with linear interpolation.

    statistics.quantiles needs at least two points and returns fixed cut points;
    this handles the single-observation case a new vendor would give us.
    """
    if not values:
        raise ValueError("percentile of no observations")
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("fraction must be between 0 and 1")
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = fraction * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return float(ordered[low])
    return float(ordered[low] + (ordered[high] - ordered[low]) * (position - low))


def _as_date(value: Any) -> date:
    return value if isinstance(value, date) else datetime.fromisoformat(str(value)).date()


def _daily_totals(
    rows: Sequence[dict[str, Any]],
    window_start: date | None = None,
    window_end: date | None = None,
) -> list[tuple[str, float]]:
    """Collapse issue events into one total per calendar day, gaps included.

    A row is an issue event, not a day: the schema allows several issues against
    one date, and a day with no issues has no row at all. Treating rows as days
    would divide by the wrong denominator in both directions - double-counting
    busy days and dropping quiet ones - which moves the mean, the variance, the
    spike threshold and every stockout date downstream.

    The window matters at the edges too. The query asks for a rolling history but
    returns only the days something moved, so a part that has sat untouched for
    three weeks has three weeks of zero-draw days missing from the end. Inferring
    the window from the first and last event drops exactly the quiet stretches
    that should pull the mean down, which makes stock look like it is going
    faster than it is. Pass the real bounds when you know them.
    """
    totals: dict[date, float] = {}
    for row in rows:
        day = _as_date(row["consumed_on"])
        totals[day] = totals.get(day, 0.0) + float(row["qty"])

    first = window_start or min(totals)
    last = window_end or max(totals)
    if last < first:
        raise ValueError("observation window ends before it starts")
    return [
        ((first + timedelta(days=i)).isoformat(), totals.get(first + timedelta(days=i), 0.0))
        for i in range((last - first).days + 1)
    ]


def fit_draw_rate(
    rows: Sequence[dict[str, Any]],
    spike_sigma: float = 3.0,
    *,
    window_start: date | str | None = None,
    window_end: date | str | None = None,
) -> DrawRate:
    """Fit a daily consumption rate, and notice one-off bursts separately.

    A single overhaul can drag the mean up enough to trip a reorder level that
    the steady state would never trip. Reporting both rates is what lets the
    consumption_spike hypothesis be tested rather than asserted.

    Pass the observation window the rows were queried over. Without it the
    quiet days at either edge are invisible and the draw rate reads high.
    """
    if not rows:
        raise ValueError("no consumption rows to fit")

    daily = _daily_totals(
        rows,
        _as_date(window_start) if window_start else None,
        _as_date(window_end) if window_end else None,
    )
    quantities = [qty for _, qty in daily]
    n = len(quantities)
    mean = sum(quantities) / n
    variance = sum((q - mean) ** 2 for q in quantities) / n
    stdev = math.sqrt(variance)

    threshold = mean + spike_sigma * stdev
    spike_days = [day for day, qty in daily if qty > threshold]
    ordinary = [q for q in quantities if q <= threshold]
    despiked = sum(ordinary) / len(ordinary) if ordinary else mean

    return DrawRate(
        mean_daily=mean,
        stdev_daily=stdev,
        days_observed=n,
        spike_days=spike_days,
        despiked_mean_daily=despiked,
    )


def fit_lead_time(rows: Sequence[dict[str, Any]]) -> LeadTime:
    """Build a lead-time distribution from what the vendor actually did.

    The promised figure is what the vendor says. The percentiles are what
    happened. Ordering against the promise is how works run out of stock.
    """
    actuals = [float(r["actual_days"]) for r in rows if r.get("actual_days")]
    if not actuals:
        raise ValueError("no completed orders to fit a lead time from")
    promised = [float(r["promised_days"]) for r in rows if r.get("promised_days")]
    return LeadTime(
        p50=percentile(actuals, 0.50),
        p80=percentile(actuals, 0.80),
        worst=max(actuals),
        promised=percentile(promised, 0.50) if promised else 0.0,
        orders_observed=len(actuals),
    )


def project_stockout(stock_on_hand: int, draw: DrawRate) -> Stockout:
    """When does the bin run dry, and how wide is the uncertainty?

    Cumulative draw over t days has mean mean*t and standard deviation
    stdev*sqrt(t). Solving mean*t +/- z*stdev*sqrt(t) = stock for sqrt(t) gives
    the band, so the early edge accounts for the draw running hot rather than
    being a flat percentage haircut on the median.
    """
    if stock_on_hand < 0:
        raise ValueError("stock on hand cannot be negative")
    if draw.mean_daily <= 0:
        raise ValueError("cannot project a stockout with no consumption")

    def solve(z: float) -> float:
        # mean*x^2 + z*stdev*x - stock = 0, where x = sqrt(t), positive root.
        a, b, c = draw.mean_daily, z * draw.stdev_daily, -float(stock_on_hand)
        root = (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)
        return root * root

    return Stockout(
        days_p50=stock_on_hand / draw.mean_daily,
        days_p10=solve(_Z90),
        days_p90=solve(-_Z90),
    )


def summarise(
    *, part_no: str, stock_on_hand: int, draw: DrawRate, lead: LeadTime, stockout: Stockout
) -> dict[str, Any]:
    """The projection block the dossier and adjudicate both read.

    Keys match Projection in triage.py, so the agent passes this straight
    through without restating any number in its own words.
    """
    return {
        "part_no": part_no,
        "stock_on_hand": stock_on_hand,
        "mean_daily_draw": round(draw.mean_daily, 2),
        "days_to_stockout_p50": round(stockout.days_p50, 1),
        "days_to_stockout_p10": round(stockout.days_p10, 1),
        "lead_time_p50": round(lead.p50, 1),
        "lead_time_p80": round(lead.p80, 1),
        "_evidence": {
            "days_observed": draw.days_observed,
            "stdev_daily": round(draw.stdev_daily, 2),
            "spike_days": draw.spike_days,
            "despiked_mean_daily": round(draw.despiked_mean_daily, 2),
            "days_to_stockout_p90": round(stockout.days_p90, 1),
            "lead_time_worst": round(lead.worst, 1),
            "lead_time_promised": round(lead.promised, 1),
            "vendor_runs_late": lead.runs_late,
            "orders_observed": lead.orders_observed,
        },
    }
