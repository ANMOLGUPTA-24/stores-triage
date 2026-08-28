/**
 * What a stranger needs before the console means anything.
 *
 * The four surfaces are built for a stores officer who already knows the job.
 * Someone opening a link does not: without the stakes, a hypothesis board and
 * an empty activity stream look like a toy. This sits in the space the dossier
 * and run log will occupy, and is gone the moment a run starts.
 */
export function Brief() {
  return (
    <section className="panel brief">
      <header>
        <span>what this is</span>
      </header>
      <div className="body">
        <p className="lede">
          A spare-part stock alert fires at a locomotive works. This agent decides
          whether it is a <strong>genuine</strong> shortage or a <strong>paper</strong> one.
        </p>

        <div className="impact">
          <div>
            <span className="fig">~40 min</span>
            <span className="cap">for a stores officer to answer this by hand, across three systems</span>
          </div>
          <div>
            <span className="fig">101 s</span>
            <span className="cap">for the run below, with the working attached</span>
          </div>
          <div>
            <span className="fig">20 / day</span>
            <span className="cap">alerts one officer gets through</span>
          </div>
        </div>

        <p>
          The stores officer gets twenty of these a day and about forty minutes
          each, because the evidence lives in three systems that do not talk to
          one another: the consumption log, the open indents, and the
          consignments in transit. So the alert cannot answer the only question
          that matters — <em>is this real?</em>
        </p>

        <div className="split">
          <div>
            <dl className="costs">
          <dt>Raise a duplicate indent</dt>
          <dd>against stock already in transit, and the works pays expedite rates on stock it already owns.</dd>
          <dt>Miss a genuine shortage</dt>
          <dd>and a locomotive sits idle.</dd>
        </dl>

            <p>
              <strong>The two alerts, top right, are indistinguishable from the
              alert alone</strong> — 9.3 days of stock against 9.4. One is real.
              One is not. That is the whole demonstration.
            </p>
          </div>

          <ul className="how">
          <li>
            <span className="k">Four competing explanations</span>, one subagent
            each, running in parallel. Every one is trying to prove the shortage
            is <em>not</em> real; ruling all four out is what makes it real.
          </li>
          <li>
            <span className="k">The verdict is not the model's opinion.</span>{' '}
            Adjudication is ordinary Python with unit tests. The agent gathers
            evidence and calls tools; it does not get a vote.
          </li>
          <li>
            <span className="k">No number comes from the model.</span> The draw
            rate, the stockout band and the lead-time percentiles are computed by
            tested code running in a sandbox.
          </li>
          <li>
            <span className="k">The gate is a dossier, not a confirm box.</span>{' '}
            Before anything irreversible, the run stops and shows the evidence,
            the exact payload, and the one line that would change the answer.
          </li>
          </ul>
        </div>

        <p className="closing">
          Run <span className="mono">TRB-4417</span> ends blocked on a human. Run{' '}
          <span className="mono">BRK-2290</span> looks identical and correctly
          does <strong>nothing</strong> — no gate, no approval, because nothing
          should happen. Being confidently right that nothing should happen is
          the harder half of the problem.
        </p>
      </div>
    </section>
  )
}
