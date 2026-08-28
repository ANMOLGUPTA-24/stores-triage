"""stores-mcp - the tool surface TrueForge talks to.

TrueForge connects to remote MCP servers over HTTP, so this is a real server on
a real port, backed by a real Postgres. The harness runs the agent loop, the
sandbox, the approval pause and the subagents; this only supplies tools.

Write tools carry destructiveHint so the harness knows to hold them for
approval. Read tools carry readOnlyHint so investigation never stops to ask.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from uuid import uuid4
from typing import Any

from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import StaticTokenVerifier

from stores_triage import db, mailer
from stores_triage.triage import Projection, Verdict, adjudicate as _adjudicate, hydrate_dates

load_dotenv()

_TOKEN = os.environ.get("STORES_MCP_TOKEN")
if not _TOKEN or _TOKEN == "change_me":
    raise SystemExit(
        "STORES_MCP_TOKEN must be set to something other than 'change_me'. "
        "See .env.example."
    )

mcp = FastMCP(
    name="stores",
    instructions=(
        "Spare-part stock records for a locomotive works. Read tools investigate "
        "a stock alert; adjudicate turns four hypothesis verdicts into a "
        "recommendation; raise_indent and send_vendor_mail are irreversible, so "
        "the harness holds them for a human. Calling one is how you request approval - publish the dossier first, then call it and let it be held."
    ),
    auth=StaticTokenVerifier(tokens={_TOKEN: {"client_id": "trueforge"}}),
)

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False}

# part_no -> the action adjudicate() last returned for it, in this process.
# Deliberately not persisted: it exists to stop a single run recording a
# decision it never made, not to remember anything across restarts.
_ADJUDICATED: dict[str, str] = {}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False}


# ---------------------------------------------------------------------------
# Investigation
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def list_alerts() -> list[dict[str, Any]]:
    """Every part currently below its reorder level, worst ratio first."""
    return db.list_alerts()


@mcp.tool(annotations=READ_ONLY)
def get_part(part_no: str) -> dict[str, Any]:
    """Master record for one part: stock on hand, reorder level and quantity."""
    part = db.get_part(part_no)
    if part is None:
        raise ValueError(f"no such part: {part_no}")
    return part


@mcp.tool(annotations=READ_ONLY)
def get_consumption_log(part_no: str, days: int = 120) -> dict[str, Any]:
    """Daily issue history. Use this to fit a draw rate in the sandbox.

    Returns the rows themselves, not a summary - the numbers must be computed
    from the log by code, never estimated from a description of it.
    """
    rows = db.get_consumption_log(part_no, days)
    window_start, window_end = db.consumption_window(days)
    return {
        "part_no": part_no,
        "days": days,
        # The window the query actually used. The log only holds days something
        # moved, so the sandbox cannot infer the quiet stretches at either edge -
        # and inferring them from its own clock puts it on a different day to the
        # database whenever the two are in different timezones.
        "window_start": window_start,
        "window_end": window_end,
        "rows": rows,
        "row_count": len(rows),
    }


@mcp.tool(annotations=READ_ONLY)
def list_open_indents(part_no: str) -> list[dict[str, Any]]:
    """Open indents for a part, each with any consignment moving against it.

    This is the duplicate_indent hypothesis's primary evidence.
    """
    return db.list_open_indents(part_no)


@mcp.tool(annotations=READ_ONLY)
def list_consignments(part_no: str) -> list[dict[str, Any]]:
    """Consignments not yet received.

    Status matters: 'in_transit' is confirmed cover, 'unconfirmed' means the
    vendor has not confirmed dispatch and it must not be counted as cover.
    """
    return db.list_consignments(part_no)


@mcp.tool(annotations=READ_ONLY)
def get_vendor_lead_times(vendor_code: str) -> list[dict[str, Any]]:
    """Historical promised vs actual lead times, for fitting a distribution."""
    return db.get_vendor_lead_times(vendor_code)


# ---------------------------------------------------------------------------
# Decision
# ---------------------------------------------------------------------------


@mcp.tool(annotations=READ_ONLY)
def adjudicate(
    part_no: str,
    projection: dict[str, float],
    verdicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Weigh the four hypothesis verdicts and return one recommendation.

    This is deterministic code, not a judgement call. All four hypotheses must
    be present - adjudicating on partial evidence would mean recommending an
    irreversible action without having checked everything.

    projection must come from sandbox-computed numbers and carry
    mean_daily_draw, days_to_stockout_p50, days_to_stockout_p10, lead_time_p50
    and lead_time_p80.

    Each verdict is {hypothesis, verdict, evidence, note} where verdict is
    'positive', 'negative' or 'inconclusive'.
    """
    part = db.get_part(part_no)
    if part is None:
        raise ValueError(f"no such part: {part_no}")

    rec = _adjudicate(
        part_no=part_no,
        stock_on_hand=part["stock_on_hand"],
        reorder_qty=part["reorder_qty"],
        projection=Projection(**projection),
        verdicts=[
            Verdict(
                hypothesis=v["hypothesis"],
                verdict=v["verdict"],
                evidence=hydrate_dates(v.get("evidence") or {}),
                note=v.get("note", ""),
            )
            for v in verdicts
        ],
        today=db.today(),
    )
    # What log_run is allowed to record for this part. The deterministic
    # decision is the only thing entitled to the name "no_action".
    _ADJUDICATED[part_no] = rec.action
    return {
        "action": rec.action,
        "reason": rec.reason,
        "what_would_change_my_mind": rec.what_would_change_my_mind,
        "ruled_out": rec.ruled_out,
        "urgency": rec.urgency,
        "indent_qty": rec.indent_qty,
    }


