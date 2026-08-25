-- Synthetic seed for the two demo runs. Deterministic: setseed() fixes the noise.
-- Vendors and part numbers are invented. Nothing here comes from a real works.
-- All dates are relative to CURRENT_DATE so the demo reproduces on any day.

SELECT setseed(0.4417);

INSERT INTO parts (part_no, description, uom, stock_on_hand, reorder_level, reorder_qty, vendor_code) VALUES
  -- Run A: genuine shortage. Steady draw, nothing reliable inbound.
  ('TRB-4417', 'Traction motor brush holder, Type 4',  'nos', 42,  60, 200, 'V-3301'),
  -- Run B: paper shortage. Looks identical from the alert alone.
  ('BRK-2290', 'Brake block, composite, 320mm',        'nos', 55,  80, 300, 'V-3308'),
  -- Background stock, comfortably above reorder level.
  ('LUB-1105', 'Axle box lubricant, grade EP2',        'ltr', 890, 250, 600, 'V-3301'),
  ('FLT-3320', 'Compressor intake filter element',     'nos', 310, 120, 400, 'V-3308');

-- ---------------------------------------------------------------------------
-- Consumption: 120 days. Sunday is a non-issue day at the works.
-- ---------------------------------------------------------------------------
INSERT INTO consumption_log (part_no, consumed_on, qty, work_order, remarks)
SELECT 'TRB-4417', d::date,
       CASE WHEN EXTRACT(dow FROM d) = 0 THEN 0
            ELSE GREATEST(0, ROUND(5.3 + (random() - 0.5) * 3.0))::int END,
       'WO-' || to_char(d, 'YYYYMMDD') || '-TRB',
       NULL
FROM generate_series(CURRENT_DATE - INTERVAL '119 days', CURRENT_DATE - INTERVAL '1 day', INTERVAL '1 day') d;

INSERT INTO consumption_log (part_no, consumed_on, qty, work_order, remarks)
SELECT 'BRK-2290', d::date,
       CASE WHEN EXTRACT(dow FROM d) = 0 THEN 0
            ELSE GREATEST(0, ROUND(6.9 + (random() - 0.5) * 3.4))::int END,
       'WO-' || to_char(d, 'YYYYMMDD') || '-BRK',
       NULL
FROM generate_series(CURRENT_DATE - INTERVAL '119 days', CURRENT_DATE - INTERVAL '1 day', INTERVAL '1 day') d;

INSERT INTO consumption_log (part_no, consumed_on, qty, work_order, remarks)
SELECT p.part_no, d::date,
       CASE WHEN EXTRACT(dow FROM d) = 0 THEN 0
            ELSE GREATEST(0, ROUND(3.0 + (random() - 0.5) * 2.0))::int END,
       'WO-' || to_char(d, 'YYYYMMDD') || '-' || substr(p.part_no, 1, 3),
       NULL
FROM generate_series(CURRENT_DATE - INTERVAL '59 days', CURRENT_DATE - INTERVAL '1 day', INTERVAL '1 day') d
CROSS JOIN (VALUES ('LUB-1105'), ('FLT-3320')) AS p(part_no);

-- ---------------------------------------------------------------------------
-- Run B's paper trail: an indent already raised, and stock already moving.
-- ---------------------------------------------------------------------------
INSERT INTO open_indents (indent_no, part_no, qty, raised_on, raised_by, status) VALUES
  ('IND-2026-0731', 'BRK-2290', 300, CURRENT_DATE - 7,  'stores.officer.2', 'open'),
  ('IND-2026-0688', 'FLT-3320', 400, CURRENT_DATE - 34, 'stores.officer.1', 'closed');

INSERT INTO consignments (consignment_no, part_no, qty, against_indent, dispatched_on, eta, status) VALUES
  -- Run B: real cover. Dispatched, confirmed, lands before stockout.
  ('CN-9104', 'BRK-2290', 300, 'IND-2026-0731', CURRENT_DATE - 5, CURRENT_DATE + 3, 'in_transit'),
  -- Run A: consignment 8821 is NOT cover - the vendor has not confirmed dispatch.
  -- This is what the agent must flag as "what would change my mind".
  ('CN-8821', 'TRB-4417', 200, NULL,            NULL,             CURRENT_DATE + 2, 'unconfirmed'),
  ('CN-8794', 'FLT-3320', 400, 'IND-2026-0688', CURRENT_DATE - 30, CURRENT_DATE - 9, 'received');

-- ---------------------------------------------------------------------------
-- Vendor performance history -> lead-time distribution built in the sandbox.
-- ---------------------------------------------------------------------------
INSERT INTO vendor_lead_times (vendor_code, vendor_name, vendor_email, order_ref, part_no, ordered_on, promised_days, actual_days)
SELECT 'V-3301', 'Meridian Traction Supplies', 'vendor-meridian@example.invalid',
       'PO-2026-' || lpad(n::text, 4, '0'), 'TRB-4417',
       CURRENT_DATE - (n * 27),
       21,
       GREATEST(15, ROUND(26 + (random() - 0.5) * 18.0))::int
FROM generate_series(1, 14) n;

INSERT INTO vendor_lead_times (vendor_code, vendor_name, vendor_email, order_ref, part_no, ordered_on, promised_days, actual_days)
SELECT 'V-3308', 'Northgate Friction Products', 'vendor-northgate@example.invalid',
       'PO-2026-' || lpad((100 + n)::text, 4, '0'), 'BRK-2290',
       CURRENT_DATE - (n * 24),
       18,
       GREATEST(13, ROUND(20 + (random() - 0.5) * 10.0))::int
FROM generate_series(1, 14) n;
