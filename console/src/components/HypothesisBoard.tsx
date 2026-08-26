import type { ConsoleState, Verdict } from '../lib/events'
import { hypothesisBoard } from '../lib/events'

/**
 * Four competing explanations, side by side.
 *
 * This is the surface that makes the reasoning legible on camera: four things
 * were checked, here is what each found. A column that has not reported yet
 * says so rather than sitting blank.
 */

function evidenceLine(verdict: Verdict | undefined): string | null {
  if (!verdict) return null
  const ev = verdict.evidence ?? {}

  const consignments = (ev as { consignments?: Array<Record<string, unknown>> }).consignments
  if (Array.isArray(consignments) && consignments.length) {
    return consignments
      .map((c) => `${c.consignment_no}  ${c.qty}  ${c.status}  eta ${c.eta}`)
      .join('\n')
  }

  const indentNo = (ev as { indent_no?: string }).indent_no
  if (indentNo) {
    const linked = (ev as { linked_consignment?: Record<string, unknown> | null }).linked_consignment
    return linked
      ? `${indentNo}\n  → ${linked.consignment_no} ${linked.status} eta ${linked.eta}`
      : `${indentNo}\n  → nothing moving against it`
  }

  const despiked = (ev as { despiked_daily_draw?: number }).despiked_daily_draw
  if (typeof despiked === 'number') return `underlying draw ${despiked}/day`

  const superseded = (ev as { superseded_by?: string | null }).superseded_by
  if (superseded) return `superseded by ${superseded}`

  return null
}

export function HypothesisBoard({ state }: { state: ConsoleState }) {
  const columns = hypothesisBoard(state)
  const reported = columns.filter((c) => c.verdict).length

  return (
    <section className="panel">
      <header>
        <span>hypotheses</span>
        <span className="spacer" />
        <span>{reported} of 4 reported</span>
      </header>
      <div className="board">
        {columns.map(({ hypothesis, thread, verdict }) => {
          const waiting = !verdict
          const cls = waiting ? 'is-waiting' : `is-${verdict.verdict}`
          const evidence = evidenceLine(verdict)
          return (
            <div className={`hyp ${cls}`} key={hypothesis}>
              <div className="name">{hypothesis}</div>
              <div className="verdict">
                {verdict ? (
                  verdict.verdict
                ) : thread ? (
                  <>
                    investigating<span className="working">...</span>
                  </>
                ) : (
                  'not started'
                )}
              </div>
              {verdict?.note && <div className="note">{verdict.note}</div>}
              {evidence && <pre className="ev mono">{evidence}</pre>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
