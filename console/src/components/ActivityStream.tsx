import { useEffect, useRef } from 'react'

import type { ActivityItem, ConsoleState } from '../lib/events'

/**
 * What the agent is doing, in order.
 *
 * Tool calls and sandbox output are monospace so they never read as the agent
 * talking. The moment it stops for a human is the only coloured row.
 */

const KIND_CLASS: Record<ActivityItem['kind'], string> = {
  text: 'is-text',
  tool: 'is-tool',
  thread: 'is-thread',
  sandbox: 'is-sandbox',
  gate: 'is-gate',
  lifecycle: 'is-lifecycle',
}

export function ActivityStream({ state }: { state: ConsoleState }) {
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = bodyRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [state.activity.length])

  return (
    <section className="panel">
      <header>
        <span>activity</span>
        <span className="spacer" />
        <span>{state.activity.length} events</span>
      </header>
      <div className="body" ref={bodyRef}>
        {state.activity.length === 0 ? (
          <div className="empty">
            Waiting for a stock alert.
            <br />
            Nothing has happened yet.
            {/* On a public page this panel is the first thing read, and
                "nothing has happened" on its own reads as broken rather than
                ready. Say where the run comes from - an operator watching a
                live queue already knows, a visitor does not. */}
            <br />
            <br />
            Pick one of the two alerts, top right, to replay a run.
          </div>
        ) : (
          state.activity.map((item, i) => (
            <div className={`activity-row ${KIND_CLASS[item.kind]}`} key={`${item.id}-${i}`}>
              <div className="when">{String(item.sequence).padStart(3, '0')}</div>
              <div className="what">
                {item.label}
                {item.detail && <span className="detail mono">{item.detail}</span>}
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  )
}
