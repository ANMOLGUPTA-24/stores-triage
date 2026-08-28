import type { ConsoleState } from '../lib/events'

/**
 * What is happening right now, shown while a run is in flight.
 *
 * Between the first tool call and the recommendation the right column has
 * nothing to put in it, and that is exactly when a first-time viewer is trying
 * to work out what they are watching. These are the same steps the front door
 * lists, with the current one marked.
 */
const STEPS: Array<[string, string]> = [
  ['Alert', 'A part drops below its reorder level.'],
  ['Records', 'Pulled over MCP from a real Postgres — consumption log, open indents, consignments in transit, vendor lead times.'],
  ['Arithmetic', 'Tested Python runs in a sandbox: fits the daily draw rate, builds a lead-time distribution, solves the stockout band, draws the chart.'],
  ['Four hypotheses', 'One subagent each, in parallel, each trying to prove the shortage is not real.'],
  ['Adjudication', 'Ordered rules in ordinary Python with unit tests — not a model call.'],
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

export function Pipeline({ state }: { state: ConsoleState }) {
  const active = currentStep(state)

  return (
    <section className="panel pipeline">
      <header>
        <span>what is happening</span>
      </header>
      <div className="body">
        <ol>
          {STEPS.map(([title, detail], i) => (
            <li key={title} className={i === active ? 'is-now' : i < active ? 'is-done' : ''}>
              <span className="n mono">{i < active ? '✓' : String(i + 1).padStart(2, '0')}</span>
              <div>
                <span className="t">{title}</span>
                <span className="d">{detail}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  )
}
