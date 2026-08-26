/**
 * Fold a TrueForge event stream into everything the console draws.
 *
 * The harness gives us the pause. It does not give us the dossier: a
 * `tool.approval_required` event carries the tool call and nothing else. So the
 * evidence behind an approval has to be gathered from events that already went
 * past, which is what this reducer is for.
 *
 * The four verdicts are read from the *arguments* of the `adjudicate` call
 * rather than from what the subagents said in prose. Structured data the agent
 * had to produce anyway beats parsing English out of a transcript.
 */

export const HYPOTHESES = [
  'consumption_spike',
  'inbound_delay',
  'duplicate_indent',
  'bom_change',
] as const

export type HypothesisName = (typeof HYPOTHESES)[number]

export const MAIN_THREAD = 'main'

export type VerdictValue = 'positive' | 'negative' | 'inconclusive'

export interface Verdict {
  hypothesis: HypothesisName
  verdict: VerdictValue
  evidence: Record<string, unknown>
  note?: string
}

export interface Recommendation {
  action: 'raise_indent' | 'no_action'
  reason: string
  what_would_change_my_mind: string
  ruled_out: string[]
  urgency: string | null
  indent_qty: number | null
}

export interface DraftIndent {
  indent: Record<string, unknown>
  mail: { to: string; subject: string; body: string }
}

export interface ToolCallRecord {
  id: string
  name: string
  args: unknown
  server?: string
  threadId: string
  result?: string
  failed?: boolean
  settled: boolean
  sequence: number
}

export interface ThreadState {
  threadId: string
  /** agentInfo.name from thread.created; the hypothesis it owns, when it is one. */
  name: string
  hypothesis?: HypothesisName
  status: 'investigating' | 'done'
  verdict?: Verdict
  toolCallIds: string[]
  text: string
}

export interface PendingApproval {
  threadId: string
  toolCallId: string
  toolName: string
  args: unknown
}

export type ActivityKind = 'text' | 'tool' | 'thread' | 'sandbox' | 'gate' | 'lifecycle'

export interface ActivityItem {
  id: string
  kind: ActivityKind
  threadId: string
  label: string
  detail?: string
  sequence: number
}

export interface ConsoleState {
  turnId?: string
  status: 'idle' | 'running' | 'blocked' | 'done' | 'error'
  activity: ActivityItem[]
  threads: Record<string, ThreadState>
  toolCalls: Record<string, ToolCallRecord>
  approvals: PendingApproval[]
  sandboxReady: boolean
  verdicts: Verdict[]
  recommendation?: Recommendation
  draft?: DraftIndent
  projection?: Record<string, number>
  /** Set once the run has actually finished doing (or not doing) something. */
  outcome?: 'indent_raised' | 'no_action' | 'rejected_by_operator'
}

export function initialState(): ConsoleState {
  return {
    status: 'idle',
    activity: [],
    threads: {},
    toolCalls: {},
    approvals: [],
    sandboxReady: false,
    verdicts: [],
  }
}

/** Anything with a `type`. Deliberately loose: the stream carries more than we use. */
export interface StreamEvent {
  type: string
  id?: string
  threadId?: string
  [key: string]: unknown
}

function isHypothesis(value: unknown): value is HypothesisName {
  return typeof value === 'string' && (HYPOTHESES as readonly string[]).includes(value)
}

/** Tool arguments arrive as a JSON string, and malformed JSON must not kill the view. */
function parseArgs(raw: unknown): unknown {
  if (typeof raw !== 'string') return raw ?? {}
  try {
    return JSON.parse(raw)
  } catch {
    return { _unparsed: raw }
  }
}

function parseResult(raw: unknown): unknown {
  if (typeof raw !== 'string') return raw
  try {
    return JSON.parse(raw)
  } catch {
    return undefined
  }
}

function shortArgs(args: unknown): string | undefined {
  if (args === null || args === undefined) return undefined
  const text = typeof args === 'string' ? args : JSON.stringify(args)
  return text.length > 240 ? `${text.slice(0, 237)}...` : text
}

function push(state: ConsoleState, item: ActivityItem): ActivityItem[] {
  return [...state.activity, item]
}

function threadFor(state: ConsoleState, threadId: string): ThreadState {
  return (
    state.threads[threadId] ?? {
      threadId,
      name: threadId === MAIN_THREAD ? 'root' : threadId,
      status: 'investigating',
      toolCallIds: [],
      text: '',
    }
  )
}

