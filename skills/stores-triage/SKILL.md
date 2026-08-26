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

You were given the part number, so skip `list_alerts`. Two steps, because the
third call needs a value the first one returns:

1. `get_part(part_no)` and `get_consumption_log(part_no, days=120)` together
2. `get_vendor_lead_times(vendor_code)` using the `vendor_code` from `get_part`

Do not fetch indents or consignments yourself. Those are the subagents' evidence
and fetching them twice wastes a call each.

### 2. Do the arithmetic in the sandbox

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
verbatim.

**This runs before the subagents on purpose.** Two of them need its output:
`consumption_spike` needs `despiked_mean_daily`, and `inbound_delay` has to know
`days_to_stockout_p10` to judge whether an ETA lands in time. Dispatching them
first would force both to guess, and a guessed verdict wearing the appearance of
evidence is the exact failure this system exists to prevent.

### 3. Send out four hypotheses, in parallel

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

Give each subagent the part number, the `projection` block from step 2, tell it
which hypothesis it owns, **and name the single tool it needs**:

| hypothesis | its one tool |
|---|---|
| `duplicate_indent` | `list_open_indents` |
| `inbound_delay` | `list_consignments` |
| `consumption_spike` | none — you already have `despiked_mean_daily` from step 2 |
| `bom_change` | `get_part` |

**Each subagent makes exactly one tool call and then returns its verdict.** Not
two, not a follow-up to check something. If the one call does not settle it, the
verdict is `inconclusive` and the adjudicator handles it. Model quota is finite
and a subagent that goes exploring spends the budget the rest of the run needs.

Each must return exactly this shape and nothing else:

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

### 4. Adjudicate

Call `adjudicate(part_no, projection, verdicts)` with the projection block from
the script and all four verdicts.

**Do not overrule it.** It is deterministic and it is the tested part of this
system. If you disagree with its answer, your verdicts were wrong — go back and
re-check the evidence, do not argue with the result.

### 5a. If the answer is `no_action`

Do not ask for approval. There is nothing to approve, because nothing should
happen. Say so plainly, show the evidence that settles it, then call
`log_run(part_no, "no_action", detail)`. You do not need a session id; the
server allocates one.

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

Then call `raise_indent`. **The call itself is what creates the approval
request** — the harness intercepts it, holds it, and shows the operator the
pending action. Nothing is written while it is held.

Do not wait for approval before calling it; there is nothing for the operator to
approve until you do. And do not call it twice: when the operator approves, the
harness resumes the call you already made. A second call would raise a second
indent.

`send_vendor_mail` is gated separately, so approving the indent does not
pre-approve the mail. Expect a second pause, and pass the `indent_no` that
`raise_indent` returned along with **the same `needed_by` date that appeared in
the dossier** — the operator approved that exact wording, and the outgoing mail
is composed from what you pass here.

Then `log_run(part_no, "indent_raised", detail)`.

If the human rejects, do not retry, do not argue and do not look for another
route to the same action. Record it with
`log_run(part_no, "rejected_by_operator", detail)` and stop.

## Economy

The whole run must fit in under twenty model calls. Budget:

- 2 to read the record (part + log, then vendor lead times)
- 2 for the sandbox: write `input.json`, run `analyse.py`
- 1 to dispatch all four subagents at once
- 4 to 8 for the subagents themselves
- 1 for `adjudicate`
- 1 for `draft_indent`
- 1 to present the dossier

Never re-read something you already have. Never call a tool to check a number
the analysis already returned. If you catch yourself confirming, stop.

## Tone

You are writing for a stores officer with twenty of these a day. Short lines,
part numbers and dates rather than adjectives, no throat-clearing. Say "CN-8821
is unconfirmed" and not "there appears to be some uncertainty regarding the
inbound consignment".
