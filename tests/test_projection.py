"""Tests for the numbers. If these are wrong, every dossier is wrong."""

from __future__ import annotations

import math

import pytest

from stores_triage.projection import (
    DrawRate,
    fit_draw_rate,
    fit_lead_time,
    percentile,
    project_stockout,
    summarise,
)


def log(quantities, start_day: int = 1):
    """One issue event per consecutive day."""
    return [
        {"consumed_on": f"2026-08-{start_day + i:02d}", "qty": q}
        for i, q in enumerate(quantities)
    ]


class TestPercentile:
    def test_median_of_odd_count(self):
        assert percentile([1, 5, 9], 0.5) == 5

    def test_interpolates_between_points(self):
        assert percentile([10, 20], 0.5) == 15

    def test_single_observation_is_its_own_percentile(self):
        # A vendor with one completed order still has to produce a lead time.
        assert percentile([21], 0.8) == 21

    def test_endpoints(self):
        assert percentile([3, 1, 2], 0.0) == 1
        assert percentile([3, 1, 2], 1.0) == 3

    def test_empty_is_an_error(self):
        with pytest.raises(ValueError):
            percentile([], 0.5)

    def test_fraction_out_of_range_is_an_error(self):
        with pytest.raises(ValueError):
            percentile([1, 2], 1.5)


class TestDrawRate:
    def test_mean_of_a_steady_draw(self):
        rate = fit_draw_rate(log([4, 4, 4, 4]))
        assert rate.mean_daily == 4
        assert rate.stdev_daily == 0
        assert rate.days_observed == 4

    def test_steady_draw_has_no_spike(self):
        rate = fit_draw_rate(log([4, 5, 4, 5, 4]))
        assert rate.had_spike is False
        assert rate.spike_days == []

    def test_one_off_overhaul_is_flagged_and_excluded(self):
        # Nineteen ordinary days and one overhaul that drew sixty.
        rate = fit_draw_rate(log([2] * 19 + [60]))
        assert rate.had_spike is True
        assert len(rate.spike_days) == 1
        assert rate.despiked_mean_daily == 2
        # The raw mean is dragged up far enough to trip a reorder level.
        assert rate.mean_daily > 4

    def test_despiked_rate_equals_mean_when_nothing_spikes(self):
        rate = fit_draw_rate(log([3, 3, 4, 2]))
        assert rate.despiked_mean_daily == pytest.approx(rate.mean_daily)

    def test_several_issues_on_one_day_count_as_one_day(self):
        # A row is an issue event, not a day. Counting rows as days would report
        # four days here and halve the mean.
        rows = [
            {"consumed_on": "2026-08-01", "qty": 2},
            {"consumed_on": "2026-08-01", "qty": 3},
            {"consumed_on": "2026-08-02", "qty": 4},
            {"consumed_on": "2026-08-02", "qty": 1},
        ]
        rate = fit_draw_rate(rows)
        assert rate.days_observed == 2
        assert rate.mean_daily == 5

    def test_days_with_no_issues_count_as_zero_draw(self):
        # The query returns no row for a quiet day. Skipping those days would
        # inflate the mean and shorten every stockout date.
        rows = [
            {"consumed_on": "2026-08-01", "qty": 6},
            {"consumed_on": "2026-08-04", "qty": 6},
        ]
        rate = fit_draw_rate(rows)
        assert rate.days_observed == 4
        assert rate.mean_daily == 3

    def test_quiet_days_at_the_window_edges_still_count(self):
        # The log only holds days something moved. A part untouched for the last
        # week has a week of zero-draw days that never appear as rows; dropping
        # them makes stock look like it is going faster than it is.
        rows = [
            {"consumed_on": "2026-08-05", "qty": 10},
            {"consumed_on": "2026-08-06", "qty": 10},
        ]
        without = fit_draw_rate(rows)
        assert without.days_observed == 2
        assert without.mean_daily == 10

        withwindow = fit_draw_rate(
            rows, window_start="2026-08-01", window_end="2026-08-10"
        )
        assert withwindow.days_observed == 10
        assert withwindow.mean_daily == 2

    def test_a_window_that_ends_before_it_starts_is_an_error(self):
        rows = [{"consumed_on": "2026-08-05", "qty": 1}]
        with pytest.raises(ValueError, match="window ends before"):
            fit_draw_rate(rows, window_start="2026-08-10", window_end="2026-08-01")

    def test_a_gap_day_can_be_reported_as_a_spike_free_low(self):
        rows = [{"consumed_on": "2026-08-01", "qty": 5}, {"consumed_on": "2026-08-03", "qty": 5}]
        assert fit_draw_rate(rows).had_spike is False

    def test_empty_log_is_an_error_not_a_zero(self):
        # Silently returning 0/day would project an infinite stockout date.
        with pytest.raises(ValueError, match="no consumption rows"):
            fit_draw_rate([])


