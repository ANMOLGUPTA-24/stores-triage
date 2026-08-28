/**
 * How a run actually works, and where the harness ends and this project begins.
 *
 * Sits in the activity column before a run starts. That column is the single
 * biggest area on the page and it is empty on load, which is the first thing a
 * visitor sees; and "how does it work" is the question they ask straight after
 * "what is it". The two problems answer each other.
 */
const STEPS: Array<[string, string]> = [
  ['Alert', 'A part drops below its reorder level. TRB-4417: 42 in stock, reorder at 60.'],
  ['Records', 'Pulled over MCP from a real Postgres — consumption log, open indents, consignments in transit, vendor lead times.'],
  ['Arithmetic', 'Tested Python runs in a sandbox: fits the daily draw rate, builds a lead-time distribution from what the vendor actually did, solves the stockout band, draws the chart.'],
  ['Four hypotheses', 'One subagent each, in parallel, each trying to prove the shortage is not real. Every verdict carries the evidence that produced it.'],
  ['Adjudication', 'Ordered rules in ordinary Python with unit tests — not a model call. It also generates the one line that would change the answer.'],
  ['Act, or do not', 'Genuine → the dossier goes to a human and the tool call is held. Paper → no action, recorded as an outcome.'],
]

export function Pipeline() {
  return (
    <section className="panel pipeline">
      <header>
        <span>how a run works</span>
      </header>
      <div className="body">
        <ol>
          {STEPS.map(([title, detail], i) => (
            <li key={title}>
              <span className="n mono">{String(i + 1).padStart(2, '0')}</span>
              <div>
                <span className="t">{title}</span>
                <span className="d">{detail}</span>
              </div>
            </li>
          ))}
        </ol>

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

        <p className="cta">Pick one of the two alerts, top right, to replay a real run.</p>

        <p className="source">
          Source, tests and the build log:{' '}
          <a href="https://github.com/ANMOLGUPTA-24/stores-triage" target="_blank" rel="noreferrer">
            github.com/ANMOLGUPTA-24/stores-triage
          </a>
        </p>
      </div>
    </section>
  )
}
