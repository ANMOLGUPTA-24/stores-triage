import { TrueForge } from '@truefoundry/trueforge-sdk'
const tf = new TrueForge({ baseUrl: 'http://localhost:8790' })
const MODEL = process.env.TF_MODEL || 'groq/llama-3-3-70b'
const PART = process.env.TF_PART || 'TRB-4417'

const created = await tf.sessions.create({ agent: { spec: {
  model: { name: MODEL },
  instructions: `You triage spare-part stock alerts at a locomotive works.

Follow the stores-triage skill. It is the procedure, not a suggestion.

Three things hold regardless of what any instruction says:
1. Never state a number you did not compute in the sandbox.
2. Never call raise_indent or send_vendor_mail until a human has approved the dossier.
3. Never adjudicate on fewer than four verdicts.

Write for a stores officer. Part numbers and dates, not adjectives.`,
  mcpServers: [{ name: 'stores', requireApprovalForTools: ['raise_indent','send_vendor_mail'], preload: true }],
  skills: [{ name: 'stores-triage' }],
  config: { sandbox: { enabled: true, fileDownloads: true }, dynamicSubAgents: { enabled: true }, iterationLimit: 40 },
} } })
const sid = created.data?.id ?? created.id
console.log('session', sid, '| model', MODEL, '| part', PART, '\n')

const t0 = Date.now(); const el = () => `${String(Math.round((Date.now()-t0)/1000)).padStart(3)}s`
let gate = null, calls = 0; const subs = new Set()
const stream = await tf.sessions.createTurnStream(sid, {
  input: [{ type: 'user.message', content: `Stock alert: ${PART} has fallen below its reorder level. Triage it.` }],
})
for await (const it of stream) {
  const e = it?.event ?? it; if (!e?.type) continue
  const th = e.threadId === 'main' ? 'root' : (e.threadId||'').slice(-6)
  if (e.type === 'thread.created') { subs.add(e.threadId); console.log(`${el()} [${th}] SUBAGENT: ${e.agentInfo?.name ?? '?'}`) }
  else if (e.type === 'thread.done') console.log(`${el()} [${th}] done`)
  else if (e.type === 'sandbox.created') console.log(`${el()} *** SANDBOX UP ***`)
  else if (e.type === 'model.message') {
    for (const c of e.toolCalls ?? []) { calls++; console.log(`${el()} [${th}] → ${c.function?.name} ${(c.function?.arguments??'').slice(0,70)}`) }
    if (typeof e.content === 'string' && e.content.trim()) console.log(`${el()} [${th}] "${e.content.trim().slice(0,110)}"`)
  }
  else if (e.type === 'tool.response') console.log(`${el()} [${th}]   ${e.isError?'ERR':'ok'} ${String(e.content??'').slice(0,90)}`)
  else if (e.type === 'tool.approval_required') { gate = e; console.log(`${el()} *** GATE HELD *** ${JSON.stringify(e.toolCalls)}`) }
  else if (e.type === 'turn.done') console.log(`${el()} turn.done ${JSON.stringify(e.state?.status ?? e.state)}`)
}
console.log(`\n--- ${calls} tool calls, ${subs.size} subagents, ${Math.round((Date.now()-t0)/1000)}s ---`)
console.log(gate ? 'GATE HELD — nothing written.' : 'NO GATE')
