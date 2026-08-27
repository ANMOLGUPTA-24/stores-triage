"""Tests for adjudication, including the Run B case the demo turns on."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from stores_triage.triage import (
    HYPOTHESES,
    Projection,
    Recommendation,
    Verdict,
    adjudicate,
)

TODAY = date(2026, 8, 25)


def negatives(*except_for: str) -> list[Verdict]:
    """All four hypotheses negative, minus the ones the test will supply."""
    return [
        Verdict(hypothesis=h, verdict="negative")
        for h in HYPOTHESES
        if h not in except_for
    ]


# Run A: TRB-4417, 42 on hand, 4.23/day, ~10 days of stock, 21-33 day lead time.
RUN_A_PROJECTION = Projection(
    mean_daily_draw=4.23,
    days_to_stockout_p50=9.9,
    days_to_stockout_p10=8.1,
    lead_time_p50=24.7,
    lead_time_p80=30.0,
)

# Run B: BRK-2290, 55 on hand, 5.37/day, ~10 days of stock.
RUN_B_PROJECTION = Projection(
    mean_daily_draw=5.37,
    days_to_stockout_p50=10.2,
    days_to_stockout_p10=8.4,
    lead_time_p50=19.7,
    lead_time_p80=23.0,
)


def run_a(**overrides) -> Recommendation:
    kwargs = dict(
        part_no="TRB-4417",
        stock_on_hand=42,
        reorder_qty=200,
        projection=RUN_A_PROJECTION,
        today=TODAY,
    )
    kwargs.update(overrides)
    return adjudicate(**kwargs)


def run_b(**overrides) -> Recommendation:
    kwargs = dict(
        part_no="BRK-2290",
        stock_on_hand=55,
        reorder_qty=300,
        projection=RUN_B_PROJECTION,
        today=TODAY,
    )
    kwargs.update(overrides)
    return adjudicate(**kwargs)


class TestRunAGenuineShortage:
    """Nothing explains the shortage away, so it is real."""

    def test_recommends_raising_the_indent(self):
        rec = run_a(verdicts=negatives())
        assert rec.action == "raise_indent"
        assert rec.indent_qty == 200

    def test_urgency_is_critical_when_stock_runs_out_inside_the_lead_time(self):
        # 8.1 days of stock against a 30-day lead time: already too late to be calm.
        rec = run_a(verdicts=negatives())
        assert rec.urgency == "critical"

    def test_all_four_hypotheses_are_reported_as_ruled_out(self):
        rec = run_a(verdicts=negatives())
        assert sorted(rec.ruled_out) == sorted(HYPOTHESES)

    def test_unconfirmed_consignment_is_not_treated_as_cover(self):
        # CN-8821 covers the quantity and lands in time, but the vendor has not
        # confirmed dispatch. Counting it as cover is exactly the mistake that
        # idles a locomotive.
        verdicts = negatives("inbound_delay") + [
            Verdict(
                hypothesis="inbound_delay",
                verdict="positive",
                evidence={
                    "consignments": [
                        {
                            "consignment_no": "CN-8821",
                            "qty": 200,
                            "eta": TODAY + timedelta(days=2),
                            "status": "unconfirmed",
                        }
                    ]
                },
            )
        ]
        rec = run_a(verdicts=verdicts)
        assert rec.action == "raise_indent"

    def test_counterfactual_names_the_unconfirmed_consignment(self):
        # The operator must be able to check the one fact that would flip this.
        verdicts = negatives("inbound_delay") + [
            Verdict(
                hypothesis="inbound_delay",
                verdict="positive",
                evidence={
                    "consignments": [
                        {
                            "consignment_no": "CN-8821",
                            "qty": 200,
                            "eta": TODAY + timedelta(days=2),
                            "status": "unconfirmed",
                        }
                    ]
                },
            )
        ]
        rec = run_a(verdicts=verdicts)
        assert "CN-8821" in rec.what_would_change_my_mind
        assert "2026-08-27" in rec.what_would_change_my_mind

    def test_counterfactual_exists_even_with_no_near_misses(self):
        rec = run_a(verdicts=negatives())
        assert rec.what_would_change_my_mind.strip()
        assert "TRB-4417" in rec.what_would_change_my_mind


class TestRunBPaperShortage:
    """The alert looks identical to Run A. The evidence says do nothing."""

    def test_duplicate_indent_with_stock_moving_means_no_action(self):
        verdicts = negatives("duplicate_indent", "inbound_delay") + [
            Verdict(
                hypothesis="duplicate_indent",
                verdict="positive",
                evidence={
                    "indent_no": "IND-2026-0731",
                    "raised_on": TODAY - timedelta(days=7),
                    "linked_consignment": {
                        "consignment_no": "CN-9104",
                        "qty": 300,
                        "eta": TODAY + timedelta(days=3),
                        "status": "in_transit",
                    },
                },
            ),
            Verdict(
                hypothesis="inbound_delay",
                verdict="positive",
                evidence={
                    "consignments": [
                        {
                            "consignment_no": "CN-9104",
                            "qty": 300,
                            "eta": TODAY + timedelta(days=3),
                            "status": "in_transit",
                        }
                    ]
                },
            ),
        ]
        rec = run_b(verdicts=verdicts)
        assert rec.action == "no_action"
        assert rec.indent_qty is None

    def test_no_action_still_cites_its_evidence(self):
        verdicts = negatives("duplicate_indent") + [
            Verdict(
                hypothesis="duplicate_indent",
                verdict="positive",
                evidence={
                    "indent_no": "IND-2026-0731",
                    "linked_consignment": {
                        "consignment_no": "CN-9104",
                        "qty": 300,
                        "eta": TODAY + timedelta(days=3),
                        "status": "in_transit",
                    },
                },
            )
        ]
        rec = run_b(verdicts=verdicts)
        assert "IND-2026-0731" in rec.reason
        assert "CN-9104" in rec.reason
        assert rec.what_would_change_my_mind.strip()

    def test_inbound_alone_is_enough_when_it_covers_in_time(self):
        verdicts = negatives("inbound_delay") + [
            Verdict(
                hypothesis="inbound_delay",
                verdict="positive",
                evidence={
                    "consignments": [
                        {
                            "consignment_no": "CN-9104",
                            "qty": 300,
                            "eta": TODAY + timedelta(days=3),
                            "status": "in_transit",
                        }
                    ]
                },
            )
        ]
        rec = run_b(verdicts=verdicts)
        assert rec.action == "no_action"
        assert "CN-9104" in rec.reason

    def test_open_indent_with_nothing_moving_does_not_stop_the_indent(self):
        # An indent raised last week that nobody has shipped against is not cover.
        verdicts = negatives("duplicate_indent") + [
            Verdict(
                hypothesis="duplicate_indent",
                verdict="positive",
                evidence={"indent_no": "IND-2026-0731", "linked_consignment": None},
            )
        ]
        rec = run_b(verdicts=verdicts)
        assert rec.action == "raise_indent"
        assert "IND-2026-0731" in rec.what_would_change_my_mind


class TestOverdueCover:
    """A consignment past its ETA and still not received is late, not cover."""

    def _overdue(self, days_late: int):
        return [
            {
                "consignment_no": "CN-9104",
                "qty": 300,
                "eta": TODAY - timedelta(days=days_late),
                "status": "in_transit",
            }
        ]

    def test_an_overdue_consignment_does_not_stop_the_indent(self):
        # Saying "no action, it is due 2026-08-28" two days after the 28th is
        # exactly how a genuine shortage gets missed.
        verdicts = negatives("inbound_delay") + [
            Verdict(hypothesis="inbound_delay", verdict="positive",
                    evidence={"consignments": self._overdue(2)})
        ]
        assert run_b(verdicts=verdicts).action == "raise_indent"

    def test_an_overdue_linked_consignment_does_not_stop_the_indent(self):
        verdicts = negatives("duplicate_indent") + [
            Verdict(hypothesis="duplicate_indent", verdict="positive",
                    evidence={"indent_no": "IND-2026-0731",
                              "linked_consignment": self._overdue(2)[0]})
        ]
        rec = run_b(verdicts=verdicts)
        assert rec.action == "raise_indent"
        assert "IND-2026-0731" in rec.what_would_change_my_mind

    def test_a_consignment_due_today_still_counts(self):
        # Due today is not overdue; the boundary must not exclude it.
        verdicts = negatives("inbound_delay") + [
            Verdict(hypothesis="inbound_delay", verdict="positive",
                    evidence={"consignments": self._overdue(0)})
        ]
        assert run_b(verdicts=verdicts).action == "no_action"


class TestCoverThatArrivesTooLate:
    def test_consignment_landing_after_stockout_is_not_cover(self):
        verdicts = negatives("inbound_delay") + [
            Verdict(
                hypothesis="inbound_delay",
                verdict="positive",
                evidence={
                    "consignments": [
                        {
                            "consignment_no": "CN-9999",
                            "qty": 300,
                            "eta": TODAY + timedelta(days=40),
                            "status": "in_transit",
                        }
                    ]
                },
            )
        ]
        rec = run_b(verdicts=verdicts)
        assert rec.action == "raise_indent"

    def test_short_shipment_is_not_cover(self):
        verdicts = negatives("inbound_delay") + [
            Verdict(
                hypothesis="inbound_delay",
                verdict="positive",
                evidence={
                    "consignments": [
                        {
                            "consignment_no": "CN-9104",
                            "qty": 10,
                            "eta": TODAY + timedelta(days=3),
                            "status": "in_transit",
                        }
                    ]
                },
            )
        ]
        rec = run_b(verdicts=verdicts)
        assert rec.action == "raise_indent"


class TestConsumptionSpike:
    def test_one_off_burst_with_slack_underneath_means_no_action(self):
        # Stripping the overhaul burst leaves 1.0/day: 42 days of stock against
        # a 30-day lead time, so the reorder trigger was misleading.
        verdicts = negatives("consumption_spike") + [
            Verdict(
                hypothesis="consumption_spike",
                verdict="positive",
                evidence={"despiked_daily_draw": 1.0},
                note="single overhaul on 12 Aug drew 60 nos",
            )
        ]
        rec = run_a(verdicts=verdicts)
        assert rec.action == "no_action"
        assert "one-off" in rec.reason

    def test_burst_that_does_not_explain_the_shortage_is_rejected(self):
        # De-spiked rate still empties the bin inside the lead time.
        verdicts = negatives("consumption_spike") + [
            Verdict(
                hypothesis="consumption_spike",
                verdict="positive",
                evidence={"despiked_daily_draw": 4.0},
            )
        ]
        rec = run_a(verdicts=verdicts)
        assert rec.action == "raise_indent"


class TestBomChange:
    def test_superseded_part_is_referred_to_engineering(self):
        verdicts = negatives("bom_change") + [
            Verdict(
                hypothesis="bom_change",
                verdict="positive",
                evidence={"superseded_by": "TRB-4419"},
            )
        ]
        rec = run_a(verdicts=verdicts)
        assert rec.action == "no_action"
        assert "TRB-4419" in rec.reason


class TestInputValidation:
    def test_a_missing_hypothesis_is_an_error_not_a_silent_pass(self):
        # Adjudicating on three of four verdicts would mean recommending an
        # irreversible action on incomplete evidence.
        with pytest.raises(ValueError, match="bom_change"):
            run_a(verdicts=negatives("bom_change"))

    def test_unknown_hypothesis_is_rejected(self):
        with pytest.raises(ValueError, match="unknown hypothesis"):
            Verdict(hypothesis="vibes", verdict="positive")

    def test_unknown_verdict_value_is_rejected(self):
        with pytest.raises(ValueError, match="unknown verdict"):
            Verdict(hypothesis="bom_change", verdict="probably")

    def test_inconclusive_does_not_count_as_positive(self):
        # A subagent that could not decide must not be able to block an indent.
        verdicts = negatives("inbound_delay") + [
            Verdict(hypothesis="inbound_delay", verdict="inconclusive")
        ]
        rec = run_a(verdicts=verdicts)
        assert rec.action == "raise_indent"

    def test_inconclusive_is_not_reported_as_ruled_out(self):
        verdicts = negatives("bom_change") + [
            Verdict(hypothesis="bom_change", verdict="inconclusive")
        ]
        rec = run_a(verdicts=verdicts)
        assert "bom_change" not in rec.ruled_out
