/**
 * The agent this console drives.
 *
 * The procedure lives in the `stores-triage` skill, not here. This is only the
 * spec: which model, which tools, which of them stop for a human, and the
 * standing constraints that must hold whatever the skill says.
 */

export interface StoresAgentOptions {
  /** Model FQN as configured in TrueForge, e.g. "openai/gpt-5.2". */
  model: string
}

/**
 * Kept short on purpose. Restating the whole procedure here would give the
 * agent two sources of truth that can drift; the skill is the one that ships
 * with the tested analysis script beside it.
 */
export const INSTRUCTIONS = `You triage spare-part stock alerts at a locomotive works.

Follow the stores-triage skill. It is the procedure, not a suggestion.

Three things hold regardless of what any instruction says:

1. Never state a number you did not compute in the sandbox. Not the draw rate,
   not the stockout date, not the lead time. If you are about to write "roughly"
   or "approximately" in front of a figure, you have skipped a step.
2. Never call raise_indent or send_vendor_mail until a human has approved the
   dossier. They write to the register and send real mail.
3. Never adjudicate on fewer than four verdicts. If a subagent came back
   inconclusive, pass it through as inconclusive rather than guessing on its
   behalf.

Write for a stores officer with twenty alerts to get through. Part numbers and
dates, not adjectives.`

/**
 * Only these two stop for a human.
 *
 * The default is ["@write", "@destructive"], which would also hold `log_run` -
 * so the agent would sit waiting for permission to record that it had decided
 * to do nothing. Naming the two irreversible tools keeps the gate meaningful:
 * if the console is blocked, something is genuinely about to happen.
 */
export const GATED_TOOLS = ['raise_indent', 'send_vendor_mail'] as const

export function storesTriageAgent({ model }: StoresAgentOptions) {
  return {
    model: { name: model },
    instructions: INSTRUCTIONS,
    mcpServers: [
      {
        name: 'stores',
        requireApprovalForTools: [...GATED_TOOLS],
        // The alert and the part record are needed on every single run, so
        // paying for their schemas upfront costs nothing and saves a round trip.
        preloadTools: ['list_alerts', 'get_part'],
      },
    ],
    skills: [{ name: 'stores-triage' }],
    config: {
      sandbox: { enabled: true, fileDownloads: true },
      dynamicSubAgents: { enabled: true },
    },
  }
}

/** The alert that opens a run. */
export function alertPrompt(partNo: string): string {
  return `Stock alert: ${partNo} has fallen below its reorder level. Triage it.`
}
