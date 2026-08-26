import type { ConsoleState } from '../lib/events'
import { isBlocked } from '../lib/events'

/**
 * The approval card, and the reason it is safe to approve.
 *
 * An approval is only meaningful if the human can check the reasoning in about
 * five seconds, so this never shows a bare confirm. It shows the recommendation,
 * the numbers, the exact payload that will go out, and the one line stating what
 * would change the answer.
 *
 * When the recommendation is no_action there is nothing to approve, and the card
 * says so as a result rather than as an error.
 */

interface Props {
  state: ConsoleState
  chartUrl?: string
  onApprove: () => void
  onReject: () => void
}

export function Dossier({ state, chartUrl, onApprove, onReject }: Props) {
  const rec = state.recommendation
  const blocked = isBlocked(state)

  if (!rec) {
    return (
      <section className="dossier">
        <header>
          <h2>No recommendation yet</h2>
        </header>
        <div className="section empty" style={{ padding: '18px 12px' }}>
          The agent is still gathering evidence. Nothing will be raised and no mail
          will go out until all four hypotheses have reported and a person has
          approved.
        </div>
      </section>
    )
  }

  const noAction = rec.action === 'no_action'

  return (
    <section className={`dossier${blocked ? ' is-gate' : ''}`}>
      <header>
        <h2>
          {noAction
            ? 'No action'
            : blocked
              ? 'Waiting for your approval'
              : 'Recommendation'}
        </h2>
        <span className="spacer" />
        {rec.urgency && <span className="mono">{rec.urgency}</span>}
      </header>

      <div className="section">
        <div className="label">why</div>
        <div>{rec.reason}</div>
      </div>

      {state.projection && (
        <div className="section">
          <div className="label">from the sandbox</div>
          <div className="mono">
            draw {state.projection.mean_daily_draw}/day &nbsp;·&nbsp; runs dry in{' '}
            {state.projection.days_to_stockout_p50} days (p10{' '}
            {state.projection.days_to_stockout_p10}) &nbsp;·&nbsp; vendor p80{' '}
            {state.projection.lead_time_p80} days
          </div>
        </div>
      )}

      {chartUrl && (
        <div className="section">
          <div className="label">projection</div>
          <img className="chart" src={chartUrl} alt="Projected stock against vendor lead time" />
        </div>
      )}

      <div className="section">
        <div className="label">ruled out</div>
        <div className="mono">
          {rec.ruled_out.length ? rec.ruled_out.join(' · ') : 'nothing was ruled out'}
        </div>
      </div>

      {!noAction && state.draft && (
        <>
          <div className="section">
            <div className="label">indent that will be raised</div>
            <pre className="payload mono">{JSON.stringify(state.draft.indent, null, 2)}</pre>
          </div>
          <div className="section">
            <div className="label">mail that will be sent — to {state.draft.mail.to}</div>
            <pre className="payload mono">
              {`Subject: ${state.draft.mail.subject}\n\n${state.draft.mail.body}`}
            </pre>
          </div>
        </>
      )}

      <div className="section">
        <div className="label">what would change this</div>
        <div className="mind">{rec.what_would_change_my_mind}</div>
      </div>

      {blocked ? (
        <div className="actions">
          <button className="primary" onClick={onApprove}>
            Approve — raise indent and mail vendor
          </button>
          <button onClick={onReject}>Reject</button>
        </div>
      ) : (
        noAction && (
          <div className="section">
            <div className="mono" style={{ color: 'var(--ok)' }}>
              nothing to approve — nothing should happen
            </div>
          </div>
        )
      )}
    </section>
  )
}