@mcp.tool(annotations=READ_ONLY)
def draft_indent(part_no: str, qty: int) -> dict[str, Any]:
    """Build the exact indent and mail that raise_indent would send.

    Nothing is written and nothing is sent. This exists so the approval card can
    show the operator the real payload rather than a description of it.
    """
    part = db.get_part(part_no)
    if part is None:
        raise ValueError(f"no such part: {part_no}")
    vendor = db.get_vendor_for_part(part_no) or {}
    needed_by = db.today().isoformat()
    msg = mailer.compose(
        indent_no="(allocated on approval)",
        part_no=part_no,
        description=part["description"],
        qty=qty,
        uom=part["uom"],
        vendor_name=vendor.get("vendor_name", "Vendor"),
        needed_by=needed_by,
    )
    return {
        "indent": {
            "part_no": part_no,
            "description": part["description"],
            "qty": qty,
            "uom": part["uom"],
            "vendor_code": part["vendor_code"],
            "vendor_name": vendor.get("vendor_name"),
        },
        "mail": {
            "to": msg["To"],
            "subject": msg["Subject"],
            "body": msg.get_content(),
        },
    }


# ---------------------------------------------------------------------------
# Irreversible - the harness holds these for a human
# ---------------------------------------------------------------------------


@mcp.tool(annotations=DESTRUCTIVE)
def raise_indent(part_no: str, qty: int, raised_by: str = "stores-triage") -> dict[str, Any]:
    """Write a new open indent against the part. Irreversible.

    Never call this without an approved dossier.
    """
    part = db.get_part(part_no)
    if part is None:
        raise ValueError(f"no such part: {part_no}")
    if qty <= 0:
        raise ValueError("indent quantity must be positive")
    return db.insert_indent(part_no, qty, raised_by)


@mcp.tool(annotations=DESTRUCTIVE)
def send_vendor_mail(part_no: str, indent_no: str, qty: int, needed_by: str) -> dict[str, Any]:
    """Mail the vendor asking them to supply against the indent. Irreversible.

    Never call this without an approved dossier.
    """
    part = db.get_part(part_no)
    if part is None:
        raise ValueError(f"no such part: {part_no}")
    vendor = db.get_vendor_for_part(part_no) or {}
    msg = mailer.compose(
        indent_no=indent_no,
        part_no=part_no,
        description=part["description"],
        qty=qty,
        uom=part["uom"],
        vendor_name=vendor.get("vendor_name", "Vendor"),
        needed_by=needed_by,
    )
    return mailer.send(msg)


@mcp.tool(annotations={"readOnlyHint": False, "destructiveHint": False})
def log_run(
    part_no: str,
    outcome: str,
    detail: dict[str, Any],
    session_id: str | None = None,
) -> dict[str, Any]:
    """Record what this run decided.

    outcome is 'indent_raised', 'no_action', 'rejected_by_operator', or
    'inconclusive' when the run could not reach a decision at all. A run that
    correctly decides to do nothing is a result, not an absence, and gets logged
    like any other - but a run that merely failed is NOT that result, and must
    not borrow its name.

    'no_action' is therefore refused unless adjudicate() actually returned it
    for this part. An agent that stopped early - a broken sandbox, a missing
    projection, a rate limit - has to say 'inconclusive', which is the honest
    record and the one an operator can act on. Observed in a live run: a model
    whose sandbox calls were failing collected the evidence, correctly declined
    to invent a projection, and then logged 'no_action' - indistinguishable in
    the log from the run this whole project is built to demonstrate.

    session_id is optional. The agent has no reliable way to learn its own
    session id, and a required argument it cannot supply would make it invent
    one - so the server allocates a stable id instead of the model guessing.
    """
    if outcome == "no_action" and _ADJUDICATED.get(part_no) != "no_action":
        raise ValueError(
            "no_action was not returned by adjudicate() for this part in this "
            "process. If the run could not reach a decision, log 'inconclusive' "
            "with the reason - do not record a failure as a decision."
        )
    return db.insert_run_log(session_id or f"run-{uuid4().hex[:12]}", part_no, outcome, detail)


@mcp.tool(annotations=READ_ONLY)
def list_run_log(limit: int = 50) -> list[dict[str, Any]]:
    """Previous runs, newest first."""
    return db.list_run_log(limit)


def main() -> None:
    mcp.run(
        transport="http",
        host=os.environ.get("STORES_MCP_HOST", "0.0.0.0"),
        port=int(os.environ.get("STORES_MCP_PORT", "8081")),
    )


if __name__ == "__main__":
    main()
