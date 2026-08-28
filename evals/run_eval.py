"""Measure the adjudicator against labelled scenarios, and price the mistakes.

"Potential impact" is easy to assert and hard to believe. This runs the same
deterministic adjudication the agent calls, over cases whose right answer is
known by construction, and reports both kinds of error in the units the works
actually pays in:

- a WRONG RAISE buys stock that was already covered - reorder_qty units of
  working capital, plus whatever expedite premium the order carries;
- a MISSED SHORTAGE leaves the bin empty between the day it runs dry and the
  day the vendor delivers - days of exposure, which is when a locomotive stops.

No model is involved. That is the point: the decision is testable code, so its
error rate is a measured number rather than a claim.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from scenarios import Scenario, build  # noqa: E402
from stores_triage.triage import (  # noqa: E402
    Projection,
    Verdict,
    adjudicate,
    hydrate_dates,
)


def verdicts_for(s: Scenario) -> list[Verdict]:
    """The evidence a perfectly diligent set of subagents would return.

    Each subagent reports what it found, not what it concludes about the alert
    overall - that judgement is the adjudicator's, and is what we are measuring.
    """
    spike_positive = s.despiked_daily is not None
    return [
        Verdict(
            hypothesis="consumption_spike",
            verdict="positive" if spike_positive else "negative",
            evidence=hydrate_dates(
                {"despiked_daily_draw": s.despiked_daily} if spike_positive else {}
            ),
        ),
        Verdict(
            hypothesis="inbound_delay",
            verdict="positive" if s.consignments else "negative",
            evidence=hydrate_dates({"consignments": s.consignments}),
        ),
        Verdict(
            hypothesis="duplicate_indent",
            verdict="positive" if s.indent_no else "negative",
            evidence=hydrate_dates(
                {"indent_no": s.indent_no, "linked_consignment": s.linked_consignment}
                if s.indent_no
                else {}
            ),
        ),
        Verdict(
            hypothesis="bom_change",
            verdict="positive" if s.superseded_by else "negative",
            evidence=hydrate_dates({"superseded_by": s.superseded_by}),
        ),
    ]


def main() -> int:
    today = date.today()
    cases = build(today)

    wrong_raises: list[tuple[Scenario, str]] = []
    missed: list[tuple[Scenario, str]] = []
    correct = 0

    print(f"{len(cases)} labelled scenarios · adjudication only, no model\n")
    print(f"{'scenario':34} {'truth':9} {'decided':13} ok")
    print("-" * 72)

    for s in cases:
        proj = Projection(
            mean_daily_draw=s.mean_daily,
            days_to_stockout_p50=s.stock_on_hand / s.mean_daily,
            days_to_stockout_p10=(s.stock_on_hand / s.mean_daily) * 0.82,
            lead_time_p50=s.lead_p50,
            lead_time_p80=s.lead_p80,
        )
        rec = adjudicate(
            part_no=s.name,
            stock_on_hand=s.stock_on_hand,
            reorder_qty=s.reorder_qty,
            projection=proj,
            verdicts=verdicts_for(s),
            today=today,
        )
        expected = "raise_indent" if s.truth == "genuine" else "no_action"
        ok = rec.action == expected
        if ok:
            correct += 1
        elif s.truth == "paper":
            wrong_raises.append((s, rec.reason))
        else:
            missed.append((s, rec.reason))
        print(f"{s.name:34} {s.truth:9} {rec.action:13} {'ok' if ok else 'MISS'}")

    n = len(cases)
    print("-" * 72)
    print(f"\ncorrect: {correct}/{n}  ({100 * correct / n:.0f}%)")
    print(f"  wrong raises   (buys covered stock): {len(wrong_raises)}")
    print(f"  missed shortages (bin runs empty)  : {len(missed)}")

    # Price the mistakes in the works's own units, not invented currency.
    capital = sum(s.reorder_qty for s, _ in wrong_raises)
    exposure = sum(max(0.0, s.lead_p80 - s.days_to_stockout) for s, _ in missed)
    print("\nconsequence of the errors above")
    print(f"  working capital committed against stock already covered : {capital} units")
    print(f"  days with an empty bin before the vendor delivers        : {exposure:.0f}")

    if wrong_raises or missed:
        print("\nfailures in detail")
        for s, why in wrong_raises:
            print(f"  WRONG RAISE  {s.name}\n    should be paper: {s.why}\n    said: {why[:150]}")
        for s, why in missed:
            print(f"  MISSED       {s.name}\n    should be genuine: {s.why}\n    said: {why[:150]}")

    # The paper cases are the ones worth money and the ones an officer gets
    # wrong, so report them separately rather than hiding them in an average.
    papers = [s for s in cases if s.truth == "paper"]
    caught = len(papers) - len(wrong_raises)
    print(f"\npaper alerts correctly refused: {caught}/{len(papers)}")
    print(f"avoided per 20-alert day at this mix: "
          f"{20 * caught / n:.1f} indents not raised")

    return 0 if not (wrong_raises or missed) else 1




# ---------------------------------------------------------------------------
# Does this evaluation have teeth?
# ---------------------------------------------------------------------------
#
# A perfect score on cases the author wrote is worth nothing on its own - the
# scenarios could simply describe whatever the code already does. So break the
# rules on purpose, one at a time, and check the suite notices. A mutation that
# survives is a case the set is missing, not a rule that does not matter.

import stores_triage.triage as triage_module  # noqa: E402


def _score(cases: list[Scenario], today: date) -> int:
    wrong = 0
    for s in cases:
        proj = Projection(
            mean_daily_draw=s.mean_daily,
            days_to_stockout_p50=s.stock_on_hand / s.mean_daily,
            days_to_stockout_p10=(s.stock_on_hand / s.mean_daily) * 0.82,
            lead_time_p50=s.lead_p50,
            lead_time_p80=s.lead_p80,
        )
        rec = adjudicate(
            part_no=s.name, stock_on_hand=s.stock_on_hand, reorder_qty=s.reorder_qty,
            projection=proj, verdicts=verdicts_for(s), today=today,
        )
        if rec.action != ("raise_indent" if s.truth == "genuine" else "no_action"):
            wrong += 1
    return wrong


def mutations() -> int:
    today = date.today()
    cases = build(today)
    original = triage_module._lands_in_time

    def accepts_overdue(eta, today_, deadline):
        # The bug we actually shipped and fixed: an ETA in the past counted as cover.
        return eta is not None and (eta - today_).days <= deadline

    def accepts_anything(eta, today_, deadline):
        # Any ETA at all is cover, however far away.
        return eta is not None

    checks = [
        ("overdue consignments count as cover", accepts_overdue),
        ("any ETA counts as cover, however late", accepts_anything),
    ]

    print("\nmutation checks — each should be caught\n")
    survived = 0
    for name, fn in checks:
        triage_module._lands_in_time = fn
        try:
            wrong = _score(cases, today)
        finally:
            triage_module._lands_in_time = original
        verdict = f"caught, {wrong} scenario(s) fail" if wrong else "SURVIVED — the set is missing a case"
        if not wrong:
            survived += 1
        print(f"  {name:44} {verdict}")

    print(f"\n{len(checks) - survived}/{len(checks)} mutations caught")
    return survived


if __name__ == "__main__":
    rc = main()
    if mutations():
        rc = 1
    raise SystemExit(rc)
