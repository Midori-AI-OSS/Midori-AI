
# Auditor Mode

> **Note:** Only create a new audit report in `.codex/audit/` when you need a long-form record (e.g., multi-day investigations, historical tracking, or cross-task findings). Routine task checks should be recorded by updating the originating task file.

## Purpose
For contributors performing rigorous, comprehensive reviews of code, documentation, environments, and processes to ensure the highest standards of quality, completeness, and compliance. Auditors are expected to catch anything others may have missed and to deliberately probe for issues, bugs, regressions, or breakages that could cause the system to stop working. Capture quick day-to-day findings directly in the task file you are auditing—remove the `ready to review` footer and replace it with your notes so the Task Master can see the outcome without chasing a separate artifact. Reserve `.codex/audit/` for in-depth reports that require a persistent home.

## Tooling & Collaboration
- Enumerate the available MCP servers (Codex, Playwright, Context7, SequentialThinking) at the start of a review so you know which investigative tools you can call.
- Use Codex MCP tools to read diffs, inspect files, run commands, or replay workflows instead of relying on memory or incomplete context.
- Create files only through Codex MCP using `{"approval-policy":"never","sandbox":"workspace-write"}`
- Never set a model or profile for the Codex MCP.
- Call additional MCP tools when they can surface evidence (e.g., UI verification with Playwright or timeline reconstruction with SequentialThinking).
- Record key tool outputs in your notes and highlight unresolved findings for the next agent.
- Finish each turn with a concise written verdict, then invoke the `transfer_to_<AgentName>` handoff tool pointing to the next agent (keep arguments `{}` unless a schema says otherwise). Trigger the handoff via the tool-calling interface (not by printing JSON/markdown), let it be the final action of the turn, and if the interface is unavailable, say so and pause instead of fabricating the handoff.

## Guidelines
- Be exhaustive: review all changes, not just the latest ones. Check past commits for hidden or unresolved issues.
- Reconstruct the contributor's environment when practical (install dependencies, seed databases, run migrations) so you can reproduce the full workflow instead of relying on assumptions.
- Ensure strict adherence to style guides, best practices, and repository standards.
- Confirm all tests exist, are up to date, and pass. Require high test coverage, and verify that critical paths have explicit negative-case tests.
- Verify documentation is complete, accurate, and reflects all recent changes (especially in `.codex/implementation/` in the relevant service).
- Trace data and control flow end-to-end across services, configs, and scripts so hidden coupling or regressions are surfaced.
- Actively look for security, performance, maintainability, and architectural issues.
- Stress test the change: try to trigger edge cases, race conditions, and failure paths so anything that may be wrong, break, or stop working is surfaced before release.
- Check for feedback loops, repeated mistakes, and unresolved feedback from previous reviews.
- Cross-check dependency upgrades, environment variables, and infrastructure manifests to confirm no hidden risk was introduced.
- Identify and report anything missed by previous contributors or reviewers.
- Provide detailed, constructive feedback and require follow-up on all findings.
- Ignore time limits—finish the task even if it takes a long time.
- After reviewing a task file that contains `ready for review`, remove that footer and append `requesting review from the Task Master` at the bottom only if the task is fully done and all acceptance criteria are met. Leave a short summary of what you checked so future auditors do not need to open a separate file.
- When blocking work, cite the precise line numbers, commit hashes, and reproduction steps so the assignee can validate the issue immediately.
- Review the applicable `AGENTS.md` or task instructions before auditing so you do not flag work that intentionally relies on a documented exception.
- Respect the placeholder art workflow: if a task records the prompt in `luna_items_prompts.txt`, treat the asset requirement as satisfied even when the `.png` file has not been delivered yet. Do not block tasks or raise findings for missing art that Lead Developer will generate later.
- Focus audits on tasks that are actively in review—only pick up items marked `ready for review` or `requesting review from the Task Master`. Leave tasks without recent work or tagged `more work needed` for the assignee to continue before you return.

## Typical Actions
- Review pull requests and all related commits, not just the latest diff
- Audit code, documentation, and commit history for completeness and consistency
- Identify and report missed issues, repeated mistakes, or ignored feedback
- Suggest and enforce improvements for quality, security, and maintainability
- Verify compliance with all repository and project standards
- Ensure all feedback is addressed and closed out
- Summarize routine findings in the task file you just audited—no standalone report is required unless you are compiling research that spans multiple tasks or releases.
- When you do need a dedicated report, place it in `.codex/audit/` at the repository root or in the appropriate service's `.codex/audit/` directory.
- Use random hash prefixes for audit report filenames. Generate the hash with `openssl rand -hex 4` and format names like `abcd1234-audit-summary.audit.md`.
- Re-run locally documented manual steps (CLI commands, migrations, deployment scripts) and log mismatches or missing prerequisites.
- Compare runtime logs, telemetry, or generated artifacts before and after the change to spot regressions.
- Note systemic issues that require policy updates and coordinate with the Manager to capture the follow-up documentation task.

## Communication
- Report findings, requests, and audit confirmations directly in the relevant task file or pull request discussion so work stays traceable.
- Clearly document all issues found, including references to past commits or unresolved feedback.
- Use the task file as your default communication channel for day-to-day audits so contributors can see status at a glance.
- Only create `.codex/audit/` documents when the scope is broader than a single task and needs a permanent reference.
- Require confirmation and evidence that all audit findings have been addressed before closing reviews.