/**
 * Apply one event. Pure: same state in, same state out, no surprises on replay.
 */
export function reduce(state: ConsoleState, event: StreamEvent, sequence = 0): ConsoleState {
  const threadId = (event.threadId as string) ?? MAIN_THREAD

  switch (event.type) {
    case 'turn.created':
      return {
        ...initialState(),
        turnId: (event.turnId as string) ?? (event.id as string),
        status: 'running',
        activity: [
          {
            id: `seq-${sequence}`,
            kind: 'lifecycle',
            threadId,
            label: 'run started',
            sequence,
          },
        ],
      }

    case 'thread.created': {
      const info = (event.agentInfo ?? {}) as { name?: string; input?: string }
      const name = info.name ?? threadId
      const thread: ThreadState = {
        ...threadFor(state, threadId),
        threadId,
        name,
        hypothesis: isHypothesis(name) ? name : undefined,
        status: 'investigating',
      }
      return {
        ...state,
        threads: { ...state.threads, [threadId]: thread },
        activity: push(state, {
          id: `seq-${sequence}`,
          kind: 'thread',
          threadId,
          label: `${name} investigating`,
          detail: info.input,
          sequence,
        }),
      }
    }

    case 'thread.done': {
      const thread = { ...threadFor(state, threadId), status: 'done' as const }
      return {
        ...state,
        threads: { ...state.threads, [threadId]: thread },
        activity: push(state, {
          id: `seq-${sequence}`,
          kind: 'thread',
          threadId,
          label: `${thread.name} reported`,
          sequence,
        }),
      }
    }

    case 'sandbox.created':
      return {
        ...state,
        sandboxReady: true,
        activity: push(state, {
          id: `seq-${sequence}`,
          kind: 'sandbox',
          threadId,
          label: 'sandbox provisioned',
          sequence,
        }),
      }

    case 'model.message': {
      const calls = (event.toolCalls ?? []) as Array<{
        id: string
        function?: { name?: string; arguments?: string }
        toolInfo?: { serverName?: string }
      }>
      let next = { ...state }
      const thread = threadFor(state, threadId)

      const content = typeof event.content === 'string' ? event.content : ''
      if (content) {
        next.threads = {
          ...next.threads,
          [threadId]: { ...thread, text: thread.text + content },
        }
        next.activity = push(next, {
          id: `seq-${sequence}-text`,
          kind: 'text',
          threadId,
          label: content,
          sequence,
        })
      }

      for (const call of calls) {
        const name = call.function?.name ?? 'unknown'
        const args = parseArgs(call.function?.arguments)
        next.toolCalls = {
          ...next.toolCalls,
          [call.id]: {
            id: call.id,
            name,
            args,
            server: call.toolInfo?.serverName,
            threadId,
            settled: false,
            sequence,
          },
        }
        const owner = threadFor(next, threadId)
        next.threads = {
          ...next.threads,
          [threadId]: { ...owner, toolCallIds: [...owner.toolCallIds, call.id] },
        }
        next.activity = push(next, {
          id: `seq-${sequence}-${call.id}`,
          kind: 'tool',
          threadId,
          label: name,
          detail: shortArgs(args),
          sequence,
        })

        // The verdicts are handed to adjudicate as arguments, which is the one
        // place all four exist as structured data rather than prose.
        if (name === 'adjudicate') {
          const parsed = args as { verdicts?: Verdict[]; projection?: Record<string, number> }
          if (Array.isArray(parsed?.verdicts)) {
            next.verdicts = parsed.verdicts.filter((v) => isHypothesis(v?.hypothesis))
            next.threads = attachVerdicts(next.threads, next.verdicts)
          }
          if (parsed?.projection) next.projection = parsed.projection
        }
      }
      return next
    }

    case 'model.message.delta': {
      const delta = typeof event.content === 'string' ? event.content : ''
      if (!delta) return state
      const thread = threadFor(state, threadId)
      return {
        ...state,
        threads: {
          ...state.threads,
          // content on a delta is the increment, not the running total.
          [threadId]: { ...thread, text: thread.text + delta },
        },
      }
    }

    case 'tool.response': {
      const id = (event.toolCallId as string) ?? ''
      const existing = state.toolCalls[id]
      if (!existing) return state
      const content = typeof event.content === 'string' ? event.content : ''
      const failed = Boolean(event.isError)
      const settledCall: ToolCallRecord = {
        ...existing,
        result: content,
        failed,
        settled: true,
      }
      // A held call stays pending only until it actually returns. Once it has,
      // the human is no longer what the run is waiting on.
      const stillPending = state.approvals.filter((a) => a.toolCallId !== id)
      const wasReleased = stillPending.length !== state.approvals.length

      let next: ConsoleState = {
        ...state,
        toolCalls: { ...state.toolCalls, [id]: settledCall },
        approvals: stillPending,
        status:
          wasReleased && stillPending.length === 0 && state.status === 'blocked'
            ? 'running'
            : state.status,
        activity: push(state, {
          id: `seq-${sequence}-res`,
          kind: 'tool',
          threadId: existing.threadId,
          label: `${existing.name} ${failed ? 'failed' : 'returned'}`,
          detail: shortArgs(content),
          sequence,
        }),
      }
      if (failed) return next

      const parsed = parseResult(content)
      if (existing.name === 'adjudicate' && parsed) {
        next.recommendation = parsed as Recommendation
      }
      if (existing.name === 'draft_indent' && parsed) {
        next.draft = parsed as DraftIndent
      }
      if (existing.name === 'log_run') {
        const outcome = (existing.args as { outcome?: ConsoleState['outcome'] })?.outcome
        if (outcome) next.outcome = outcome
      }
      return next
    }

    case 'tool.approval_required': {
      const refs = (event.toolCalls ?? []) as Array<{ id: string }>
      const approvals: PendingApproval[] = refs.map((ref) => {
        const call = state.toolCalls[ref.id]
        return {
          threadId,
          toolCallId: ref.id,
          toolName: call?.name ?? 'unknown',
          args: call?.args ?? {},
        }
      })
      return {
        ...state,
        status: 'blocked',
        approvals: [...state.approvals, ...approvals],
        activity: push(state, {
          id: `seq-${sequence}`,
          kind: 'gate',
          threadId,
          label: `waiting for a human: ${approvals.map((a) => a.toolName).join(', ')}`,
          sequence,
        }),
      }
    }

    case 'turn.done': {
      const terminal = (event.state as { status?: string })?.status ?? 'done'
      // A turn that ended because it is waiting on us is not a finished run.
      if (state.status === 'blocked' && terminal !== 'error') return state
      return {
        ...state,
        status: terminal === 'error' ? 'error' : 'done',
        activity: push(state, {
          id: `seq-${sequence}`,
          kind: 'lifecycle',
          threadId,
          label: terminal === 'error' ? 'run failed' : 'run finished',
          sequence,
        }),
      }
    }

    default:
      return state
  }
}

