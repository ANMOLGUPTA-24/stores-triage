"""The sandbox pulls its own inputs, so the model never restates the record.

The first live run had the agent retype 120 consumption rows into a heredoc
from a tool result it had just read. Nothing caught it, because nothing tested
how the analysis got its inputs - only what it did with them.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ANALYSE = Path(__file__).resolve().parents[1] / "skills/stores-triage/scripts/analyse.py"
_spec = importlib.util.spec_from_file_location("analyse", _ANALYSE)
analyse = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(analyse)


PART = {"part_no": "TRB-4417", "stock_on_hand": 42, "vendor_code": "V-3301"}


def _recorder(responses):
    calls = []

    def call(tool, arguments):
        calls.append((tool, arguments))
        return responses[tool]

    return call, calls


def test_build_payload_makes_exactly_three_calls():
    call, calls = _recorder({
        "get_part": PART,
        "get_consumption_log": {"rows": [{"consumed_on": "2026-08-01", "qty": 4}]},
        "get_vendor_lead_times": [{"actual_days": 20, "promised_days": 21}],
    })

    payload = analyse.build_payload("TRB-4417", 120, call)

    assert [t for t, _ in calls] == [
        "get_part",
        "get_consumption_log",
        "get_vendor_lead_times",
    ]
    assert payload["part"] is PART
    assert payload["window_days"] == 120
    assert payload["consumption_rows"] == [{"consumed_on": "2026-08-01", "qty": 4}]


def test_vendor_code_comes_from_the_part_not_the_caller():
    """The lead-time query has to use the vendor the part actually names."""
    call, calls = _recorder({
        "get_part": PART,
        "get_consumption_log": {"rows": []},
        "get_vendor_lead_times": [],
    })

    analyse.build_payload("TRB-4417", 90, call)

    assert dict(calls)["get_vendor_lead_times"] == {"vendor_code": "V-3301"}
    assert dict(calls)["get_consumption_log"]["days"] == 90


def test_window_days_is_the_window_that_was_queried():
    """A mismatch here silently inflates the draw rate, so pin it."""
    call, _ = _recorder({
        "get_part": PART,
        "get_consumption_log": {"rows": []},
        "get_vendor_lead_times": [],
    })

    assert analyse.build_payload("TRB-4417", 30, call)["window_days"] == 30


@pytest.mark.parametrize(
    "raw, expected",
    [
        ({"result": [1, 2]}, [1, 2]),
        ({"result": []}, []),
        ({"part_no": "TRB-4417"}, {"part_no": "TRB-4417"}),
        ({"result": [], "rows": []}, {"result": [], "rows": []}),
        ([1, 2], [1, 2]),
    ],
)
def test_unwrap_only_unwraps_the_fastmcp_envelope(raw, expected):
    """A real payload that merely has a "result" key must survive intact."""
    assert analyse._unwrap(raw) == expected


def test_payload_carries_the_window_the_database_reported():
    """The fit must use the window the query used, not this process's clock.

    Postgres runs on UTC in the compose file and the laptop runs on IST, so for
    five and a half hours a day they are on different dates. Deriving the window
    locally shifted the draw rate - 4.48/day in the sandbox against 4.45/day on
    the host, from identical rows.
    """
    call, _ = _recorder({
        "get_part": PART,
        "get_consumption_log": {
            "rows": [],
            "window_start": "2026-04-30",
            "window_end": "2026-08-27",
        },
        "get_vendor_lead_times": [],
    })

    payload = analyse.build_payload("TRB-4417", 120, call)

    assert payload["window_start"] == "2026-04-30"
    assert payload["window_end"] == "2026-08-27"


def test_payload_survives_a_log_without_window_bounds():
    """Older payloads still work; they just fall back to window_days."""
    call, _ = _recorder({
        "get_part": PART,
        "get_consumption_log": {"rows": []},
        "get_vendor_lead_times": [],
    })

    payload = analyse.build_payload("TRB-4417", 120, call)

    assert payload["window_start"] is None
    assert payload["window_days"] == 120
