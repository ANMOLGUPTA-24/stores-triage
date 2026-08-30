# Submission form — answers to paste

Plain text, no markdown: Google Forms renders none of it.
Short on purpose — a judge is reading fifty of these.

---

## 1. What does your project do?

A spare part drops below its reorder level at a locomotive works and an alert
fires. The stores officer then has to answer a question the alert cannot: is this
real? The evidence sits in three systems that do not talk to each other — the
consumption log, the open indents, and the consignments in transit — and he gets
twenty of these a day.

Both mistakes cost. A duplicate indent against stock already in transit means
paying expedite rates on stock the works already owns. A missed shortage idles a
locomotive.

The agent decides which it is, then either raises the indent and mails the vendor
behind a human approval gate, or concludes nothing should happen — and shows its
working either way.

The two demo alerts are indistinguishable from the alert alone: 9.4 days of stock
against 9.5. One is genuine. The other is already covered, and the agent correctly
does nothing. That is the harder half of the problem and the half that saves the
money.

---

## 2. How did you use TrueForge in your project?

TrueForge runs the agent loop, the MCP calls, the sandbox, the parallel subagent
threads, the approval pause and the session. I reimplemented none of it.

I brought three things: a real MCP server (12 tools over Postgres, bearer auth,
destructiveHint on the two irreversible ones), the stores-triage skill with the
analysis code that runs in the sandbox, and adjudicate() — four ordered rules in
ordinary Python with unit tests. The agent gathers evidence and calls tools; it
does not get a vote on the answer.

A run: four subagents dispatched at once, one per competing explanation, each
trying to prove the shortage is NOT real. analyse.py runs in the sandbox and pulls
its own record over Code Mode, so the data never passes through the model. Then
adjudicate decides, and the harness holds raise_indent for a human — and holds
send_vendor_mail again, separately, after approval.

Two settings that mattered. requireApprovalForTools is narrowed to the two
irreversible tools; the default would also hold log_run, so the agent would wait
for permission to record that it had decided to do nothing. And askUserQuestions
is disabled — left on, the agent reached the right answer and then asked for
permission in prose, with no evidence and no held call to gate. That is the
confirm() box this project exists to replace.

Both runs are live. TRB-4417 holds at both gates. BRK-2290 returns no_action in
one unbroken 101-second turn. A third run died mid-way on a rate limit and the
session came back with its four verdicts intact.

---

## 3. How did you use Qodo in your project?

Every substantive change went through a reviewed pull request — nine of them. The
only non-merge commit on main is the initial scaffold.

Qodo raised 11 High-severity findings across three PRs and every one was fixed;
none dismissed. Two would have broken the demo outright. "Approval gate cannot
start": the skill both forbade calling raise_indent before approval and told the
agent to call it, so an obedient agent would never create anything to approve.
"Gate instructions deadlock agent": three places still said never to call the
gated tools until a human approved, which means waiting forever for an approval
nothing was ever held for.

Three more were arithmetic that would have put wrong numbers in front of an
operator — a p20 cutoff labelled p10, consumption rows counted as days, and a
divide-by-zero that crashed on the most urgent alert there is.

I disagreed with exactly one Medium finding and wrote the reasoning on the PR
rather than ignoring it.

The habit it forced is why the repo has 70 Python and 32 TypeScript tests plus an
evaluation that scores the adjudicator 16/16 on labelled cases — and proves the
suite has teeth by breaking the rules on purpose and checking it notices.

---

## Blog link

Publish notes/blog-post.md anywhere and paste the URL.

---

## 4. Which TrueForge feature was the most useful, and why?

The approval pause, by a distance — because it is the one thing I would have got
subtly wrong on my own.

Marking a tool destructiveHint and naming it in requireApprovalForTools is all it
takes: the harness intercepts the call, holds it, and shows the operator a pending
action. Nothing is written while it waits. The part I did not appreciate until I
used it is that approving RESUMES the call the agent already made rather than
asking the agent to make it again. A hand-rolled version would almost certainly
have re-issued it and raised two indents.

Dynamic subagents are a close second. Four hypotheses investigating in parallel,
each with its own threadId in the event stream, is what makes the reasoning
legible on screen instead of being a wall of prose.

---

## 5. Where did you get stuck, and what would you improve about the developer experience?

The local sandbox on Linux cannot reach the network, and the error tells you the
wrong story. It surfaces as "Failed to pip install pydantic", which sends you
looking for an offline-wheels workaround. That is not the problem. SRT reaches its
filtering proxy over a Unix socket at os.tmpdir()/claude-http-<id>.sock, but
ALLOW_READ_BY_PLATFORM.linux does not include /tmp — so the sandboxed process
cannot see the socket and every connection dies with "Proxy CONNECT aborted", even
though pypi.org is on your own allowed-domain list. On Linux this makes the local
sandbox unusable, and it takes skills with it, because skills require a sandbox.
It cost me three days. Adding /tmp, or putting the socket somewhere already
allow-read, fixes it.

Three smaller ones. The sandbox child environment is built from scratch, so
PIP_NO_INDEX and PIP_FIND_LINKS set on the harness process silently never arrive.
There is no backoff on a 429 — four subagents dispatching at once is eight
requests in ten seconds, and on a per-minute cap that kills the whole turn; the
session surviving is excellent, but the turn should be able to wait. And skills
materialise at /opt/tfy/skills/<name> remotely but relative to the working
directory locally, with no documented way to ask which.

One default I would change: ask_user_questions is on by default, and it quietly
defeats approval gating. My agent reached the correct decision and then asked for
permission in prose — no evidence, no payload, and no held call for the harness to
gate. If an agent has gated tools, that tool should probably be off.

---

## 6. How useful was Qodo's code review feedback?  →  5 stars

---

## 7. What was the most useful or frustrating part of working with Qodo, and what would you change?

Most useful: it reviewed my prose, not just my code. Two of its findings were
logical contradictions inside the agent's instruction file — one where the skill
both forbade calling a tool and told the agent to call it, another where three
separate places deadlocked the approval gate. Neither is a code defect any linter
or type checker would ever see, and both would have broken the live demo. I did
not expect a code reviewer to catch that.

Also worth saying: 11 High-severity findings and zero false positives. Nothing was
noise, so I never learned to skim it.

What I would change: findings are reported per instance rather than per class. It
flagged one hard-coded font size outside my type tokens — correct — while the same
commit had introduced six more of exactly the same violation. Fixing only what was
flagged would have satisfied the review while the actual problem grew. Something
like "this pattern occurs 7 times in this diff" would have pointed me at the class
instead of the symptom.

The rule-violation checks derived from my own project constitution were the most
valuable and the most literal. One flagged my GitHub username in a Pages URL as
exposed personal data, which is not removable — GitHub derives the URL from the
account. I replied on the PR rather than complying, which is the right escape
hatch, but a way to mark a rule as "does not apply to generated URLs" would save
that round trip.
