/**
 * How a run actually works, and where the harness ends and this project begins.
 *
 * Sits in the activity column before a run starts. That column is the single
 * biggest area on the page and it is empty on load, which is the first thing a
 * visitor sees; and "how does it work" is the question they ask straight after
 * "what is it". The two problems answer each other.
 */
import type { ConsoleState } from '../lib/events'

const STEPS: Array<[string, string]> = [
  ['Alert', 'A part drops below its reorder level. TRB-4417: 42 in stock, reorder at 60.'],
  ['Records', 'Pulled over MCP from a real Postgres — consumption log, open indents, consignments in transit, vendor lead times.'],
  ['Arithmetic', 'Tested Python runs in a sandbox: fits the daily draw rate, builds a lead-time distribution from what the vendor actually did, solves the stockout band, draws the chart.'],
  ['Four hypotheses', 'One subagent each, in parallel, each trying to prove the shortage is not real. Every verdict carries the evidence that produced it.'],
  ['Adjudication', 'Ordered rules in ordinary Python with unit tests — not a model call. It also generates the one line that would change the answer.'],
  ['Act, or do not', 'Genuine → the dossier goes to a human and the tool call is held. Paper → no action, recorded as an outcome.'],
]

/** Which step the run is on, from what the console already knows. */
function currentStep(state: ConsoleState): number {
  if (state.outcome || state.recommendation) return 5
  if (state.verdicts.length >= 4) return 4
  if (Object.keys(state.threads).some((t) => t !== 'main')) return 3
  if (state.sandboxReady || state.projection) return 2
  if (state.activity.length > 1) return 1
  return 0
}

export function Pipeline({ state }: { state?: ConsoleState }) {
  // Idle: a plain explainer. Mid-run: the same explainer with the current step
  // marked, which is what turns the empty half of the screen into something
  // that tells a first-time viewer what they are watching.
  const active = state ? currentStep(state) : -1

  return (
    <section className="panel pipeline">
      <header>
        <span>{state ? 'what is happening' : 'how a run works'}</span>
      </header>
      <div className="body">
        <ol>
          {STEPS.map(([title, detail], i) => (
            <li
              key={title}
              className={i === active ? 'is-now' : i < active ? 'is-done' : ''}
            >
              <span className="n mono">{i < active ? '\u2713' : String(i + 1).padStart(2, '0')}</span>
              <div>
                <span className="t">{title}</span>
                <span className="d">{detail}</span>
              </div>
            </li>
          ))}
        </ol>

        {state === undefined && (
        <div className="boundary">
          <p>
            <span className="t">TrueForge provides</span> the agent loop, the MCP
            calls, the sandbox, the parallel subagent threads, the approval pause
            and session persistence. None of it is reimplemented here.
          </p>
          <p>
            <span className="t">This project provides</span> the MCP server over
            Postgres, the skill the agent follows, the analysis code that runs in
            the sandbox, the deterministic adjudication, and this console.
          </p>
        </div>
        )}

        {state === undefined && (
        <p className="cta">Pick one of the two alerts, top right, to replay a real run.</p>

        )}

        {state === undefined && (
        <p className="source">
          Source, tests and the build log:{' '}
          <a href="https://github.com/ANMOLGUPTA-24/stores-triage" target="_blank" rel="noreferrer">
            github.com/ANMOLGUPTA-24/stores-triage
          </a>
        </p>
        )}
      </div>
    </section>
  )
}
