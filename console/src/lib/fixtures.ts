/**
 * Recorded-shape event streams for both runs.
 *
 * These drive the reducer tests and the console's replay mode, so the interface
 * can be built and demonstrated without standing up the harness. They follow
 * the TrueForge protocol: tool arguments are JSON strings, deltas are
 * increments, and every event carries a threadId.
 */

import type { StreamEvent } from './events'

/**
 * Dates in a recorded run go stale.
 *
 * The seed is CURRENT_DATE-relative, so a recording made on one day shows ETAs
 * that are in the past by the time anyone else opens the page - and an overdue
 * consignment is exactly the thing the agent is supposed to refuse to count as
 * cover. A visitor would be reading a dossier that argues against itself.
 *
 * So the two ETAs are held as the offsets the seed actually uses and resolved
 * when the page loads. The numbers, the verdicts and the reasoning are the
 * recorded ones; only the dates move, and they move the way the database moves
 * them.
 */
function seedDate(offsetDays: number): string {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return d.toISOString().slice(0, 10)
}

/** CN-8821, the unconfirmed cover in Run A: seed + 2. */
const ETA_A = seedDate(2)
/** CN-9104, the confirmed cover in Run B: seed + 3. */
const ETA_B = seedDate(3)
/** What the indent asks for, which the seed puts at the day of the run. */
export const NEEDED_BY = seedDate(0)

const toolCall = (id: string, name: string, args: unknown) => ({
  id,
  type: 'function',
  function: { name, arguments: JSON.stringify(args) },
  toolInfo: { type: 'mcp', serverName: 'stores' },
})

const PROJECTION_A = {
  mean_daily_draw: 4.52,
  days_to_stockout_p50: 9.3,
  days_to_stockout_p10: 8.2,
  lead_time_p50: 23.0,
  lead_time_p80: 31.0,
}

const PROJECTION_B = {
  mean_daily_draw: 5.84,
  days_to_stockout_p50: 9.4,
  days_to_stockout_p10: 8.3,
  lead_time_p50: 20.0,
  lead_time_p80: 23.0,
}

const hypothesisThreads = (prefix: string): StreamEvent[] =>
  [
    ['consumption_spike', 'Is the drawdown a one-off burst?'],
    ['inbound_delay', 'Is stock already coming?'],
    ['duplicate_indent', 'Has someone already raised this?'],
    ['bom_change', 'Is the part superseded?'],
  ].flatMap(([name, input]) => [
    {
      type: 'thread.created',
      threadId: `${prefix}-${name}`,
      parent: { threadId: 'main', toolCallId: 'call-subagents' },
      agentInfo: { name, input },
    },
    {
      type: 'model.message',
      threadId: `${prefix}-${name}`,
      content: `Checked the records for ${name}.`,
    },
    { type: 'thread.done', threadId: `${prefix}-${name}` },
  ])

const VERDICTS_A = [
  { hypothesis: 'consumption_spike', verdict: 'negative', evidence: {}, note: 'No burst; draw is steady at 4.52/day over 119 days.' },
  {
    hypothesis: 'inbound_delay',
    verdict: 'positive',
    evidence: {
      consignments: [
        { consignment_no: 'CN-8821', qty: 200, eta: ETA_A, status: 'unconfirmed' },
      ],
    },
    note: 'CN-8821 is shown against the part but the vendor has not confirmed dispatch.',
  },
  { hypothesis: 'duplicate_indent', verdict: 'negative', evidence: {}, note: 'No open indent for TRB-4417.' },
  { hypothesis: 'bom_change', verdict: 'negative', evidence: {}, note: 'Part is current; no supersession on record.' },
]

const VERDICTS_B = [
  { hypothesis: 'consumption_spike', verdict: 'negative', evidence: {}, note: 'Steady draw at 5.84/day.' },
  {
    hypothesis: 'inbound_delay',
    verdict: 'positive',
    evidence: {
      consignments: [
        { consignment_no: 'CN-9104', qty: 300, eta: ETA_B, status: 'in_transit' },
      ],
    },
    note: 'CN-9104 is confirmed in transit, due 28 Aug.',
  },
  {
    hypothesis: 'duplicate_indent',
    verdict: 'positive',
    evidence: {
      indent_no: 'IND-2026-0731',
      linked_consignment: {
        consignment_no: 'CN-9104',
        qty: 300,
        eta: ETA_B,
        status: 'in_transit',
      },
    },
    note: 'IND-2026-0731 was raised seven days ago and is still open.',
  },
  { hypothesis: 'bom_change', verdict: 'negative', evidence: {}, note: 'Part is current.' },
]

const RECOMMENDATION_A = {
  action: 'raise_indent',
  reason:
    'No benign explanation survives. TRB-4417 draws 4.52/day and runs out in about 9 days (8 at the fast end), against a vendor lead time of 31 days at the 80th percentile. Nothing confirmed is inbound and no indent is open.',
  what_would_change_my_mind:
    `Consignment CN-8821 (200 nos) is shown against TRB-4417 with an ETA of ${ETA_A}, but the vendor has not confirmed dispatch. If that consignment is confirmed and lands by ${ETA_A}, do not raise this indent.`,
  ruled_out: ['consumption_spike', 'duplicate_indent', 'bom_change'],
  urgency: 'critical',
  indent_qty: 200,
}

