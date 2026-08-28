# Evaluation

`potential impact` is easy to assert and hard to believe, so this measures it.

```bash
.venv/bin/python evals/run_eval.py
```

## What it does

Runs the same deterministic adjudication the agent calls, over **16 labelled
scenarios whose right answer is known by construction** — not by asking the
adjudicator what it thinks. A consignment that is confirmed in transit, covers
the shortfall and lands before the stock runs out *is* cover, so that alert is
paper. One that is unconfirmed, short-shipped, overdue or lands too late is not,
so that alert is genuine.

Half the cases differ from a paper case by **one field** — a status, a quantity,
a date — because that is exactly where a stores officer working across three
systems at forty minutes an alert makes the mistake this project exists to catch.

No model is involved. That is the point: the decision is testable code, so its
error rate is a measured number rather than a claim.

## Result

```
correct: 16/16  (100%)
  wrong raises   (buys covered stock): 0
  missed shortages (bin runs empty)  : 0
paper alerts correctly refused: 5/5
```

## Why that number is worth anything

A perfect score on scenarios the author wrote proves nothing on its own — they
could simply describe whatever the code already does. So the suite breaks the
rules on purpose and checks it notices:

```
mutation checks — each should be caught
  overdue consignments count as cover          caught, 2 scenario(s) fail
  any ETA counts as cover, however late        caught, 3 scenario(s) fail
2/2 mutations caught
```

The first mutation is not hypothetical. It is the bug this project actually
shipped and fixed a day before the deadline: `_lands_in_time` accepted ETAs in
the past, so an overdue-but-still-in-transit consignment counted as cover and
the agent would have recommended doing nothing while citing a delivery that
never turned up. A mutation that survived would mean the scenario set was
missing a case, not that the rule did not matter.

## The consequence, in the works's own units

The harness prices both kinds of error in what the works actually pays, rather
than in invented currency:

- a **wrong raise** commits `reorder_qty` units of working capital against stock
  that was already covered, plus whatever expedite premium the order carries;
- a **missed shortage** leaves the bin empty between the day it runs dry and the
  day the vendor delivers — days of exposure, which is when a locomotive stops.

Both are zero on the current rules. When they are not, the failures print in
full with the scenario, the reason it should have gone the other way, and what
the adjudicator said instead.
