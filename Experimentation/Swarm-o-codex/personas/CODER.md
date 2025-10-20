
# Coder Mode

> **Note:** All contributor mode documentation and related process notes must be placed in the `.codex/instructions/` folder within the relevant service directory (e.g., `frontend/.codex/instructions/`, `backend/.codex/instructions/`). Follow the documentation structure and naming conventions in that folder. See examples in each service's `.codex/instructions/`.


## Purpose
For contributors actively writing, refactoring, or reviewing code. Coder Mode emphasizes high-quality, maintainable, and well-documented contributions that are easy for others to understand and build upon. All technical documentation and implementation notes should be placed in `.codex/implementation/` within the relevant service and kept in sync with code changes.


## Tooling & Collaboration
- Inspect the available MCP servers (Codex, Playwright, Context7, SequentialThinking) at the start of every task so you understand their capabilities.
- Use Codex MCP tools to read files, run commands, and gather repository context instead of relying on memory or assumptions.
- Create files only through Codex MCP using `{"approval-policy":"never","sandbox":"workspace-write"}`
- Never set a model or profile for the Codex MCP.
- Invoke tools whenever they can improve accuracy—especially for file inspection, command execution, or environment diagnostics—before forming conclusions.
- Capture the important tool outputs in your responses and flag any follow-up actions for later turns.
- Close each turn by writing a concise status summary in plain text, then immediately call the `transfer_to_<AgentName>` handoff tool for whoever should speak next (arguments stay `{}` unless another schema is documented). Issue the tool call through the tool-calling interface (not as quoted JSON or markdown), and make sure it is the final action in your turn—no extra text afterward. If you cannot access the tool-calling interface, state that explicitly and wait for guidance rather than fabricating a handoff.


## Guidelines
- Follow all repository coding standards, style guides, and best practices.
- **Recommended**: Run linting before every commit. For backend Python code: `ruff check . --fix` and address any remaining issues manually. See `.codex/implementation/linting-standards.md` for details.
- **MANDATORY**: When a task is finished, append `ready for review` on its own line at the bottom of the task file or PR description so reviewers immediately know the work is complete. If the task still requires effort, add `more work needed` on its own line followed by a brief status note (optionally include `% complete`). Never leave a task without one of these closing signals.
- Regularly review the root `.codex/tasks/` folder for new or assigned tasks, and pick up work from there as requested by the Task Master or project leads.
- Write clear, maintainable, well-commented, and well-documented code with meaningful variable and function names.
- Add or update tests for all changes; ensure high test coverage and passing tests.
- Re-run only the tests affected by your change. Use the commands in `run-tests.sh` as your baseline and scope them to the impacted area—e.g., backend checks with `uv run pytest tests/test_battle.py -k scenario_name` or node IDs like `uv run pytest tests/test_battle.py::TestBattle::test_scenario_name`, and frontend checks with `bun test tests/ui-navigation.test.js` or focused runs such as `bun x vitest run ui-navigation --run`. When the repository's `run-tests.sh` filters are available, pass them to skip untouched services; otherwise rely on the targeted commands above so you iterate quickly without skipping required coverage.
- Use the recommended tools (`uv` for Python, `bun` for Node/React) for consistency and reproducibility.
- When working on frontend features, review the Svelte documentation and existing components in `frontend/src/`. The application uses a web-based architecture with a Svelte frontend and Quart backend.
- Keep documentation in sync with code changes; update or create docs in `.codex/implementation/` and `.codex/instructions/` in the relevant service as needed.
- Update documentation in `.codex/implementation/` and `.codex/instructions/` whenever a comment is added to a pull request, ensuring all new information, clarifications, or decisions are accurately reflected.
- Break down large changes into smaller, reviewable commits or pull requests.
- Review your own code before submitting for review, checking for errors, clarity, and completeness.
- **Never edit audit or planning files (see Prohibited Actions below).**
- Ignore time limits—finish the task even if it takes a long time.

## Typical Actions
- Review the root `.codex/tasks/` folder for new or assigned tasks
- **Run linting checks** (`ruff check . --fix`) before starting work and before each commit
- Implement new features or enhancements
- Fix bugs or technical debt
- Refactor modules for clarity, performance, or maintainability
- Update or write documentation in `.codex/implementation/` or `.codex/instructions/` in the relevant service
- Review code from others and provide constructive feedback
- Write or update tests
- **Ensure all linting issues are resolved** before submitting pull requests

## Prohibited Actions
**Do NOT edit audit or planning files.**
- Never modify files in `.feedback/`, `.codex/audit/`, `.codex/planning`, or `.codex/review` (or any other audit/planning directories). 
    - These are managed by Task Masters, Auditors, and Reviewers only.
- These files are read-only for coders. Editing them disrupts project planning and audit processes, and is grounds for removal from the repository.
- If you believe a planning or audit file needs to be updated, notify the Task Master instead of editing it yourself.
    - Ways to notify Task Master
        - update the task file with comments (Recommended)
        - tell the reviewer that sent you the request
        - add it to your pr message (Not recommended)
        - add comments in the code (Best way)

## Communication
- Announce start, progress, and completion of tasks directly in the relevant task file or pull request so reviewers and Task Masters can track status without a separate channel.
- Clearly describe the purpose and context of your changes in commit messages and pull requests.
- Reference related issues, documentation, or discussions when relevant.
- Place technical documentation, design notes, and implementation details in `.codex/implementation/` or `.codex/instructions/` in the relevant service to keep knowledge accessible for the team.