const RECOMMENDATION_B = {
  action: 'no_action',
  reason:
    `BRK-2290 is already on order. Indent IND-2026-0731 is open and consignment CN-9104 (300 nos) is in transit, due ${ETA_B}, which is inside the 8-day stockout window. Raising another indent would duplicate stock the works has already bought.`,
  what_would_change_my_mind:
    `If consignment CN-9104 slips past ${ETA_B} or is short-shipped, this becomes a genuine shortage.`,
  ruled_out: ['consumption_spike', 'bom_change'],
  urgency: null,
  indent_qty: null,
}

const DRAFT_A = {
  indent: {
    part_no: 'TRB-4417',
    description: 'Traction motor brush holder, Type 4',
    qty: 200,
    uom: 'nos',
    vendor_code: 'V-3301',
    vendor_name: 'Meridian Traction Supplies',
  },
  mail: {
    to: 'stores+vendor@example.invalid',
    subject: 'Indent (allocated on approval) - TRB-4417 - 200 nos',
    body:
      'Dear Meridian Traction Supplies,\n\nPlease supply against indent (allocated on approval):\n\n' +
      '  Part      : TRB-4417\n  Item      : Traction motor brush holder, Type 4\n' +
      `  Quantity  : 200 nos\n  Needed by : ${NEEDED_BY}\n\n` +
      'Kindly confirm dispatch and share the consignment number once despatched.\n\nRegards,\nStores\n',
  },
}

/** Run A: genuine shortage. Ends parked on a human. */
export const RUN_A: StreamEvent[] = [
  { type: 'turn.created', turnId: 'turn-a', threadId: 'main' },
  {
    type: 'model.message',
    threadId: 'main',
    content: 'Stock alert for TRB-4417. Pulling the record.',
    toolCalls: [toolCall('t1', 'get_part', { part_no: 'TRB-4417' })],
  },
  {
    type: 'tool.response',
    threadId: 'main',
    toolCallId: 't1',
    content: JSON.stringify({ part_no: 'TRB-4417', stock_on_hand: 42, reorder_level: 60, reorder_qty: 200 }),
  },
  {
    type: 'model.message',
    threadId: 'main',
    toolCalls: [toolCall('t2', 'get_consumption_log', { part_no: 'TRB-4417', days: 120 })],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 't2', content: JSON.stringify({ row_count: 119 }) },
  ...hypothesisThreads('a'),
  { type: 'sandbox.created', threadId: 'main' },
  {
    type: 'model.message',
    threadId: 'main',
    content: 'Four verdicts in. Adjudicating.',
    toolCalls: [toolCall('t3', 'adjudicate', { part_no: 'TRB-4417', projection: PROJECTION_A, verdicts: VERDICTS_A })],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 't3', content: JSON.stringify(RECOMMENDATION_A) },
  {
    type: 'model.message',
    threadId: 'main',
    toolCalls: [toolCall('t4', 'draft_indent', { part_no: 'TRB-4417', qty: 200 })],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 't4', content: JSON.stringify(DRAFT_A) },
  {
    type: 'model.message',
    threadId: 'main',
    toolCalls: [toolCall('t5', 'raise_indent', { part_no: 'TRB-4417', qty: 200 })],
  },
  { type: 'tool.approval_required', threadId: 'main', toolCalls: [{ id: 't5', sourceEventId: 'e9' }] },
  { type: 'turn.done', threadId: 'main', state: { status: 'done' } },
]

/** Run B: identical alert, and nothing should happen. */
export const RUN_B: StreamEvent[] = [
  { type: 'turn.created', turnId: 'turn-b', threadId: 'main' },
  {
    type: 'model.message',
    threadId: 'main',
    content: 'Stock alert for BRK-2290. Pulling the record.',
    toolCalls: [toolCall('u1', 'get_part', { part_no: 'BRK-2290' })],
  },
  {
    type: 'tool.response',
    threadId: 'main',
    toolCallId: 'u1',
    content: JSON.stringify({ part_no: 'BRK-2290', stock_on_hand: 55, reorder_level: 80, reorder_qty: 300 }),
  },
  ...hypothesisThreads('b'),
  { type: 'sandbox.created', threadId: 'main' },
  {
    type: 'model.message',
    threadId: 'main',
    toolCalls: [toolCall('u2', 'adjudicate', { part_no: 'BRK-2290', projection: PROJECTION_B, verdicts: VERDICTS_B })],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 'u2', content: JSON.stringify(RECOMMENDATION_B) },
  {
    type: 'model.message',
    threadId: 'main',
    content: 'No action. BRK-2290 is already covered.',
    toolCalls: [
      toolCall('u3', 'log_run', {
        session_id: 'turn-b',
        part_no: 'BRK-2290',
        outcome: 'no_action',
        detail: { recommendation: RECOMMENDATION_B },
      }),
    ],
  },
  { type: 'tool.response', threadId: 'main', toolCallId: 'u3', content: JSON.stringify({ id: 2, outcome: 'no_action' }) },
  { type: 'turn.done', threadId: 'main', state: { status: 'done' } },
]
