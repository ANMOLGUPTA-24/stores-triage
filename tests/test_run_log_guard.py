"""A failed run must not be recorded as a decision.

Observed live: a model whose sandbox calls were failing gathered the evidence,
correctly refused to invent a projection, and then wrote `no_action` to the run
log. That is the right *action* - nothing was raised - but the wrong *record*.
In the log it is indistinguishable from the run this project exists to
demonstrate, which is the one where the agent considered the evidence and
concluded that nothing should happen.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://stores:change_me@localhost:5433/stores")
os.environ.setdefault("STORES_MCP_TOKEN", "test-token")
os.environ.setdefault("SMTP_HOST", "localhost")
os.environ.setdefault("SMTP_USER", "test@example.invalid")
os.environ.setdefault("SMTP_PASSWORD", "test")
os.environ.setdefault("VENDOR_MAIL_TO", "vendor@example.invalid")

server = pytest.importorskip("stores_triage.server")


def _fn(tool):
    return getattr(tool, "fn", tool)


def test_no_action_is_refused_without_an_adjudication(monkeypatch):
    monkeypatch.setattr(server, "_ADJUDICATED", {}, raising=False)
    called = []
    monkeypatch.setattr(server.db, "insert_run_log", lambda *a: called.append(a))

    with pytest.raises(ValueError, match="not returned by adjudicate"):
        _fn(server.log_run)("TRB-4417", "no_action", {"why": "sandbox broke"})

    assert called == [], "nothing should reach the database"


def test_inconclusive_is_the_honest_record_for_a_run_that_stopped(monkeypatch):
    monkeypatch.setattr(server, "_ADJUDICATED", {}, raising=False)
    seen = {}
    monkeypatch.setattr(
        server.db, "insert_run_log",
        lambda sid, part, outcome, detail: seen.update(part=part, outcome=outcome),
    )

    _fn(server.log_run)("TRB-4417", "inconclusive", {"reason": "sandbox unreachable"})

    assert seen == {"part": "TRB-4417", "outcome": "inconclusive"}


def test_no_action_is_allowed_once_the_adjudicator_returned_it(monkeypatch):
    monkeypatch.setattr(server, "_ADJUDICATED", {"BRK-2290": "no_action"}, raising=False)
    seen = {}
    monkeypatch.setattr(
        server.db, "insert_run_log",
        lambda sid, part, outcome, detail: seen.update(outcome=outcome),
    )

    _fn(server.log_run)("BRK-2290", "no_action", {"reason": "already on order"})

    assert seen == {"outcome": "no_action"}


def test_the_guard_is_per_part(monkeypatch):
    """A no_action for one part does not licence one for another."""
    monkeypatch.setattr(server, "_ADJUDICATED", {"BRK-2290": "no_action"}, raising=False)
    monkeypatch.setattr(server.db, "insert_run_log", lambda *a: None)

    with pytest.raises(ValueError):
        _fn(server.log_run)("TRB-4417", "no_action", {})


def test_raise_indent_outcome_is_not_gated_by_this(monkeypatch):
    """The indent itself is gated by the harness; the log records what happened."""
    monkeypatch.setattr(server, "_ADJUDICATED", {}, raising=False)
    seen = {}
    monkeypatch.setattr(
        server.db, "insert_run_log",
        lambda sid, part, outcome, detail: seen.update(outcome=outcome),
    )

    _fn(server.log_run)("TRB-4417", "indent_raised", {"indent_no": "IND-2026-0999"})

    assert seen == {"outcome": "indent_raised"}
