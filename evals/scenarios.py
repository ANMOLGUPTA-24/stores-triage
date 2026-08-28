"""Labelled stock-alert scenarios, built to have a known right answer.

The ground truth here is not the adjudicator's opinion of a case - that would
make the evaluation circular and worthless. Each scenario is *constructed* to be
genuine or paper by the physical situation it describes, and the label is
recorded at construction time:

- a consignment that is confirmed in transit, covers the shortfall and lands
  before the stock runs out IS cover, so the alert is paper;
- one that is unconfirmed, short, or lands too late is NOT cover, whatever it
  looks like on the screen, so the alert is genuine.

The hard cases are deliberate. Half of these differ from a paper case by one
field - a status, a quantity, a date - because that is exactly where a stores
officer working across three systems at forty minutes an alert makes the
mistake this project exists to catch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Literal

Truth = Literal["genuine", "paper"]


@dataclass(frozen=True)
class Scenario:
    name: str
    truth: Truth
    why: str
    stock_on_hand: int
    reorder_qty: int
    mean_daily: float
    stdev_daily: float
    lead_p50: float
    lead_p80: float
    consignments: list[dict[str, Any]] = field(default_factory=list)
    indent_no: str | None = None
    linked_consignment: dict[str, Any] | None = None
    despiked_daily: float | None = None
    superseded_by: str | None = None

    @property
    def days_to_stockout(self) -> float:
        return self.stock_on_hand / self.mean_daily


def _eta(today: date, days: int) -> str:
    return (today + timedelta(days=days)).isoformat()


def build(today: date) -> list[Scenario]:
    """A grid of cases across the four benign explanations, plus genuine ones.

    Quantities and rates are varied so the set is not four cases wearing
    different names: stock 18-120, draw 1.9-9.4/day, lead times 12-34 days.
    """
    out: list[Scenario] = []

    # ---- genuinely short, nothing explains it away -----------------------
    for i, (stock, draw, p50, p80) in enumerate(
        [(42, 4.5, 23.0, 30.0), (18, 1.9, 26.0, 34.0), (95, 9.4, 19.0, 25.0), (60, 5.0, 21.0, 28.0)]
    ):
        out.append(Scenario(
            name=f"genuine/bare-{i}",
            truth="genuine",
            why="No inbound, no open indent, steady draw, lead time longer than the stock lasts.",
            stock_on_hand=stock, reorder_qty=200, mean_daily=draw, stdev_daily=draw / 3,
            lead_p50=p50, lead_p80=p80,
        ))

    # ---- inbound_delay: real cover, and near-misses that are not ---------
    out.append(Scenario(
        name="paper/inbound-confirmed",
        truth="paper",
        why="Confirmed in transit, covers the shortfall, lands inside the window.",
        stock_on_hand=55, reorder_qty=300, mean_daily=5.8, stdev_daily=1.6,
        lead_p50=18.0, lead_p80=23.0,
        consignments=[{"consignment_no": "CN-1", "qty": 300, "eta": _eta(today, 3), "status": "in_transit"}],
    ))
    out.append(Scenario(
        name="genuine/inbound-unconfirmed",
        truth="genuine",
        why="Vendor has not confirmed dispatch, so it may never leave. Not cover.",
        stock_on_hand=42, reorder_qty=200, mean_daily=4.5, stdev_daily=1.4,
        lead_p50=23.0, lead_p80=30.0,
        consignments=[{"consignment_no": "CN-2", "qty": 200, "eta": _eta(today, 2), "status": "unconfirmed"}],
    ))
    out.append(Scenario(
        name="genuine/inbound-too-late",
        truth="genuine",
        why="In transit, but arrives after the stock is gone.",
        stock_on_hand=30, reorder_qty=250, mean_daily=5.0, stdev_daily=1.2,
        lead_p50=20.0, lead_p80=27.0,
        consignments=[{"consignment_no": "CN-3", "qty": 250, "eta": _eta(today, 40), "status": "in_transit"}],
    ))
    out.append(Scenario(
        name="genuine/inbound-short-shipped",
        truth="genuine",
        why="In transit and on time, but only a third of the shortfall.",
        stock_on_hand=40, reorder_qty=300, mean_daily=4.0, stdev_daily=1.0,
        lead_p50=22.0, lead_p80=29.0,
        consignments=[{"consignment_no": "CN-4", "qty": 100, "eta": _eta(today, 4), "status": "in_transit"}],
    ))
    out.append(Scenario(
        name="genuine/inbound-overdue",
        truth="genuine",
        why="Still 'in transit' with an ETA that has already passed. Late stock is evidence of a shortage, not cover against one.",
        stock_on_hand=36, reorder_qty=200, mean_daily=4.2, stdev_daily=1.1,
        lead_p50=21.0, lead_p80=28.0,
        consignments=[{"consignment_no": "CN-5", "qty": 200, "eta": _eta(today, -6), "status": "in_transit"}],
    ))

    # ---- duplicate_indent: open indent with and without movement --------
    out.append(Scenario(
        name="paper/indent-with-movement",
        truth="paper",
        why="Open indent with a consignment moving against it, landing in time.",
        stock_on_hand=55, reorder_qty=300, mean_daily=5.8, stdev_daily=1.5,
        lead_p50=18.0, lead_p80=23.0,
        indent_no="IND-A",
        linked_consignment={"consignment_no": "CN-6", "qty": 300, "eta": _eta(today, 2), "status": "in_transit"},
    ))
    out.append(Scenario(
        name="genuine/indent-nothing-moving",
        truth="genuine",
        why="Indent is open but nothing has shipped against it. An order is not stock.",
        stock_on_hand=45, reorder_qty=250, mean_daily=4.8, stdev_daily=1.3,
        lead_p50=24.0, lead_p80=31.0,
        indent_no="IND-B",
        linked_consignment=None,
    ))
    out.append(Scenario(
        name="genuine/indent-linked-overdue",
        truth="genuine",
        why="Indent open, linked consignment overdue and still not received.",
        stock_on_hand=38, reorder_qty=250, mean_daily=4.4, stdev_daily=1.2,
        lead_p50=22.0, lead_p80=29.0,
        indent_no="IND-C",
        linked_consignment={"consignment_no": "CN-7", "qty": 250, "eta": _eta(today, -4), "status": "in_transit"},
    ))

    # ---- consumption_spike: burst vs sustained --------------------------
    out.append(Scenario(
        name="paper/spike-one-off",
        truth="paper",
        why="An overhaul burst tripped the level. The underlying rate leaves stock lasting longer than the lead time.",
        stock_on_hand=120, reorder_qty=200, mean_daily=6.0, stdev_daily=4.0,
        lead_p50=14.0, lead_p80=18.0,
        despiked_daily=1.4,
    ))
    out.append(Scenario(
        name="genuine/spike-but-still-short",
        truth="genuine",
        why="There was a burst, but even the de-spiked rate empties the bin before the vendor delivers.",
        stock_on_hand=50, reorder_qty=200, mean_daily=7.0, stdev_daily=3.5,
        lead_p50=26.0, lead_p80=33.0,
        despiked_daily=4.5,
    ))

    # ---- bom_change ------------------------------------------------------
    out.append(Scenario(
        name="paper/superseded",
        truth="paper",
        why="Part is superseded; buying more of it stocks something the works is moving off.",
        stock_on_hand=40, reorder_qty=200, mean_daily=4.0, stdev_daily=1.0,
        lead_p50=20.0, lead_p80=26.0,
        superseded_by="TRB-4418",
    )),

    # ---- boundary: cover that lands exactly on the day it runs out -------
    out.append(Scenario(
        name="paper/inbound-lands-today",
        truth="paper",
        why="Confirmed cover arriving today still counts as cover.",
        stock_on_hand=48, reorder_qty=250, mean_daily=5.0, stdev_daily=1.2,
        lead_p50=19.0, lead_p80=24.0,
        consignments=[{"consignment_no": "CN-8", "qty": 250, "eta": _eta(today, 0), "status": "in_transit"}],
    ))

    return out