class TestLeadTime:
    ORDERS = [
        {"actual_days": d, "promised_days": 21}
        for d in (18, 20, 22, 24, 26, 28, 30, 33)
    ]

    def test_percentiles_come_from_what_happened(self):
        lead = fit_lead_time(self.ORDERS)
        assert lead.p50 == pytest.approx(25.0)
        assert lead.p80 > lead.p50
        assert lead.worst == 33

    def test_a_vendor_that_misses_its_promise_is_flagged(self):
        lead = fit_lead_time(self.ORDERS)
        assert lead.promised == 21
        assert lead.runs_late is True

    def test_a_vendor_that_keeps_its_promise_is_not_flagged(self):
        orders = [{"actual_days": d, "promised_days": 21} for d in (18, 19, 20)]
        assert fit_lead_time(orders).runs_late is False

    def test_orders_still_open_are_ignored(self):
        orders = self.ORDERS + [{"actual_days": None, "promised_days": 21}]
        assert fit_lead_time(orders).orders_observed == len(self.ORDERS)

    def test_no_completed_orders_is_an_error(self):
        with pytest.raises(ValueError, match="no completed orders"):
            fit_lead_time([{"actual_days": None, "promised_days": 21}])


class TestStockout:
    def test_median_is_stock_over_rate(self):
        rate = DrawRate(mean_daily=4.0, stdev_daily=0.0, days_observed=30)
        assert project_stockout(40, rate).days_p50 == 10

    def test_with_no_variance_the_band_collapses(self):
        rate = DrawRate(mean_daily=4.0, stdev_daily=0.0, days_observed=30)
        out = project_stockout(40, rate)
        assert out.days_p10 == pytest.approx(10)
        assert out.days_p90 == pytest.approx(10)

    def test_variance_opens_the_band_around_the_median(self):
        rate = DrawRate(mean_daily=4.0, stdev_daily=2.0, days_observed=30)
        out = project_stockout(40, rate)
        assert out.days_p10 < out.days_p50 < out.days_p90

    def test_the_band_is_asymmetric(self):
        # sqrt(t) scaling means the late tail stretches further than the early
        # one. A flat percentage haircut would miss this.
        rate = DrawRate(mean_daily=4.0, stdev_daily=2.0, days_observed=30)
        out = project_stockout(40, rate)
        early = out.days_p50 - out.days_p10
        late = out.days_p90 - out.days_p50
        assert late > early

    def test_the_early_edge_is_a_real_tenth_percentile(self):
        # The field is called p10, so the z it solves with must be the 90th
        # percentile of the standard normal (1.2816), not the 80th (0.8416).
        # Using the latter would name a p20 edge "p10" and hand adjudication a
        # deadline less conservative than the dossier claims.
        from statistics import NormalDist

        z = NormalDist().inv_cdf(0.90)
        rate = DrawRate(mean_daily=4.0, stdev_daily=2.0, days_observed=30)
        t = project_stockout(40, rate).days_p10
        assert 4.0 * t + z * 2.0 * math.sqrt(t) == pytest.approx(40)

    def test_the_late_edge_is_a_real_ninetieth_percentile(self):
        from statistics import NormalDist

        z = NormalDist().inv_cdf(0.90)
        rate = DrawRate(mean_daily=4.0, stdev_daily=2.0, days_observed=30)
        t = project_stockout(40, rate).days_p90
        assert 4.0 * t - z * 2.0 * math.sqrt(t) == pytest.approx(40)

    def test_zero_consumption_is_an_error(self):
        rate = DrawRate(mean_daily=0.0, stdev_daily=0.0, days_observed=30)
        with pytest.raises(ValueError, match="no consumption"):
            project_stockout(40, rate)

    def test_negative_stock_is_an_error(self):
        rate = DrawRate(mean_daily=4.0, stdev_daily=1.0, days_observed=30)
        with pytest.raises(ValueError):
            project_stockout(-1, rate)


class TestSummarise:
    def test_keys_match_what_adjudicate_expects(self):
        from stores_triage.triage import Projection

        rate = fit_draw_rate(log([4, 5, 4, 3, 4] * 6))
        lead = fit_lead_time(
            [{"actual_days": d, "promised_days": 21} for d in (20, 24, 28, 33)]
        )
        out = summarise(
            part_no="TRB-4417",
            stock_on_hand=42,
            draw=rate,
            lead=lead,
            stockout=project_stockout(42, rate),
        )
        # Everything Projection needs must be present and nothing it rejects.
        fields = {
            k: v for k, v in out.items() if not k.startswith("_") and k in
            Projection.__dataclass_fields__
        }
        assert set(fields) == set(Projection.__dataclass_fields__)
        Projection(**fields)

    def test_supporting_evidence_travels_with_the_numbers(self):
        rate = fit_draw_rate(log([2] * 19 + [60]))
        lead = fit_lead_time([{"actual_days": 24, "promised_days": 21}])
        out = summarise(
            part_no="TRB-4417",
            stock_on_hand=42,
            draw=rate,
            lead=lead,
            stockout=project_stockout(42, rate),
        )
        assert out["_evidence"]["spike_days"]
        assert out["_evidence"]["vendor_runs_late"] is True
        assert out["_evidence"]["days_observed"] == 20
