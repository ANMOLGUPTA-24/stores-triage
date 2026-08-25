-- Stores Triage - spare-part stock schema.
-- Synthetic data only. No real vendor, employer or personal data, ever.

CREATE TABLE parts (
    part_no        TEXT PRIMARY KEY,
    description    TEXT        NOT NULL,
    uom            TEXT        NOT NULL,
    stock_on_hand  INTEGER     NOT NULL CHECK (stock_on_hand >= 0),
    reorder_level  INTEGER     NOT NULL CHECK (reorder_level >= 0),
    reorder_qty    INTEGER     NOT NULL CHECK (reorder_qty > 0),
    vendor_code    TEXT        NOT NULL
);

CREATE TABLE consumption_log (
    id          BIGSERIAL PRIMARY KEY,
    part_no     TEXT      NOT NULL REFERENCES parts(part_no),
    consumed_on DATE      NOT NULL,
    qty         INTEGER   NOT NULL CHECK (qty >= 0),
    work_order  TEXT,
    remarks     TEXT
);
CREATE INDEX ON consumption_log (part_no, consumed_on);

CREATE TABLE open_indents (
    indent_no  TEXT PRIMARY KEY,
    part_no    TEXT    NOT NULL REFERENCES parts(part_no),
    qty        INTEGER NOT NULL CHECK (qty > 0),
    raised_on  DATE    NOT NULL,
    raised_by  TEXT    NOT NULL,
    status     TEXT    NOT NULL CHECK (status IN ('open', 'closed', 'cancelled'))
);
CREATE INDEX ON open_indents (part_no, status);

CREATE TABLE consignments (
    consignment_no TEXT PRIMARY KEY,
    part_no        TEXT    NOT NULL REFERENCES parts(part_no),
    qty            INTEGER NOT NULL CHECK (qty > 0),
    against_indent TEXT,
    dispatched_on  DATE,
    eta            DATE,
    -- unconfirmed: vendor has not confirmed dispatch, so it is NOT reliable cover.
    status         TEXT    NOT NULL CHECK (status IN ('unconfirmed', 'in_transit', 'delayed', 'received'))
);
CREATE INDEX ON consignments (part_no, status);

CREATE TABLE vendor_lead_times (
    id            BIGSERIAL PRIMARY KEY,
    vendor_code   TEXT    NOT NULL,
    vendor_name   TEXT    NOT NULL,
    vendor_email  TEXT    NOT NULL,
    order_ref     TEXT    NOT NULL,
    part_no       TEXT    NOT NULL REFERENCES parts(part_no),
    ordered_on    DATE    NOT NULL,
    promised_days INTEGER NOT NULL CHECK (promised_days > 0),
    actual_days   INTEGER CHECK (actual_days > 0)
);
CREATE INDEX ON vendor_lead_times (vendor_code);

-- Run log: what the agent did, in order. "no action" is a first-class outcome.
CREATE TABLE run_log (
    id         BIGSERIAL PRIMARY KEY,
    session_id TEXT        NOT NULL,
    part_no    TEXT        NOT NULL REFERENCES parts(part_no),
    outcome    TEXT        NOT NULL CHECK (outcome IN ('indent_raised', 'no_action', 'rejected_by_operator')),
    detail     JSONB       NOT NULL,
    logged_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