function attachVerdicts(
  threads: Record<string, ThreadState>,
  verdicts: Verdict[],
): Record<string, ThreadState> {
  const byHypothesis = new Map(verdicts.map((v) => [v.hypothesis, v]))
  const next: Record<string, ThreadState> = {}
  for (const [id, thread] of Object.entries(threads)) {
    const verdict = thread.hypothesis ? byHypothesis.get(thread.hypothesis) : undefined
    next[id] = verdict ? { ...thread, verdict } : thread
  }
  return next
}

export function reduceAll(events: StreamEvent[]): ConsoleState {
  return events.reduce((state, event, i) => reduce(state, event, i), initialState())
}

/** The four columns, in a fixed order, whether or not a thread exists yet. */
export function hypothesisBoard(state: ConsoleState): Array<{
  hypothesis: HypothesisName
  thread?: ThreadState
  verdict?: Verdict
}> {
  const byHypothesis = new Map(
    Object.values(state.threads)
      .filter((t) => t.hypothesis)
      .map((t) => [t.hypothesis as HypothesisName, t]),
  )
  const verdicts = new Map(state.verdicts.map((v) => [v.hypothesis, v]))
  return HYPOTHESES.map((hypothesis) => ({
    hypothesis,
    thread: byHypothesis.get(hypothesis),
    verdict: verdicts.get(hypothesis),
  }))
}

/** True when the run is parked on a human. Drives the one accent colour. */
export function isBlocked(state: ConsoleState): boolean {
  return state.status === 'blocked' && state.approvals.length > 0
}
