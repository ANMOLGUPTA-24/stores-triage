import { useCallback, useEffect, useMemo, useState } from 'react'

import { ActivityStream } from './components/ActivityStream'
import { Dossier } from './components/Dossier'
import { HypothesisBoard } from './components/HypothesisBoard'
import { RunLog, type RunLogEntry } from './components/RunLog'
import { initialState, isBlocked, reduce, type StreamEvent } from './lib/events'
import { RUN_A, RUN_B } from './lib/fixtures'

/**
 * The operator console.
 *
 * Four surfaces and nothing else: what the agent is doing now, what the four
 * hypotheses found, the dossier it is blocked on, and what it has done today.
 *
 * Runs against a recorded event stream. The reducer is fed one event at a time
 * exactly as it would be from a live turn, so the waiting states are real
 * waiting states rather than a mock-up of them.
 */

const RUNS = {
  'TRB-4417': { events: RUN_A, label: 'genuine shortage' },
  'BRK-2290': { events: RUN_B, label: 'looks identical' },
} as const

type PartNo = keyof typeof RUNS

/** How the run continues once a person has approved it. */
const APPROVED_TAIL: StreamEvent[] = [
  {
    type: 'tool.response',
    threadId: 'main',
    toolCallId: 't5',
    content: JSON.stringify({ indent_no: 'IND-2026-0742', part_no: 'TRB-4417', qty: 200, status: 'open' }),
  },
  {
    type: 'model.message',
    threadId: 'main',
    content: 'Indent IND-2026-0742 raised. Mailing the vendor.',
    toolCalls: [
      {
        id: 't6',
        type: 'function',
        function: {
          name: 'send_vendor_mail',
          arguments: JSON.stringify({
            part_no: 'TRB-4417',
            indent_no: 'IND-2026-0742',
            qty: 200,
            needed_by: '2026-09-04',
          }),
        },
        toolInfo: { type: 'mcp', serverName: 'stores' },
      },
    ],
  },
  {
    type: 'tool.response',
    threadId: 'main',
    toolCallId: 't6',
    content: JSON.stringify({ sent: true, to: 'stores+vendor@example.invalid' }),
  },
  {
    type: 'model.message',
    threadId: 'main',
    toolCalls: [
      {
        id: 't7',
        type: 'function',
        function: {
          name: 'log_run',
          arguments: JSON.stringify({
            session_id: 'turn-a',
            part_no: 'TRB-4417',
            outcome: 'indent_raised',
            detail: { indent_no: 'IND-2026-0742' },
          }),
        },
        toolInfo: { type: 'mcp', serverName: 'stores' },
      },
    ],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 't7', content: JSON.stringify({ id: 3 }) },
  { type: 'turn.done', threadId: 'main', state: { status: 'done' } },
]

const REJECTED_TAIL: StreamEvent[] = [
  // A denied call still comes back, which is what releases the gate.
  {
    type: 'tool.response',
    threadId: 'main',
    toolCallId: 't5',
    content: 'denied by the operator',
    isError: true,
  },
  {
    type: 'model.message',
    threadId: 'main',
    content: 'Rejected by the operator. Nothing raised, nothing sent.',
    toolCalls: [
      {
        id: 't8',
        type: 'function',
        function: {
          name: 'log_run',
          arguments: JSON.stringify({
            session_id: 'turn-a',
            part_no: 'TRB-4417',
            outcome: 'rejected_by_operator',
            detail: {},
          }),
        },
        toolInfo: { type: 'mcp', serverName: 'stores' },
      },
    ],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 't8', content: JSON.stringify({ id: 4 }) },
  { type: 'turn.done', threadId: 'main', state: { status: 'done' } },
]

const STEP_MS = 380

export default function App() {
  const [partNo, setPartNo] = useState<PartNo>('TRB-4417')
  const [queue, setQueue] = useState<StreamEvent[]>([])
  const [cursor, setCursor] = useState(0)
  const [log, setLog] = useState<RunLogEntry[]>([])

  const state = useMemo(
    () => queue.slice(0, cursor).reduce((acc, event, i) => reduce(acc, event, i), initialState()),
    [queue, cursor],
  )

  const start = useCallback((part: PartNo) => {
    setPartNo(part)
    setQueue([...RUNS[part].events])
    setCursor(0)
  }, [])

  // Feed the reducer one event at a time, the way a live stream would.
  useEffect(() => {
    if (cursor >= queue.length) return
    const timer = setTimeout(() => setCursor((c) => c + 1), STEP_MS)
    return () => clearTimeout(timer)
  }, [cursor, queue.length])

  // Record the outcome once the run settles.
  useEffect(() => {
    if (!state.outcome || cursor < queue.length) return
    setLog((entries) =>
      entries.some((e) => e.id === cursor && e.part_no === partNo)
        ? entries
        : [
            {
              id: cursor,
              part_no: partNo,
              outcome: state.outcome!,
              logged_at: new Date().toISOString(),
              summary: state.recommendation?.reason.split('.')[0],
            },
            ...entries,
          ],
    )
  }, [state.outcome, state.recommendation, cursor, queue.length, partNo])

  const resume = useCallback(
    (tail: StreamEvent[]) => {
      setQueue((q) => [...q.slice(0, cursor), ...tail])
    },
    [cursor],
  )

  const blocked = isBlocked(state)
  const statusClass = blocked
    ? 'is-blocked'
    : state.status === 'running'
      ? 'is-running'
      : ''

  return (
    <div className="app">
      <header className="topbar">
        <h1>Stores Triage</h1>
        <span className="part mono">{partNo}</span>
        <span className={`status ${statusClass}`}>
          <span className="dot" />
          {blocked ? 'blocked on you' : state.status}
        </span>
        <span className="spacer" />
        {(Object.keys(RUNS) as PartNo[]).map((part) => (
          <button key={part} onClick={() => start(part)} disabled={cursor > 0 && cursor < queue.length}>
            {part} — {RUNS[part].label}
          </button>
        ))}
      </header>

      <div className="columns">
        <ActivityStream state={state} />
        <div className="stack">
          <HypothesisBoard state={state} />
          <div className="body" style={{ overflow: 'auto', display: 'grid', gap: 'var(--gap)', alignContent: 'start' }}>
            <Dossier
              state={state}
              chartUrl={state.projection && partNo === 'TRB-4417' ? '/chart-TRB-4417.png' : undefined}
              onApprove={() => resume(APPROVED_TAIL)}
              onReject={() => resume(REJECTED_TAIL)}
            />
            <RunLog entries={log} />
          </div>
        </div>
      </div>
    </div>
  )
}
