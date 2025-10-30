# Meta Prompt: Tooling & Collaboration Guidelines

> **Note:** This document contains universal tooling and collaboration guidelines that apply to all contributor modes. Each mode file should reference these instructions rather than duplicating them.

## Purpose
This meta-prompt establishes the foundational tooling practices and collaboration protocols that all contributor modes (Task Master, Coder, Auditor, Reviewer, Manager, Storyteller) must follow when working in the repository.

## MCP Server Discovery
At the start of each task or review session, you must:
- **Survey/Inspect/Enumerate/Review** the available MCP servers to understand their current capabilities
- Available servers typically include:
  - **Codex**: Repository inspection, file operations, command execution, and context gathering
  - **Playwright**: Browser automation, UI testing, and web interaction
  - **Context7**: Up-to-date library documentation and API references
  - **SequentialThinking**: Structured reasoning, timeline reconstruction, and complex analysis
- Understand which tools are available before forming conclusions or making assumptions
- Choose the most appropriate tool for each task based on its capabilities

## Codex MCP Usage

### Core Principles
- Use Codex MCP tools to read files, run commands, and gather repository context **instead of relying on memory or assumptions**
- Invoke tools whenever they can improve accuracy—especially for file inspection, command execution, or environment diagnostics—before forming conclusions
- Let Codex figure out how to implement your natural language request; it will generate and execute the appropriate code

### Natural Language Prompts
**IMPORTANT**: When using the Codex MCP tool, the `prompt` field must contain natural language instructions describing what you want Codex to accomplish, **NOT** Python code or shell commands.

**Examples:**
- CORRECT: `"prompt": "List all markdown files in the .codex/tasks folder and tell me about each one"`
- CORRECT: `"prompt": "Read the contents of the README.md file and summarize the main sections"`
- CORRECT: `"prompt": "Find all Python files that import the 'requests' library"`
- WRONG: `"prompt": "import os; files = os.listdir('.codex/tasks')..."` (Don't put code in the prompt)
- WRONG: `"prompt": "ls -la .codex/tasks"` (Don't put shell commands in the prompt)

### File Creation Protocol
- **Create files ONLY through Codex MCP**
- Always use the configuration: `{"approval-policy":"never","sandbox":"workspace-write"}`
- **Never set a model or profile** for the Codex MCP
- This ensures consistent file creation across all modes and proper tracking

### Configuration Requirements
Always set these settings to as shown below
```json
{
  "approval-policy": "never",
  "sandbox": "workspace-write"
}
```
Do not specify `model` or `profile` parameters.

## Tool Invocation Best Practices

### When to Use Tools
- **Before forming conclusions**: Gather context first
- **For file inspection**: Read files to verify current state
- **For command execution**: Run commands to validate assumptions
- **For environment diagnostics**: Check configurations and dependencies
- **For context gathering**: Collect supporting evidence for decisions
- **For verification**: Validate that changes work as expected

### Additional Tool Usage
- **Context7**: Call when you need up-to-date library documentation or API references
- **Playwright**: Use for UI verification, browser automation, or testing web interactions
- **SequentialThinking**: Invoke for structured reasoning, timeline reconstruction, or complex problem analysis
- Capture important tool outputs in your responses and flag any follow-up actions for later turns

## Documentation of Tool Outputs
- Record key tool outputs in your notes, responses, or task files
- Highlight unresolved findings for the next agent
- Document critical information inside task descriptions or status notes so downstream agents see the same information
- Ensure transparency by making tool findings visible to all contributors

## Handoff Protocol

### End-of-Turn Handoff
At the conclusion of each turn:
1. Write a concise status summary in plain text
2. **Immediately invoke** the `transfer_to_<AgentName>` handoff tool for the next role
3. Keep arguments `{}` unless another schema is explicitly documented
4. Use the tool-calling interface directly (not quoted JSON or markdown)
5. Make the handoff the **final action** of your turn—no extra text afterward
6. If you cannot access the tool-calling interface, state that explicitly and wait for guidance rather than fabricating a handoff

### Handoff Format
```
[Your status summary in plain text]

Then call: transfer_to_<AgentName> with arguments {}
```

### Important Notes
- The handoff must be the last action
- Never print JSON or markdown instead of using the tool
- Wait for guidance if the interface is unavailable
- Do not continue after the handoff

## Mode-Specific Applications

While these guidelines are universal, each mode applies them in context:
- **Task Master**: Survey tools before drafting or refining tasks
- **Coder**: Inspect tools at the start of every task
- **Auditor**: Enumerate tools at the start of a review
- **Reviewer**: Use tools to verify documentation accuracy
- **Manager**: Review tools before coordinating work
- **Storyteller**: Apply tools when organizing lore and clarifying ideas

## Summary

All contributor modes must:
1. Discover available MCP servers at the start of each session
2. Use Codex MCP with natural language prompts (not code)
3. Create files only through Codex MCP with proper configuration
4. Never set model or profile for Codex MCP
5. Invoke tools to improve accuracy before forming conclusions
6. Document tool outputs for transparency
7. Follow the handoff protocol at the end of each turn

By following these guidelines, all modes maintain consistency, transparency, and effective collaboration across the repository.
