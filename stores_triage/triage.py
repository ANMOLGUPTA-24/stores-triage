"""Adjudication: turn four hypothesis verdicts into one recommendation.

This is deliberately ordinary code, not a model call. The whole claim of the
project is that "do nothing" is a *defensible* answer, and that is only true if
the reasoning is inspectable and testable. Every rule below states why it fired.

The four hypotheses are all explanations for why a shortage might be on paper
only. Ruling all four out is what makes a shortage genuine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

HYPOTHESES = ("consumption_spike", "inbound_delay", "duplicate_indent", "bom_change")

VerdictValue = Literal["positive", "negative", "inconclusive"]


@dataclass(frozen=True)
class Verdict:
    """What one hypothesis subagent came back with."""

    hypothesis: str
    verdict: VerdictValue
    evidence: dict[str, Any] = field(default_factory=dict)
    note: str = ""

    def __post_init__(self) -> None:
        if self.hypothesis not in HYPOTHESES:
            raise ValueError(f"unknown hypothesis: {self.hypothesis}")
        if self.verdict not in ("positive", "negative", "inconclusive"):
            raise ValueError(f"unknown verdict: {self.verdict}")


@dataclass(frozen=True)
class Projection:
    """Numbers from the sandbox. Never from the model."""

    mean_daily_draw: float
    days_to_stockout_p50: float
    # p10 is the pessimistic tail: draw runs hot, stock goes sooner.
    days_to_stockout_p10: float
    lead_time_p50: float
    lead_time_p80: float


@dataclass(frozen=True)
class Recommendation:
    action: Literal["raise_indent", "no_action"]
    reason: str
    what_would_change_my_mind: str
    ruled_out: list[str]
    urgency: str | None = None
    indent_qty: int | None = None


@dataclass(frozen=True)
class _Miss:
    """A rule that almost fired, and the fact that would have made it fire.

    The counterfactual in every dossier comes from here rather than from the
    model, which is why it is always specific and always checkable.
    """

    strength: int
    counterfactual: str


def _by_hypothesis(verdicts: list[Verdict]) -> dict[str, Verdict]:
    seen = {v.hypothesis: v for v in verdicts}
    missing = [h for h in HYPOTHESES if h not in seen]
    if missing:
        raise ValueError(f"no verdict returned for: {', '.join(missing)}")
    return seen


def _lands_in_time(eta: date | None, today: date, deadline_days: float) -> bool:
    if eta is None:
        return False
    return (eta - today).days <= deadline_days


def adjudicate(
    *,
    part_no: str,
    stock_on_hand: int,
    reorder_qty: int,
    projection: Projection,
    verdicts: list[Verdict],
    today: date,
) -> Recommendation:
    """Decide, and say why. Rules are ordered; the first to fire wins."""
    by_hyp = _by_hypothesis(verdicts)
    misses: list[_Miss] = []
    # The window we must be covered within before stock actually runs out.
    horizon = projection.days_to_stockout_p10

    # -- Rule 1: someone already raised this indent, and stock is moving. ----
    dup = by_hyp["duplicate_indent"]
    if dup.verdict == "positive":
        indent_no = dup.evidence.get("indent_no")
        linked = dup.evidence.get("linked_consignment") or {}
        eta = linked.get("eta")
        if linked.get("status") == "in_transit" and _lands_in_time(eta, today, horizon):
            return Recommendation(
                action="no_action",
                reason=(
                    f"{part_no} is already on order. Indent {indent_no} is open and "
                    f"consignment {linked.get('consignment_no')} "
                    f"({linked.get('qty')} nos) is in transit, due {eta}, which is "
                    f"inside the {horizon:.0f}-day stockout window. Raising another "
                    f"indent would duplicate stock the works has already bought."
                ),
                what_would_change_my_mind=(
                    f"If consignment {linked.get('consignment_no')} slips past {eta} "
                    f"or is short-shipped, this becomes a genuine shortage."
                ),
                ruled_out=_ruled_out(by_hyp, keep="duplicate_indent"),
            )
        if indent_no:
            misses.append(
                _Miss(
                    strength=3,
                    counterfactual=(
                        f"Indent {indent_no} is open but nothing confirmed is moving "
                        f"against it. If a consignment is booked against it and lands "
                        f"within {horizon:.0f} days, do not raise this."
                    ),
                )
            )

    # -- Rule 2: stock is inbound, just not booked in yet. -------------------
    inbound = by_hyp["inbound_delay"]
    if inbound.verdict == "positive":
        shortfall = max(0, reorder_qty)
        for c in inbound.evidence.get("consignments", []):
            covers = (c.get("qty") or 0) >= shortfall
            in_time = _lands_in_time(c.get("eta"), today, horizon)
            if c.get("status") == "in_transit" and covers and in_time:
                return Recommendation(
                    action="no_action",
                    reason=(
                        f"Consignment {c.get('consignment_no')} ({c.get('qty')} nos) is "
                        f"confirmed in transit and due {c.get('eta')}, before {part_no} "
                        f"runs out. The shortage is on paper only."
                    ),
                    what_would_change_my_mind=(
                        f"If {c.get('consignment_no')} is delayed past "
                        f"{c.get('eta')}, reopen this."
                    ),
                    ruled_out=_ruled_out(by_hyp, keep="inbound_delay"),
                )
            if c.get("status") == "unconfirmed" and covers and in_time:
                # The Run A case: cover exists on paper but nobody has confirmed
                # it left the vendor, so it cannot be counted as cover.
                misses.append(
                    _Miss(
                        strength=5,
                        counterfactual=(
                            f"Consignment {c.get('consignment_no')} ({c.get('qty')} nos) "
                            f"is shown against {part_no} with an ETA of {c.get('eta')}, "
                            f"but the vendor has not confirmed dispatch. If that "
                            f"consignment is confirmed and lands by {c.get('eta')}, "
                            f"do not raise this indent."
                        ),
                    )
                )

    # -- Rule 3: the trigger was a one-off burst, not the steady state. ------
    spike = by_hyp["consumption_spike"]
    if spike.verdict == "positive":
        despiked = spike.evidence.get("despiked_daily_draw")
        if despiked and despiked > 0:
            despiked_days = stock_on_hand / despiked
            if despiked_days > projection.lead_time_p80:
                return Recommendation(
                    action="no_action",
                    reason=(
                        f"The drawdown on {part_no} was a one-off "
                        f"({spike.note or 'burst in the consumption log'}). At the "
                        f"underlying rate of {despiked:.2f}/day the stock lasts "
                        f"{despiked_days:.0f} days, longer than the "
                        f"{projection.lead_time_p80:.0f}-day lead time. The reorder "
                        f"trigger is misleading."
                    ),
                    what_would_change_my_mind=(
                        "If the elevated draw continues past this week, the "
                        "underlying rate is wrong and this becomes genuine."
                    ),
                    ruled_out=_ruled_out(by_hyp, keep="consumption_spike"),
                )
            misses.append(
                _Miss(
                    strength=2,
                    counterfactual=(
                        f"Even excluding the spike, {part_no} lasts only "
                        f"{despiked_days:.0f} days against a "
                        f"{projection.lead_time_p80:.0f}-day lead time, so the burst "
                        f"is not the explanation."
                    ),
                )
            )

    # -- Rule 4: the part is on its way out of the BOM. ---------------------
    bom = by_hyp["bom_change"]
    if bom.verdict == "positive":
        superseded_by = bom.evidence.get("superseded_by")
        return Recommendation(
            action="no_action",
            reason=(
                f"{part_no} appears superseded"
                + (f" by {superseded_by}" if superseded_by else "")
                + ". Raising an indent would buy stock the works is moving away "
                "from. Refer to engineering before ordering."
            ),
            what_would_change_my_mind=(
                "If engineering confirms the old part is still fitted to running "
                "stock, treat this as a genuine shortage."
            ),
            ruled_out=_ruled_out(by_hyp, keep="bom_change"),
        )

    # -- Nothing explains it away. This is a real shortage. ------------------
    urgency = (
        "critical"
        if projection.days_to_stockout_p10 < projection.lead_time_p80
        else "normal"
    )
    if misses:
        what_would_change = max(misses, key=lambda m: m.strength).counterfactual
    else:
        what_would_change = (
            f"If confirmed inbound stock for {part_no} appears within "
            f"{horizon:.0f} days, or an open indent is found against it, "
            f"do not raise this indent."
        )
    return Recommendation(
        action="raise_indent",
        reason=(
            f"No benign explanation survives. {part_no} draws "
            f"{projection.mean_daily_draw:.2f}/day and runs out in about "
            f"{projection.days_to_stockout_p50:.0f} days "
            f"({projection.days_to_stockout_p10:.0f} at the fast end), against a "
            f"vendor lead time of {projection.lead_time_p80:.0f} days at the 80th "
            f"percentile. Nothing confirmed is inbound and no indent is open."
        ),
        what_would_change_my_mind=what_would_change,
        ruled_out=_ruled_out(by_hyp, keep=None),
        urgency=urgency,
        indent_qty=reorder_qty,
    )


def _ruled_out(by_hyp: dict[str, Verdict], keep: str | None) -> list[str]:
    """Hypotheses actively dismissed.

    Only "negative" counts. A subagent that came back inconclusive has not ruled
    anything out, and saying otherwise would overstate the evidence in the very
    place the operator is relying on it.
    """
    return [h for h in HYPOTHESES if h != keep and by_hyp[h].verdict == "negative"]
