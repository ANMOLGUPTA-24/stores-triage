/**
 * The front door.
 *
 * The console's four surfaces are for a stores officer who already knows the
 * job. Someone opening a link has 30 seconds and three questions - what is it,
 * how does it work, why does it matter - and the operator console answers none
 * of them before it is driven. This does, and hands over to the console the
 * moment a run starts.
 *
 * The four hypotheses appear here as the method rather than as an empty board:
 * four subagents arguing in parallel is the central idea, and a visitor who
 * never clicks would otherwise never meet it.
 */
const QUESTIONS: Array<[string, string]> = [
  ['consumption_spike', 'Was the drawdown a one-off burst rather than the steady rate?'],
  ['inbound_delay', 'Is stock already coming, just not booked in yet?'],
  ['duplicate_indent', 'Has someone already raised this, and it is still open?'],
  ['bom_change', 'Is the part superseded, with the works moving off it?'],
]

const STEPS: Array<[string, string]> = [
  ['Records', 'pulled over MCP from a real Postgres.'],
  ['Arithmetic in a sandbox', 'tested Python fits the draw rate and solves the stockout band. No number comes from the model.'],
  ['Four hypotheses, in parallel', 'one subagent each, every one trying to prove the shortage is not real.'],
  ['Adjudication', 'ordered rules in ordinary Python with unit tests. The model does not get a vote.'],
  ['Act, or do not', 'genuine stops at a dossier a human approves; paper does nothing, and says why.'],
]

const ARROW = (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M5 12h13" />
    <path d="M12 5l7 7-7 7" />
  </svg>
)

export function Landing({ onStart }: { onStart: (part: 'TRB-4417' | 'BRK-2290') => void }) {
  return (
    <div className="landing">
      <div className="landing-inner">
        <h2 className="headline">
          A spare-part stock alert fires at a locomotive works. This agent decides
          whether it is a genuine shortage — or a paper one.
        </h2>
        <p className="sub">
          The evidence lives in three systems that do not talk to each other. Raise a duplicate
          indent and the works pays expedite rates on stock it already owns; miss a real shortage
          and a locomotive sits idle.
        </p>

        <span className="lab">pick an alert to watch a real run</span>
        <div className="picks">
          <button className="pick is-primary" onClick={() => onStart('TRB-4417')}>
            <span className="pick-id mono">TRB-4417</span>
            <span className="pick-name">Genuine shortage</span>
            <span className="pick-days">9.3 days</span>
            <span className="pick-cap">of stock left</span>
            <span className="pick-go">{ARROW}</span>
          </button>
          <button className="pick" onClick={() => onStart('BRK-2290')}>
            <span className="pick-id mono">BRK-2290</span>
            <span className="pick-name">Looks identical</span>
            <span className="pick-days">9.4 days</span>
            <span className="pick-cap">of stock left</span>
            <span className="pick-go">{ARROW}</span>
          </button>
        </div>
        <p className="picks-note">
          From the alert alone these are the same problem. One is real. One is not — and the agent
          is right about which, without being told.
        </p>

        <div className="figures">
          <div>
            <span className="fig">~40<span className="unit"> min</span></span>
            <span className="cap">by hand, across three systems</span>
          </div>
          <div>
            <span className="fig">101<span className="unit"> s</span></span>
            <span className="cap">for the run you are about to watch</span>
          </div>
          <div>
            <span className="fig">20<span className="unit"> /day</span></span>
            <span className="cap">alerts one officer gets through</span>
          </div>
        </div>

        <div className="two">
          <section>
            <span className="lab">the four questions it asks at once</span>
            <div className="questions">
              {QUESTIONS.map(([name, q]) => (
                <div key={name}>
                  <span className="mono qname">{name}</span>
                  <span className="qtext">{q}</span>
                </div>
              ))}
            </div>
            <p className="qnote">
              One subagent each, running in parallel. Ruling all four out is what makes a shortage
              real.
            </p>
          </section>

          <section>
            <span className="lab">how a run works</span>
            <ol className="steps">
              {STEPS.map(([title, detail], i) => (
                <li key={title}>
                  <span className="n mono">{String(i + 1).padStart(2, '0')}</span>
                  <span>
                    <strong>{title}</strong> — {detail}
                  </span>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <div className="boundary">
          <p>
            <strong>TrueForge</strong> runs the agent loop, the MCP calls, the sandbox, the parallel
            subagents and the approval pause.
          </p>
          <p>
            <strong>This project</strong> is the MCP server over Postgres, the skill, the sandbox
            analysis, the deterministic adjudication and this console.
          </p>
          <p className="source">
            Source and tests:{' '}
            <a href="https://github.com/ANMOLGUPTA-24/stores-triage" target="_blank" rel="noreferrer">
              github.com/ANMOLGUPTA-24/stores-triage
            </a>
          </p>
        </div>
      </div>
    </div>
  )
}
