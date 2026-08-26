/**
 * What the agent did, in order, re-readable afterwards.
 *
 * "no action" is an outcome with the same standing as a raised indent. A run
 * that correctly decides to do nothing is a result, not an absence, and it
 * belongs in the log like anything else.
 */

export interface RunLogEntry {
  /** Stable per-run identity, so a replay does not collide with its original. */
  key: string
  id: number
  part_no: string
  outcome: 'indent_raised' | 'no_action' | 'rejected_by_operator'
  logged_at: string
  summary?: string
}

const OUTCOME_CLASS: Record<RunLogEntry['outcome'], string> = {
  indent_raised: 'is-raised',
  no_action: 'is-no-action',
  rejected_by_operator: 'is-rejected',
}

const OUTCOME_LABEL: Record<RunLogEntry['outcome'], string> = {
  indent_raised: 'raised',
  no_action: 'no action',
  rejected_by_operator: 'rejected',
}

function time(iso: string): string {
  const parsed = new Date(iso)
  return Number.isNaN(parsed.getTime())
    ? '--:--'
    : parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function RunLog({ entries }: { entries: RunLogEntry[] }) {
  return (
    <section className="panel">
      <header>
        <span>run log</span>
        <span className="spacer" />
        <span>{entries.length}</span>
      </header>
      <div className="body">
        {entries.length === 0 ? (
          <div className="empty">No runs yet today.</div>
        ) : (
          entries.map((entry) => (
            <div className={`log-row ${OUTCOME_CLASS[entry.outcome]}`} key={entry.key}>
              <span className="mono" style={{ color: 'var(--ink-faint)' }}>
                {time(entry.logged_at)}
              </span>
              <span className="outcome">{OUTCOME_LABEL[entry.outcome]}</span>
              <span>
                <span className="mono">{entry.part_no}</span>
                {entry.summary && <span className="detail"> — {entry.summary}</span>}
              </span>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
