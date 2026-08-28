// Answer a pending tool.response_required (an ask_user_question) and keep going.
//
// Kept because a session created before ask_user_questions was disabled can
// still be stuck on one, and abandoning the session would throw away verdicts
// that cost real quota to produce.
import { TrueForge } from '@truefoundry/trueforge-sdk'

const tf = new TrueForge({ baseUrl: 'http://localhost:8790' })
const sid = process.env.TF_SESSION
const content = process.env.TF_ANSWER
if (!sid || !content) { console.error('set TF_SESSION and TF_ANSWER'); process.exit(1) }

const { data: events } = await tf.sessions.listEvents(sid)

// A question that has already been answered has a tool.response against its
// call id. Without checking that, a session which asked more than one question
// across continuations would get the oldest one answered again forever, and the
// question actually blocking it would never be reached.
const settled = new Set()
for (const row of events ?? []) {
  const e = row.event ?? row
  if (e?.type === 'tool.response') settled.add(e.toolCallId ?? e.tool_call_id)
}

let pending = null
for (const row of events ?? []) {
  const e = row.event ?? row
  if (e?.type !== 'turn.done') continue
  for (const a of e.state?.required_actions ?? e.state?.requiredActions ?? []) {
    if (a.type !== 'tool.response_required') continue
    // The id that matters is the held tool call's, not the action's.
    const call = (a.tool_calls ?? a.toolCalls ?? [])[0]
    const toolCallId = call?.id ?? a.tool_call_id ?? a.id
    if (settled.has(toolCallId)) continue
    pending = { threadId: a.thread_id ?? a.threadId ?? 'main', toolCallId }
    break
  }
  if (pending) break
}
if (!pending) { console.log('nothing pending'); process.exit(0) }
console.log('answering', pending.toolCallId)

const t0 = Date.now(); const el = () => `${String(Math.round((Date.now()-t0)/1000)).padStart(3)}s`
let gate = null
const stream = await tf.sessions.createTurnStream(sid, {
  input: [{ type: 'user.tool_response', threadId: pending.threadId, toolCallId: pending.toolCallId, content }],
})
for await (const it of stream) {
  const e = it?.event ?? it
  if (!e?.type) continue
  const th = e.threadId === 'main' ? 'root' : (e.threadId || '').slice(-6)
  if (e.type === 'model.message') {
    for (const c of e.toolCalls ?? e.tool_calls ?? []) console.log(`${el()} [${th}] -> ${c.function?.name} ${(c.function?.arguments ?? '').slice(0,200)}`)
    if (typeof e.content === 'string' && e.content.trim()) console.log(`${el()} [${th}] "${e.content.trim().slice(0,600)}"`)
  } else if (e.type === 'tool.response') console.log(`${el()} [${th}]   ${e.isError?'ERR':'ok'} ${String(e.content ?? '').slice(0,200)}`)
  else if (e.type === 'tool.approval_required') { gate = e; console.log(`${el()} *** GATE HELD *** ${JSON.stringify(e.toolCalls ?? e.tool_calls)}`) }
  else if (e.type === 'turn.done') console.log(`${el()} turn.done ${JSON.stringify(e.state?.status ?? e.state)}`)
}
console.log(gate ? '\nGATE HELD — nothing written.' : '\nNO GATE')
