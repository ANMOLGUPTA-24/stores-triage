#!/usr/bin/env python3
"""Compute the numbers for a stock alert, and draw the chart.

Runs in the sandbox. Reads one JSON file, prints one JSON block, optionally
writes a PNG. Deliberately standard-library only apart from the chart, so it
works in a bare sandbox and degrades to numbers-without-a-picture rather than
failing outright when matplotlib is missing.

    python analyse.py input.json --chart chart.png

input.json:
    {"part": {...}, "consumption_rows": [...], "lead_time_rows": [...]}
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from projection import (  # noqa: E402  (path set above)
    fit_draw_rate,
    fit_lead_time,
    project_stockout,
    summarise,
)


def draw_chart(path: str, *, part_no: str, mean_daily: float, stock_on_hand: int, stockout, lead) -> bool:
    """Stock burn-down with the uncertainty band and the lead-time marker.

    Returns False if matplotlib is not installed - the numbers still stand.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    horizon = max(stockout.days_p90, lead.p80) * 1.12
    days = [d * horizon / 200 for d in range(201)]
    # Zero stock is the most urgent alert there is, and it gives a zero median.
    # Deriving the rate by division here would make that the one case that
    # crashes instead of charting.
    mean_rate = mean_daily
    top = max(stock_on_hand, 1) * 1.12

    fig, ax = plt.subplots(figsize=(9, 4.2))

    # The gap between running dry and the vendor turning up is the whole
    # argument for ordering now, so draw it rather than leaving it implied.
    exposed = lead.p80 - stockout.days_p50
    if exposed > 0:
        ax.axvspan(stockout.days_p50, lead.p80, color="#d9534f", alpha=0.10, linewidth=0)
        ax.annotate(
            f"{exposed:.0f} days with no stock",
            xy=((stockout.days_p50 + lead.p80) / 2, top * 0.58),
            ha="center", va="center", fontsize=9, color="#8a2f2c",
        )

    ax.fill_between(
        [stockout.days_p10, stockout.days_p90], 0, top,
        color="#111111", alpha=0.08, linewidth=0,
        label=f"runs dry, {stockout.days_p10:.0f}-{stockout.days_p90:.0f} days",
    )
    ax.plot(days, [max(0, stock_on_hand - mean_rate * d) for d in days],
            color="#111111", linewidth=1.8, label="stock on hand")
    ax.axvline(lead.p80, color="#8a2f2c", linewidth=1.6,
               label=f"vendor delivers, {lead.p80:.0f} days (p80)")
    ax.axhline(0, color="#bbbbbb", linewidth=0.8)

    ax.set_xlim(0, horizon)
    ax.set_ylim(0, top)
    ax.set_xlabel("days from today")
    ax.set_ylabel("stock on hand")
    ax.set_title(
        f"{part_no} - runs dry in {stockout.days_p50:.0f} days, "
        f"vendor takes {lead.p80:.0f}",
        loc="left", fontsize=11,
    )
    ax.legend(frameon=False, fontsize=8, loc="lower right", borderaxespad=1.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="JSON file: part, consumption_rows, lead_time_rows")
    parser.add_argument("--chart", help="write a PNG here")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text())
    part = payload["part"]
    # The rows only cover days something moved. Reconstruct the window that was
    # actually queried so quiet days at either edge still count as zero draw.
    window_days = payload.get("window_days")
    today = date.today()
    draw = fit_draw_rate(
        payload["consumption_rows"],
        window_start=today - timedelta(days=window_days - 1) if window_days else None,
        window_end=today if window_days else None,
    )
    lead = fit_lead_time(payload["lead_time_rows"])
    stockout = project_stockout(part["stock_on_hand"], draw)

    summary = summarise(
        part_no=part["part_no"],
        stock_on_hand=part["stock_on_hand"],
        draw=draw,
        lead=lead,
        stockout=stockout,
    )
    evidence = summary.pop("_evidence")

    charted = False
    if args.chart:
        charted = draw_chart(
            args.chart,
            part_no=part["part_no"],
            mean_daily=draw.mean_daily,
            stock_on_hand=part["stock_on_hand"],
            stockout=stockout,
            lead=lead,
        )

    print(json.dumps({
        "projection": {k: v for k, v in summary.items() if k not in ("part_no", "stock_on_hand")},
        "evidence": evidence,
        "chart": args.chart if charted else None,
        "chart_skipped_reason": None if charted or not args.chart else "matplotlib not installed",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
