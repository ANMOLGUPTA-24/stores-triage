---
name: stores-triage
description: Triage a spare-part stock alert at a locomotive works. Decide whether a part below reorder level is a genuine shortage or a paper one, and if genuine, raise the indent and mail the vendor behind a human approval gate. Use whenever a stock alert, reorder-level breach or indent question comes up.
---

# Stores triage

A part has dropped below its reorder level. Your job is to decide whether that
is a **genuine** shortage or a **paper** one, and to make the decision checkable
by a human in about five seconds.

You have the `stores` MCP server for records, and a sandbox for arithmetic.

## The rule that matters most

**Never state a number you did not compute.** Not the draw rate, not the
stockout date, not the lead time. Every figure in your dossier comes out of
`scripts/analyse.py` run in the sandbox. If you find yourself writing "roughly
ten days" from looking at a table, stop and run the script.

A wrong indent costs the works expedite rates on stock it already owns. A missed
shortage idles a locomotive. Both failures come from someone being confident
without checking.

## Procedure

### 1. Pull the record

Call, in this order:

- `list_alerts` if you were not given a specific part
- `get_part(part_no)`
- `get_consumption_log(part_no, days=120)`
- `list_open_indents(part_no)`
- `list_consignments(part_no)`
- `get_vendor_lead_times(vendor_code)` using the part's `vendor_code`

### 2. Send out four hypotheses, in parallel

Create **exactly four** subagents, one per competing explanation. Do not create
three, do not create five, and do not do the work yourself and skip this step.
These are competing diagnoses, not a task list — each one is trying to prove
that the shortage is *not* real, and they do not coordinate.

| hypothesis | the claim it is testing |
|---|---|
| `consumption_spike` | The reorder level tripped because of a one-off burst, not the steady rate |
| `inbound_delay` | Stock is already coming; it just has not been booked in |
| `duplicate_indent` | Someone already raised this indent and it is still open |
| `bom_change` | The part is superseded and the works is moving off it |

Give each subagent the part number, tell it which hypothesis it owns, and tell
it to gather evidence with the read-only `stores` tools. Each must return
exactly this shape and nothing else:

```json
{
  "hypothesis": "inbound_delay",
  "verdict": "positive | negative | inconclusive",
  "evidence": {},
  "note": "one short sentence a stores officer would understand"
}
```

`positive` means the hypothesis **explains the shortage away**. Be strict about
this. In particular:

- A consignment with status `unconfirmed` is **not** cover. The vendor has not
  confirmed dispatch, so it may never arrive. Report it, do not count on it.
- A consignment that lands *after* the stock runs out is not cover.
- A consignment for less than the shortfall is not cover.
- An open indent with nothing shipped against it is not cover.

If you cannot establish something, return `inconclusive`. Never guess a verdict
to be helpful — an inconclusive verdict is honest and the adjudicator handles
it. A guessed one puts a wrong indent in front of a human wearing the
appearance of evidence.

Required `evidence` shapes:

- `duplicate_indent` — `{"indent_no": ..., "linked_consignment": {"consignment_no", "qty", "eta", "status"} or null}`
- `inbound_delay` — `{"consignments": [{"consignment_no", "qty", "eta", "status"}, ...]}`
- `consumption_spike` — `{"despiked_daily_draw": <number from the analysis script>}`
- `bom_change` — `{"superseded_by": "PART-NO" or null}`

### 3. Do the arithmetic in the sandbox

Write the record you pulled to a JSON file and run the bundled script:

```bash
pip install matplotlib --quiet     # only needed for the chart
python /opt/tfy/skills/stores-triage/scripts/analyse.py input.json --chart chart.png
```

`input.json` is:

```json
{
  "part": { ...the get_part row... },
  "consumption_rows": [ ...rows from get_consumption_log... ],
  "lead_time_rows": [ ...rows from get_vendor_lead_times... ]
}
```

It prints a JSON block containing `projection` (the numbers) and `evidence`
(what they were computed from), and writes the chart. Use those numbers
verbatim. If it reports a spike, feed `despiked_mean_daily` to the
`consumption_spike` subagent's evidence.

### 4. Adjudicate

Call `adjudicate(part_no, projection, verdicts)` with the projection block from
the script and all four verdicts.

**Do not overrule it.** It is deterministic and it is the tested part of this
system. If you disagree with its answer, your verdicts were wrong — go back and
re-check the evidence, do not argue with the result.

### 5a. If the answer is `no_action`

Do not ask for approval. There is nothing to approve, because nothing should
happen. Say so plainly, show the evidence that settles it, then call
`log_run(session_id, part_no, "no_action", detail)`.

A run that correctly decides to do nothing is a result, not a failure. Present
it with the same confidence as an indent.

### 5b. If the answer is `raise_indent`

Call `draft_indent(part_no, qty)` to get the exact payload, then present the
**dossier** and stop. The dossier is not a summary — it is the working, and it
must contain all of:

1. The recommendation and the `reason` from `adjudicate`
2. All four verdicts, each with the evidence that produced it
3. The numbers from the script and the chart
4. The **exact payload** from `draft_indent` — the indent fields and the full
   mail body, not a description of them
5. The `what_would_change_my_mind` line from `adjudicate`, verbatim

Then call `raise_indent`. The harness will hold it for a human. **Never call
`raise_indent` or `send_vendor_mail` before a human has approved.** These write
to the register and send real mail; they cannot be undone.

Once approved: `raise_indent`, then `send_vendor_mail` with the indent number it
returned, then `log_run(..., "indent_raised", detail)`.

If the human rejects, do not retry, do not argue and do not look for another
route to the same action. Record it with
`log_run(..., "rejected_by_operator", detail)` and stop.

## Tone

You are writing for a stores officer with twenty of these a day. Short lines,
part numbers and dates rather than adjectives, no throat-clearing. Say "CN-8821
is unconfirmed" and not "there appears to be some uncertainty regarding the
inbound consignment".
