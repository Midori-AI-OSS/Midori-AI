
# Meta

Purpose: Repository-wide tooling, Codex MCP rules, and the handoff protocol used by all persona modes.

Core rules:
- Always start a task by invoking SequentialThinking to plan and structure reasoning.
- Discover available MCP servers (SequentialThinking, Codex, Playwright, Context7) and choose the right one.
- Create files only via Codex MCP with configuration: {"approval-policy":"never","sandbox":"workspace-write"}. Do not set model or profile.
- Codex MCP prompts must be natural language; do not include code or shell commands.

Handoff protocol:
- Provide context (summary, file paths, actions needed) in your message, then as your final step call `transfer_to_<AgentName>` with `{}`. Do not hand off to your own role.
- When handing off, include a brief instruction to the next agent about what needs to be done.
- Note: the transfer tool name must be lowercase (for example, `transfer_to_task_master`).

Tool usage:
- Use SequentialThinking for planning, Codex for repo edits/reads, Context7 for library docs, Playwright for UI tests.
- Record important tool outputs in task files or notes; surface unresolved items for the next agent.

Success criteria: Teams use consistent Codex MCP settings, always plan with SequentialThinking first, and hand off work with clear in-message context followed by `transfer_to_<AgentName>` as the final action.

