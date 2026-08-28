// Continue an existing session with one more turn.
//
// A full run bursts past Gemini's 5 requests/minute the moment four subagents
// dispatch at once, and the harness has no backoff, so the turn dies partway.
// The session survives it though, verdicts and all, so the rest of the run can
// be driven sequentially - which is both under the rate limit and exactly what
// the operator sees after approving.
import { TrueForge } from '@truefoundry/trueforge-sdk'

const tf = new TrueForge({ baseUrl: 'http://localhost:8790' })
const sid = process.env.TF_SESSION
const message = process.env.TF_MESSAGE
if (!sid || !message) {
  console.error('set TF_SESSION and TF_MESSAGE')
  process.exit(1)
}

const t0 = Date.now()
const el = () => `${String(Math.round((Date.now() - t0) / 1000)).padStart(3)}s`
let gate = null
const stream = await tf.sessions.createTurnStream(sid, {
  input: [{ type: 'user.message', content: message }],
})
for await (const it of stream) {
  const e = it?.event ?? it
  if (!e?.type) continue
  const th = e.threadId === 'main' ? 'root' : (e.threadId || '').slice(-6)
  if (e.type === 'thread.created') console.log(`${el()} [${th}] SUBAGENT: ${e.agentInfo?.name ?? '?'}`)
  else if (e.type === 'sandbox.created') console.log(`${el()} *** SANDBOX UP ***`)
  else if (e.type === 'model.message') {
    for (const c of e.toolCalls ?? e.tool_calls ?? []) {
      console.log(`${el()} [${th}] -> ${c.function?.name} ${(c.function?.arguments ?? '').slice(0, 160)}`)
    }
    if (typeof e.content === 'string' && e.content.trim()) {
      console.log(`${el()} [${th}] "${e.content.trim().slice(0, 400)}"`)
    }
  } else if (e.type === 'tool.response') console.log(`${el()} [${th}]   ${e.isError ? 'ERR' : 'ok'} ${String(e.content ?? '').slice(0, 220)}`)
  else if (e.type === 'tool.approval_required') { gate = e; console.log(`${el()} *** GATE HELD *** ${JSON.stringify(e.toolCalls ?? e.tool_calls)}`) }
  else if (e.type === 'turn.done') console.log(`${el()} turn.done ${JSON.stringify(e.state?.status ?? e.state)}`)
}
console.log(gate ? '\nGATE HELD — nothing written.' : '\nNO GATE')
