/**
 * The agent this console drives.
 *
 * The procedure lives in the `stores-triage` skill, not here. This is only the
 * spec: which model, which tools, which of them stop for a human, and the
 * standing constraints that must hold whatever the skill says.
 */

export interface StoresAgentOptions {
  /** Model FQN as configured in TrueForge, e.g. "google-gemini/gemini-3-6-flash". */
  model: string
}

/**
 * Free-tier quota is the binding constraint, not cost per token.
 *
 * Gemini's free tier allows 5 requests/minute per model, and a full run is the
 * root agent plus four subagents - comfortably past that. Subagents inherit the
 * root's model (AgentSpec.model is singular and DynamicSubAgentsConfig has no
 * model field), so the whole run shares one bucket and the only lever is making
 * fewer round trips.
 */
export const DEFAULT_MODEL = 'google-gemini/gemini-3-6-flash'

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
        // Every tool here gets used on a normal run and there are only twelve,
        // so loading the schemas upfront costs one small prompt instead of a
        // discovery round trip per subagent. On a 5-requests-per-minute free
        // tier, round trips are the scarce resource, not tokens.
        preload: true,
      },
    ],
    skills: [{ name: 'stores-triage' }],
    config: {
      sandbox: { enabled: true, fileDownloads: true },
      dynamicSubAgents: { enabled: true },
      // The whole premise is that the agent never asks for permission bare.
      // Left enabled, it does exactly that: the first live run reached the
      // decision and then called ask_user_question with "Do you approve raising
      // an indent of 200 nos for TRB-4417?" - no evidence, no payload, no
      // counterfactual, and no held tool call for the harness to gate. A confirm()
      // box with the dossier deleted. Turning the tool off leaves one route to a
      // human, which is calling the gated tool and letting the harness hold it.
      askUserQuestions: { enabled: false },
      // A runaway loop on a 5 RPM quota does not just waste money, it burns the
      // minute budget that the next attempt needs. Fail fast instead.
      iterationLimit: 40,
    },
  }
}

/** The alert that opens a run. */
export function alertPrompt(partNo: string): string {
  return `Stock alert: ${partNo} has fallen below its reorder level. Triage it.`
}
