
# Meta

Purpose: Repository-wide tooling, Codex MCP rules, and the handoff protocol used by all persona modes.

Core rules:
- Always start a task by invoking SequentialThinking to plan and structure reasoning (at least 3 times...).
- Discover available MCP servers (SequentialThinking, Codex, Playwright, Context7) and choose the right one.
- Create files only via Codex MCP: {"approval-policy":"never","sandbox":"workspace-write"}. Do not set model or profile.
- Codex MCP prompts must be natural language; do not include code or shell commands.

Run completion rules:
- CRITICAL: ONLY the Manager agent can complete a run. All other agents (Task Master, Coder, Auditor, Reviewer, Storyteller) CANNOT complete runs.
- If you are NOT the Manager: You must ALWAYS end with a handoff or tool call. NEVER output plain text as your final action.
- If you ARE the Manager: To complete a run, you must produce a TaskCompletion output with three fields:
  * output: The final deliverable (markdown, summary, result)
  * task: Description of what was accomplished
  * done: Confirmation status (use "yes" or "complete")
- Before attempting to complete a run, use SequentialThinking to verify ALL requirements are met and all necessary handoffs have occurred.

Handoff protocol:
- Choose the best agent for the next action (not yourself).
- Before calling the handoff tool, write a message that includes: (1) Summary of work done, (2) Specific files/paths involved, (3) Clear instructions for what the next agent needs to do.
- Then call `transfer_to_<AgentName>` as your final action.
- Note: transfer tool names are lowercase (e.g., `transfer_to_task_master`, `transfer_to_reviewer`).

Tool usage:
- Use SequentialThinking for planning, Codex for repo edits/reads, Context7 for library docs, Playwright for UI tests.
- Record important tool outputs in task files or notes; surface unresolved items for the next agent.

Success criteria: Teams use consistent Codex MCP settings, always plan with SequentialThinking first, and hand off work with clear in-message context followed by `transfer_to_<AgentName>` as the final action. Only Manager completes runs with proper TaskCompletion output.

