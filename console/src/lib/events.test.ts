import { describe, expect, it } from 'vitest'

import {
  HYPOTHESES,
  hypothesisBoard,
  initialState,
  isBlocked,
  reduce,
  reduceAll,
  type StreamEvent,
} from './events'
import { RUN_A, RUN_B } from './fixtures'

describe('Run A - genuine shortage', () => {
  const state = reduceAll(RUN_A)

  it('ends parked on a human rather than finished', () => {
    // turn.done arrives after the approval request. Treating that as "done"
    // would drop the gate off the screen at the exact moment it matters.
    expect(state.status).toBe('blocked')
    expect(isBlocked(state)).toBe(true)
  })

  it('holds the irreversible call, not a read', () => {
    expect(state.approvals).toHaveLength(1)
    expect(state.approvals[0].toolName).toBe('raise_indent')
  })

  it('recovers the arguments of the held call for the approval card', () => {
    // The approval event carries only an id, so this had to be harvested from
    // the model.message that requested it.
    expect(state.approvals[0].args).toEqual({ part_no: 'TRB-4417', qty: 200 })
  })

  it('assembles the recommendation from the adjudicate response', () => {
    expect(state.recommendation?.action).toBe('raise_indent')
    expect(state.recommendation?.urgency).toBe('critical')
    expect(state.recommendation?.indent_qty).toBe(200)
  })

  it('carries the counterfactual through to the dossier', () => {
    const line = state.recommendation?.what_would_change_my_mind ?? ''
    expect(line).toContain('CN-8821')

    // The date must be the ETA the evidence actually carries, not a literal -
    // the fixtures resolve their dates at load so a recorded run never shows a
    // consignment that is already overdue, and asserting a hard-coded date here
    // would only test that constant.
    const inbound = state.verdicts.find((v) => v.hypothesis === 'inbound_delay')
    const eta = (inbound?.evidence as { consignments?: Array<{ eta: string }> })
      ?.consignments?.[0]?.eta
    expect(eta).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    expect(line).toContain(eta as string)
  })

  it('has the exact payload ready to show', () => {
    expect(state.draft?.indent.part_no).toBe('TRB-4417')
    expect(state.draft?.mail.subject).toContain('TRB-4417')
    expect(state.draft?.mail.body).toContain('Quantity  : 200 nos')
  })

  it('keeps the numbers the sandbox produced', () => {
    expect(state.projection?.days_to_stockout_p50).toBe(9.3)
    expect(state.projection?.lead_time_p80).toBe(31.0)
  })
})

describe('Run B - nothing should happen', () => {
  const state = reduceAll(RUN_B)

  it('asks for no approval at all', () => {
    expect(state.approvals).toHaveLength(0)
    expect(isBlocked(state)).toBe(false)
  })

  it('records no_action as an outcome rather than an absence', () => {
    expect(state.outcome).toBe('no_action')
    expect(state.status).toBe('done')
  })

  it('keeps the evidence that settles it', () => {
    expect(state.recommendation?.action).toBe('no_action')
    expect(state.recommendation?.reason).toContain('IND-2026-0731')
    expect(state.recommendation?.reason).toContain('CN-9104')
  })

  it('still says what would change its mind', () => {
    expect(state.recommendation?.what_would_change_my_mind).toContain('CN-9104')
  })
})

describe('hypothesis board', () => {
  it('always shows four columns in a fixed order', () => {
    const board = hypothesisBoard(reduceAll(RUN_A))
    expect(board.map((c) => c.hypothesis)).toEqual([...HYPOTHESES])
  })

  it('shows the columns before any subagent has reported', () => {
    // The empty state is most of the demo; it must not be blank.
    const board = hypothesisBoard(initialState())
    expect(board).toHaveLength(4)
    expect(board.every((c) => c.verdict === undefined)).toBe(true)
  })

  it('marks each subagent done once its thread closes', () => {
    const board = hypothesisBoard(reduceAll(RUN_A))
    expect(board.every((c) => c.thread?.status === 'done')).toBe(true)
  })

  it('attaches each verdict to its own column', () => {
    const board = hypothesisBoard(reduceAll(RUN_A))
    const inbound = board.find((c) => c.hypothesis === 'inbound_delay')
    expect(inbound?.verdict?.verdict).toBe('positive')
    expect(inbound?.verdict?.note).toContain('CN-8821')
    const dup = board.find((c) => c.hypothesis === 'duplicate_indent')
    expect(dup?.verdict?.verdict).toBe('negative')
  })

  it('shows a subagent as investigating before the verdicts land', () => {
    const upTo = RUN_A.slice(0, RUN_A.findIndex((e) => e.type === 'sandbox.created'))
    const board = hypothesisBoard(reduceAll(upTo))
    expect(board.every((c) => c.verdict === undefined)).toBe(true)
    expect(board.filter((c) => c.thread).length).toBe(4)
  })
})

describe('threads', () => {
  it('separates subagent work from the root thread', () => {
    const state = reduceAll(RUN_A)
    const subagents = Object.values(state.threads).filter((t) => t.hypothesis)
    expect(subagents).toHaveLength(4)
    expect(state.threads.main?.hypothesis).toBeUndefined()
  })

  it('attributes tool calls to the thread that made them', () => {
    const state = reduceAll(RUN_A)
    expect(state.toolCalls.t1.threadId).toBe('main')
  })
})

