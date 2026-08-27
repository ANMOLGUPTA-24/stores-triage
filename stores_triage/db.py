"""Read and write the stores database.

Every query here runs against a real Postgres holding synthetic seed data.
Nothing in this module returns a made-up row.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row


class ConfigError(RuntimeError):
    """Raised when the server is missing configuration it cannot invent."""


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ConfigError("DATABASE_URL is not set. Copy .env.example to .env.")
    return url


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(_database_url(), row_factory=dict_row) as conn:
        yield conn


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    """Dates go over the wire as ISO strings so the model reads them unambiguously."""
    return {k: (v.isoformat() if isinstance(v, date) else v) for k, v in row.items()}


def _rows(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return [_jsonable(r) for r in cur.fetchall()]


def _row(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    found = _rows(sql, params)
    return found[0] if found else None


# ---------------------------------------------------------------------------
# Read-only
# ---------------------------------------------------------------------------


def today() -> date:
    """The database's idea of today, which is the only one that counts here.

    Every date in this system is relative to Postgres CURRENT_DATE: the seed, the
    consumption window, the consignment ETAs, the indent numbers. The Python
    process can disagree - a container on UTC and a laptop on IST are on
    different days for five and a half hours out of every twenty-four - and when
    it does, adjudication compares an ETA against a "today" that the data was
    never built around. That is a day of skew in the direction that throws away
    valid cover, which is exactly the mistake this project exists to catch.
    """
    row = _row("SELECT CURRENT_DATE AS today")
    assert row is not None  # a SELECT of a constant always returns a row
    value = row["today"]
    return value if isinstance(value, date) else date.fromisoformat(str(value))


def consumption_window(days: int) -> tuple[str, str]:
    """The exact window get_consumption_log queries, straight from the database.

    Returned alongside the rows so the sandbox fits the draw rate over the window
    that was actually asked for, rather than re-deriving it from its own clock
    and quietly shifting every number.

    `days` means exactly that many days ending today, which is why the query uses
    a strict `>`: `>= CURRENT_DATE - 120` spans 121 calendar days, and dividing a
    121-day total by a 120-day denominator understates the draw rate.
    """
    row = _row(
        "SELECT (CURRENT_DATE - %s::int + 1) AS window_start, CURRENT_DATE AS window_end",
        (days,),
    )
    assert row is not None
    return str(row["window_start"]), str(row["window_end"])


def list_alerts() -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT part_no, description, uom, stock_on_hand, reorder_level,
               reorder_qty, vendor_code,
               reorder_level - stock_on_hand AS shortfall
        FROM parts
        WHERE stock_on_hand < reorder_level
        ORDER BY (stock_on_hand::float / NULLIF(reorder_level, 0)) ASC
        """
    )


def get_part(part_no: str) -> dict[str, Any] | None:
    return _row("SELECT * FROM parts WHERE part_no = %s", (part_no,))


def get_consumption_log(part_no: str, days: int = 120) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT consumed_on, qty, work_order, remarks
        FROM consumption_log
        WHERE part_no = %s AND consumed_on > CURRENT_DATE - %s::int
        ORDER BY consumed_on
        """,
        (part_no, days),
    )


def list_open_indents(part_no: str) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT i.indent_no, i.part_no, i.qty, i.raised_on, i.raised_by, i.status,
               c.consignment_no AS linked_consignment_no,
               c.status         AS linked_consignment_status,
               c.eta            AS linked_consignment_eta,
               c.qty            AS linked_consignment_qty
        FROM open_indents i
        LEFT JOIN consignments c ON c.against_indent = i.indent_no
        WHERE i.part_no = %s AND i.status = 'open'
        ORDER BY i.raised_on DESC
        """,
        (part_no,),
    )


def list_consignments(part_no: str) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT consignment_no, part_no, qty, against_indent, dispatched_on, eta, status
        FROM consignments
        WHERE part_no = %s AND status <> 'received'
        ORDER BY eta NULLS LAST
        """,
        (part_no,),
    )


def get_vendor_lead_times(vendor_code: str) -> list[dict[str, Any]]:
    return _rows(
        """
        SELECT vendor_code, vendor_name, vendor_email, order_ref, part_no,
               ordered_on, promised_days, actual_days
        FROM vendor_lead_times
        WHERE vendor_code = %s AND actual_days IS NOT NULL
        ORDER BY ordered_on DESC
        """,
        (vendor_code,),
    )


def get_vendor_for_part(part_no: str) -> dict[str, Any] | None:
    return _row(
        """
        SELECT DISTINCT v.vendor_code, v.vendor_name, v.vendor_email
        FROM parts p
        JOIN vendor_lead_times v ON v.vendor_code = p.vendor_code
        WHERE p.part_no = %s
        LIMIT 1
        """,
        (part_no,),
    )


# ---------------------------------------------------------------------------
# Writes - these are the irreversible half, gated by the harness
# ---------------------------------------------------------------------------


def next_indent_no() -> str:
    row = _row(
        """
        SELECT 'IND-' || to_char(CURRENT_DATE, 'YYYY') || '-' ||
               lpad((COALESCE(MAX(substring(indent_no from '[0-9]{4}$')::int), 0) + 1)::text, 4, '0')
               AS indent_no
        FROM open_indents
        WHERE indent_no LIKE 'IND-' || to_char(CURRENT_DATE, 'YYYY') || '-%%'
        """
    )
    if not row or not row.get("indent_no"):
        raise RuntimeError("could not allocate an indent number")
    return str(row["indent_no"])


def insert_indent(part_no: str, qty: int, raised_by: str) -> dict[str, Any]:
    indent_no = next_indent_no()
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO open_indents (indent_no, part_no, qty, raised_on, raised_by, status)
                VALUES (%s, %s, %s, CURRENT_DATE, %s, 'open')
                RETURNING indent_no, part_no, qty, raised_on, raised_by, status
                """,
                (indent_no, part_no, qty, raised_by),
            )
            created = cur.fetchone()
        conn.commit()
    return _jsonable(created)


def insert_run_log(
    session_id: str, part_no: str, outcome: str, detail: dict[str, Any]
) -> dict[str, Any]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO run_log (session_id, part_no, outcome, detail)
                VALUES (%s, %s, %s, %s)
                RETURNING id, session_id, part_no, outcome, logged_at
                """,
                (session_id, part_no, outcome, psycopg.types.json.Json(detail)),
            )
            created = cur.fetchone()
        conn.commit()
    created["logged_at"] = created["logged_at"].isoformat()
    return created


def list_run_log(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, session_id, part_no, outcome, detail, logged_at
                FROM run_log ORDER BY logged_at DESC LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
    for r in rows:
        r["logged_at"] = r["logged_at"].isoformat()
    return rows
