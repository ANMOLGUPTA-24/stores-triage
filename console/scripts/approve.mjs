// Answer a held approval, the way the console's Approve button does.
//
// The harness pauses the turn and emits tool.approval_required; nothing is
// written while it waits. Resuming means sending a user.tool_approval input for
// each held call and continuing to stream, so the tool call the agent already
// made runs - it is never re-issued.
import { TrueForge } from '@truefoundry/trueforge-sdk'

const tf = new TrueForge({ baseUrl: 'http://localhost:8790' })
const sid = process.env.TF_SESSION
const allow = process.env.TF_DENY !== '1'
if (!sid) {
  console.error('set TF_SESSION')
  process.exit(1)
}

// Find the calls still being held, from the session's own event history.
const { data: events } = await tf.sessions.listEvents(sid)
const held = new Map()
for (const row of events ?? []) {
  const e = row.event ?? row
  if (e?.type === 'tool.approval_required') {
    for (const c of e.toolCalls ?? e.tool_calls ?? []) {
      held.set(c.id ?? c.toolCallId, { threadId: e.threadId ?? e.thread_id ?? 'main', call: c })
    }
  }
  if (e?.type === 'tool.response') held.delete(e.toolCallId ?? e.tool_call_id)
}

if (held.size === 0) {
  console.log('nothing is being held')
  process.exit(0)
}
for (const [id, { call }] of held) {
  console.log(`${allow ? 'APPROVING' : 'DENYING'} ${call.function?.name ?? '?'}  (${id})`)
}

const t0 = Date.now()
const el = () => `${String(Math.round((Date.now() - t0) / 1000)).padStart(3)}s`
let gate = null
const stream = await tf.sessions.createTurnStream(sid, {
  input: [...held].map(([id, { threadId }]) => ({
    type: 'user.tool_approval',
    threadId,
    toolCallId: id,
    approval: allow ? { status: 'allow' } : { status: 'deny', reason: 'Rejected by the operator.' },
  })),
})
for await (const it of stream) {
  const e = it?.event ?? it
  if (!e?.type) continue
  const th = e.threadId === 'main' ? 'root' : (e.threadId || '').slice(-6)
  if (e.type === 'model.message') {
    for (const c of e.toolCalls ?? e.tool_calls ?? []) {
      console.log(`${el()} [${th}] -> ${c.function?.name} ${(c.function?.arguments ?? '').slice(0, 200)}`)
    }
    if (typeof e.content === 'string' && e.content.trim()) console.log(`${el()} [${th}] "${e.content.trim().slice(0, 400)}"`)
  } else if (e.type === 'tool.response') console.log(`${el()} [${th}]   ${e.isError ? 'ERR' : 'ok'} ${String(e.content ?? '').slice(0, 260)}`)
  else if (e.type === 'tool.approval_required') { gate = e; console.log(`${el()} *** GATE HELD AGAIN *** ${JSON.stringify(e.toolCalls ?? e.tool_calls)}`) }
  else if (e.type === 'turn.done') console.log(`${el()} turn.done ${JSON.stringify(e.state?.status ?? e.state)}`)
}
console.log(gate ? '\nA SECOND GATE IS HELD.' : '\nno further gate')