describe('robustness', () => {
  const run = (events: StreamEvent[]) => reduceAll(events)

  it('ignores event types it does not know', () => {
    const state = run([...RUN_B, { type: 'some.future.event', threadId: 'main' }])
    expect(state.outcome).toBe('no_action')
  })

  it('survives tool arguments that are not valid JSON', () => {
    const state = run([
      { type: 'turn.created', turnId: 't', threadId: 'main' },
      {
        type: 'model.message',
        threadId: 'main',
        toolCalls: [{ id: 'x', type: 'function', function: { name: 'get_part', arguments: '{oops' } }],
      },
    ])
    expect(state.toolCalls.x.args).toEqual({ _unparsed: '{oops' })
  })

  it('ignores a response to a tool call it never saw', () => {
    const state = run([
      { type: 'turn.created', turnId: 't', threadId: 'main' },
      { type: 'tool.response', threadId: 'main', toolCallId: 'ghost', content: '{}' },
    ])
    expect(Object.keys(state.toolCalls)).toHaveLength(0)
  })

  it('does not treat a failed tool call as a result', () => {
    const state = run([
      { type: 'turn.created', turnId: 't', threadId: 'main' },
      {
        type: 'model.message',
        threadId: 'main',
        toolCalls: [{ id: 'a', type: 'function', function: { name: 'adjudicate', arguments: '{}' } }],
      },
      { type: 'tool.response', threadId: 'main', toolCallId: 'a', content: 'boom', isError: true },
    ])
    expect(state.recommendation).toBeUndefined()
    expect(state.toolCalls.a.failed).toBe(true)
  })

  it('marks a turn that errored', () => {
    const state = run([
      { type: 'turn.created', turnId: 't', threadId: 'main' },
      { type: 'turn.done', threadId: 'main', state: { status: 'error' } },
    ])
    expect(state.status).toBe('error')
  })

  it('merges deltas as increments rather than replacing', () => {
    let state = initialState()
    state = reduce(state, { type: 'turn.created', turnId: 't', threadId: 'main' }, 0)
    state = reduce(state, { type: 'model.message.delta', threadId: 'main', content: 'CN-' }, 1)
    state = reduce(state, { type: 'model.message.delta', threadId: 'main', content: '8821' }, 2)
    expect(state.threads.main.text).toBe('CN-8821')
  })

  it('starts a fresh run when a new turn is created', () => {
    const state = reduceAll([...RUN_A, { type: 'turn.created', turnId: 'turn-c', threadId: 'main' }])
    expect(state.approvals).toHaveLength(0)
    expect(state.recommendation).toBeUndefined()
    expect(state.status).toBe('running')
  })
})

describe('releasing the gate', () => {
  const approvedTail: StreamEvent[] = [
    { type: 'tool.response', threadId: 'main', toolCallId: 't5', content: JSON.stringify({ indent_no: 'IND-2026-0742' }) },
    { type: 'turn.done', threadId: 'main', state: { status: 'done' } },
  ]

  it('stops being blocked once the held call returns', () => {
    // Latching blocked forever would leave the console claiming it still needs
    // a human long after the indent was raised.
    const state = reduceAll([...RUN_A, ...approvedTail])
    expect(state.approvals).toHaveLength(0)
    expect(isBlocked(state)).toBe(false)
    expect(state.status).toBe('done')
  })

  it('a denied call also releases the gate', () => {
    const state = reduceAll([
      ...RUN_A,
      { type: 'tool.response', threadId: 'main', toolCallId: 't5', content: 'denied', isError: true },
      { type: 'turn.done', threadId: 'main', state: { status: 'done' } },
    ])
    expect(isBlocked(state)).toBe(false)
    expect(state.toolCalls.t5.failed).toBe(true)
  })

  it('stays blocked while any other approval is still outstanding', () => {
    const state = reduceAll([
      ...RUN_A,
      {
        type: 'model.message',
        threadId: 'main',
        toolCalls: [{ id: 't9', type: 'function', function: { name: 'send_vendor_mail', arguments: '{}' } }],
      },
      { type: 'tool.approval_required', threadId: 'main', toolCalls: [{ id: 't9' }] },
      { type: 'tool.response', threadId: 'main', toolCallId: 't5', content: '{}' },
    ])
    expect(state.approvals.map((a) => a.toolCallId)).toEqual(['t9'])
    expect(isBlocked(state)).toBe(true)
  })

  it('a response to an unheld call does not disturb the gate', () => {
    const state = reduceAll([
      ...RUN_A,
      { type: 'tool.response', threadId: 'main', toolCallId: 't4', content: '{}' },
    ])
    expect(isBlocked(state)).toBe(true)
  })
})

describe('activity stream', () => {
  it('records tool calls and their results in order', () => {
    const state = reduceAll(RUN_A)
    const labels = state.activity.filter((a) => a.kind === 'tool').map((a) => a.label)
    expect(labels[0]).toBe('get_part')
    expect(labels).toContain('get_part returned')
    expect(labels).toContain('raise_indent')
  })

  it('marks the moment it stopped for a human', () => {
    const state = reduceAll(RUN_A)
    const gate = state.activity.find((a) => a.kind === 'gate')
    expect(gate?.label).toContain('raise_indent')
  })

  it('notes when the sandbox came up', () => {
    const state = reduceAll(RUN_A)
    expect(state.activity.some((a) => a.kind === 'sandbox')).toBe(true)
    expect(state.sandboxReady).toBe(true)
  })
})
