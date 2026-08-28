/**
 * Drive a real TrueForge turn and feed its events to the reducer.
 *
 * The reducer is the same one the recorded runs use, so what the console draws
 * from a live turn and what it draws from a replay go through identical code.
 */

import { TrueForge } from '@truefoundry/trueforge-sdk'

import { alertPrompt, storesTriageAgent } from './agent'
import type { StreamEvent } from './events'

export interface LiveOptions {
  baseUrl: string
  model: string
  onEvent: (event: StreamEvent) => void
  signal?: AbortSignal
}

export interface LiveRun {
  sessionId: string
  /** Approve or reject the calls the harness is holding, and keep streaming. */
  respond: (decisions: ApprovalDecision[]) => Promise<void>
}

export interface ApprovalDecision {
  threadId: string
  toolCallId: string
  allow: boolean
  reason?: string
}

function client(baseUrl: string): TrueForge {
  // Standalone mode runs with auth disabled, so no token is sent.
  return new TrueForge({ baseUrl })
}

async function pump(
  stream: AsyncIterable<unknown>,
  onEvent: (event: StreamEvent) => void,
): Promise<void> {
  for await (const item of stream) {
    // createTurnStream yields the event; listEvents wraps it. Accept either
    // rather than assuming, so a shape change does not blank the console.
    const record = item as { event?: StreamEvent; type?: string }
    const event = record?.event ?? (record as StreamEvent)
    if (event && typeof event.type === 'string') onEvent(event)
  }
}

/** Start a run for one part and stream it until it finishes or stops for us. */
export async function startRun(partNo: string, options: LiveOptions): Promise<LiveRun> {
  const tf = client(options.baseUrl)

  const created = await tf.sessions.create({
    agent: { spec: storesTriageAgent({ model: options.model }) },
  })
  // Responses are enveloped as { data: ... }; reading .id off the envelope
  // silently yields undefined and every later call 404s on "session undefined".
  // Both shapes are read off one cast: narrowing only the first branch left
  // `created.id` typed against the SDK's envelope, which has no id at all, so
  // the console did not compile.
  const envelope = created as { data?: { id?: string }; id?: string }
  const sessionId = envelope.data?.id ?? envelope.id
  if (!sessionId) throw new Error('TrueForge did not return a session id')

  const stream = await tf.sessions.createTurnStream(sessionId, {
    input: [{ type: 'user.message', content: alertPrompt(partNo) }],
  })
  await pump(stream as AsyncIterable<unknown>, options.onEvent)

  return {
    sessionId,
    respond: async (decisions: ApprovalDecision[]) => {
      const resumed = await tf.sessions.createTurnStream(sessionId, {
        input: decisions.map((d) => ({
          type: 'user.tool_approval',
          threadId: d.threadId,
          toolCallId: d.toolCallId,
          approval: d.allow
            ? { status: 'allow' }
            : { status: 'deny', reason: d.reason ?? 'Rejected by the operator.' },
        })),
      })
      await pump(resumed as AsyncIterable<unknown>, options.onEvent)
    },
  }
}

/** Is the harness up, and does it have what a run needs? */
export async function checkHarness(baseUrl: string): Promise<{
  reachable: boolean
  sandbox: boolean
  skills: boolean
  detail?: string
}> {
  try {
    const response = await fetch(`${baseUrl}/api/v1/capabilities`)
    if (!response.ok) {
      return { reachable: false, sandbox: false, skills: false, detail: `HTTP ${response.status}` }
    }
    const body = (await response.json()) as {
      data?: {
        sandbox?: { enabled?: boolean }
        skill?: { enabled?: boolean; reason?: string }
      }
    }
    return {
      reachable: true,
      sandbox: Boolean(body.data?.sandbox?.enabled),
      skills: Boolean(body.data?.skill?.enabled),
      detail: body.data?.skill?.reason,
    }
  } catch (error) {
    return {
      reachable: false,
      sandbox: false,
      skills: false,
      detail: error instanceof Error ? error.message : 'unreachable',
    }
  }
}
