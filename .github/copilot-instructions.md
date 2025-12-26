# Copilot Instructions for Midori-AI-Mono-Repo

This guide enables coding agents to be immediately productive in this multi-service, multi-agent codebase. 
Follow these actionable instructions to maximize effectiveness and avoid common pitfalls.

## Big Picture Architecture
- The repository is a **multi-project mono-repo**: each major directory (e.g., `Endless-Autofighter`, `Pixelarch-OS`, `Subsystem-Manager`, `Website`) is a distinct service or product, often with its own build/test conventions and agent rules.
- **Service boundaries** are defined by top-level folders. Each service may have its own `AGENTS.md`, `.codex/`, and `README.md` with local rules and workflows.
- **Cross-service integration** is managed via containerization (Docker, Compose) and shared OS images (see `Pixelarch-OS/pixelarch_os/`, `Subsystem-Manager`).
- **Data flows**: Most agent services use Python, with data and models in `data/`, and plugins/extensions in `plugins/` or `mods/`.

## Critical Developer Workflows
- **Python:** Always use [`uv`](https://github.com/astral-sh/uv) for environment management and running code. Avoid direct `python` or `pip` commands.
  - Example: `uv run main.py` or `uv run lyra.py`
- **Node/React:** Use [`bun`](https://bun.sh/) for JS tooling, not `npm` or `yarn`.
- **Testing:** Run tests with `uv run pytest` (Python). Any test running >25s is auto-aborted.
- **Builds:** Container builds use Dockerfiles in service subfolders. Pixelarch OS images use custom Arch-based Dockerfiles (`Pixelarch-OS/pixelarch_os/`).
- **Commits:** Use `[TYPE] Title` format for commit messages and PRs. Example: `[FIX] Resolve agent startup bug`

## Project-Specific Conventions
- **Imports:** Each import on its own line, sorted shortest to longest within groups (stdlib, third-party, project). Blank lines between groups. No inline imports.
- **Documentation:** Update `.codex/implementation/` and `README.md` when changing core logic or adding plugins/players/foes.
- **Plugins:** Place custom modules in `plugins/` or `mods/`. See `.codex/instructions/plugin-system.md` for plugin rules.
  - **Contributor Modes:** Reference `.codex/modes/` for Task Master, Coder, Reviewer, Auditor, Brainstormer, and Prompter roles. Keep your cheat sheet in `.codex/notes/` up to date.
- **Legacy code:** Do not modify code in `legacy/` folders.

## Integration Points & External Dependencies
- **Subsystem-Manager** integrates with external LLMs (LocalAI, Ollama, AnythingLLM, Big-AGI, etc.) via Docker and API calls.
- **Pixelarch OS** provides containerized environments for scalable AI workloads.
- **Endless-Autofighter** uses Panda3D (active branch: Ver2) and supports plugin-based character/enemy extension.

## Key Files & Directories
- `Pixelarch-OS/pixelarch_os/`: Custom OS Dockerfiles
- `README.md` (per-service): Quickstart, architecture, setup
- `AGENTS.md` (global and per-service): Agent rules, contributor practices
- `.codex/` (per-service): Contributor docs, implementation notes, instructions

## Example Patterns
- For new contributor onboarding: start with `AGENTS.md` and `.codex/instructions/` in your target service.
- To add a new player/enemy plugin: update both `README.md` and `.codex/implementation/player-foe-reference.md`.

## Must-Dos
- **Always use thinking tools**: For all coding agents, use tools like `Sequential Thinking` to thoroughly analyze each request from the user.
- **Apply Sequential Thinking process**: For most coding, review, or analysis requests, use the Sequential Thinking process to break down, analyze, and solve problems step by step:
  - Start with an initial thought or hypothesis
  - Before and after each step, deliberately reflect, revise, or branch as needed—never rush ahead without careful consideration
  - Clearly document your reasoning and decisions at every stage, showing your thought process between steps
  - Only conclude when fully confident the problem is completely resolved, with no skipped reasoning
  - Use Sequential Thinking (4 to 10 times, with at least 2 branches) as the default approach for all requests
- **Gather context before acting**: Always collect necessary context using file reading, search, and exploration tools before making changes or assumptions
- **Use appropriate tools for tasks**: Choose the right tool for each situation:
  - Semantic search for understanding codebase concepts and finding relevant code
  - File reading for detailed examination of specific files
  - Grep search for finding specific patterns or getting file overviews
  - Terminal commands for execution, testing, and system operations
- **Read files efficiently**: Prefer reading large meaningful chunks rather than many small sections to minimize tool calls and gain better context
- **Explore workspace systematically**: Use file search and directory listing to understand project structure, then dive deeper into relevant areas
- **Leverage advanced tools for complex tasks**: Use tools like Codex MCP server for challenging tasks that require deep analysis, complex problem-solving, or when you need additional expertise beyond your individual capabilities. Collaborate with these systems to achieve better results on difficult or multi-faceted problems

---

For unclear or missing instructions, check the relevant service's `AGENTS.md` and `.codex/instructions/`, then ask for feedback to improve this guide.
