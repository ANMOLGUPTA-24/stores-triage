# Demo video storyboard

Three minutes, two runs, against §0b. Record Saturday evening, submit Sunday
morning. Every shot below has a source already working — nothing here needs to
be invented on the day.

Quota reality: Gemini Flash allows 20 model calls a day, and a full run costs
~15-18. **One live run per day.** So Run A and Run B are recorded on separate
days, or one is recorded live and the other replayed in the console. The console
replays a recorded event stream through the same reducer, so a replayed run is
not a mock-up — say so on camera rather than hiding it.

---

## 0:00-0:25 — the problem

Screen: the two alerts side by side in the console, before anything runs.

Say: a part drops below reorder level. Twenty of these a day, forty minutes each
across three systems. Raise a duplicate indent against stock already in transit
and the works pays expedite rates on stock it already owns. Miss a real shortage
and a locomotive sits idle.

Point at the two rows: **9.4 days and 9.5 days of stock left. From the alert
alone these are the same problem.** They are not.

Figures for this seed, computed live in the sandbox — quote these, do not
estimate:

| | TRB-4417 (Run A) | BRK-2290 (Run B) |
|---|---|---|
| draw | 4.48/day | 5.79/day |
| runs dry | 9.4 days (7.7 at the fast end) | 9.5 days (7.9) |
| vendor p80 | 29.8 days | 23.0 days |
| exposure if nothing is done | 20 days with no stock | covered by CN-9104 |

## 0:25-1:05 — Run A, the investigation

Screen: activity stream on the left filling up, hypothesis board on the right.

Beats to show, in order:
- **A1** Tool calls landing in monospace — `get_part`, `get_consumption_log`
- **A2** **Four subagents appearing at once** on the board, each "investigating"
- **A3** `*** SANDBOX UP ***` in the stream
- **A4** Verdicts arriving: three negative, `inbound_delay` positive with CN-8821

Say: four competing explanations, one subagent each, running in parallel. Every
one of them is trying to prove the shortage is *not* real. Ruling all four out
is what makes it real. This is differential diagnosis, not a task list.

## 1:05-1:45 — Run A, the gate

Screen: the dossier card. Let it sit. Do not scroll fast.

Show, in this order:
- **G1** The header goes amber — **"blocked on you"** in the top bar at the same time
- **G2** The numbers, and say they came out of Python in the sandbox, not the model
- **G3** The chart — the **20-day** stretch with no stock, shaded, between
  running dry and the vendor delivering (the chart labels it)
- **G4** Scroll to the **full mail body**, verbatim, not a summary
- **G5** The counterfactual: *"if CN-8821 is confirmed and lands by
  **2026-08-30**, do not raise this indent"*

Say: the harness gives us the pause. The dossier is ours. An approval is only
worth anything if the human can check it in five seconds — so the gate carries
the queries, the code, the numbers, the exact payload, and the one line that
would change the answer.

Then click **Approve**. Indent raised, vendor mailed, logged.

## 1:45-2:35 — Run B, the point

Screen: second alert. Same shape.

Say up front: this one looks identical. Same shortfall, same ten days.

Beats:
- **B1** Same four subagents dispatched
- **B2** `duplicate_indent` **positive** — IND-2026-0731, raised seven days ago
- **B3** `inbound_delay` **positive** — CN-9104, in transit, lands **2026-08-31**
- **B4** Recommendation: **no action**

Point at the screen and say: **there is no amber anywhere, and no Approve
button.** Nothing to approve, because nothing should happen. The run log records
"no action" as an outcome, not an error.

Say: the reason this is trustworthy is that the decision is not the model's
opinion. `adjudicate` is deterministic code with unit tests, including this
exact case. Run B passes in CI without a model involved at all.

## 2:35-3:00 — where the harness fits

Say, over the run log:
- TrueForge runs the loop, the MCP calls, the sandbox, the subagent threads and
  the approval pause. We did not reimplement any of it.
- Our MCP server is a real server over a real Postgres.
- The numbers come from tested Python in the sandbox.
- The two irreversible tools carry `destructiveHint`, so the harness holds them.

Close on: the agent's job is to gather evidence and call tools. The maths and
the judgment are code you can read and test.

Then, on the last card, say it and show it:

> **You can drive both of these yourself — anmolgupta-24.github.io/stores-triage**

Worth a beat of its own. A judge who can click through the gate themselves is
not taking the video's word for any of it, and it costs them a minute rather
than a clone, a Postgres, a harness and an API key.

---

## Before recording

**The dates below are filled from the seed created on 2026-08-28.** They are
correct as long as you do not re-seed. The seed is `CURRENT_DATE`-relative, so
re-seeding on a different day shifts every one of them — the offsets, which do
not move, are:

| | offset from the seed day | value for the 2026-08-28 seed |
|---|---|---|
| CN-8821 ETA (Run A, unconfirmed) | seed + 2 | **2026-08-30** |
| CN-9104 ETA (Run B, in transit) | seed + 3 | **2026-08-31** |
| IND-2026-0731 raised (Run B) | seed − 7 | **2026-08-21** |

If you re-seed, re-run the query in the checklist below and adjust.

- [ ] **Check the database is clean, and re-seed only if it is not.**

      ```
      docker exec stores-triage-db psql -U stores -d stores \
        -c "select indent_no, part_no from open_indents" -c "select count(*) from run_log"
      ```

      Two indents (`IND-2026-0688` closed, `IND-2026-0731` open) and an empty run
      log is the state to film in. Anything else is residue from a practice run —
      an indent the agent already raised, or a logged outcome — and Run A will
      then find its own indent open and reason about it.

      Re-seed **only** in that case:
      `docker compose down -v && docker compose up -d --wait`

      Re-seeding is not free: the seed is `CURRENT_DATE`-relative and fixed at
      volume-creation time, so seeding on a new day shifts every ETA and the date
      table above has to be redone. As long as the seed is fresher than the ETAs
      it quotes, leaving it alone is the safer move.

      This is what protects beats **A4**, **G5** and **B3** specifically: all
      three name a consignment ETA out loud, and an overdue ETA does not just
      look stale — since `_lands_in_time` stopped counting overdue stock as
      cover, a stale volume flips **B3** and turns Run B into an indent, which
      destroys the whole Run A / Run B contrast the video is built on.
- [ ] Confirm both runs still reach the right verdict after re-seeding
- [ ] **Only if you re-seeded**, re-read the ETAs and update the table above:
      `docker exec stores-triage-db psql -U stores -d stores -c \
       "select consignment_no, eta, status from consignments;"`

## Redaction checklist, before recording

- [ ] No API keys on screen — TrueForge Settings tab closed
- [ ] Terminal scrollback cleared of any key or token
- [ ] `.env` not open in any editor
- [ ] Vendor addresses are the `.invalid` ones
- [ ] No personal email in any frame
- [ ] Browser tabs and bookmarks bar not showing anything personal

## Footage already captured

- Console empty state, both runs, gate held, Run B "no action" — screenshots
- Chart PNG for TRB-4417, generated by `analyse.py`
- Live harness log showing the gate holding against real tools
EOF
