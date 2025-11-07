# Swarm-o-codex

Swarm-o-codex is a persona-driven orchestration layer for large reasoning models (LRMs). It lets you run the same multi-agent workflow entirely on your own hardware or through your preferred cloud provider, giving you a portable swarm that can tackle coding, auditing, storytelling, and custom automation tasks.

## About the Project

- **Multi-backend execution:** Toggle between a local LRM (default `gpt-oss:20b`) and cloud APIs (`gpt-5` or your configured endpoint) with `SWARM_RUN_LOCAL`, keeping the rest of the workflow identical.
- **Persona-first workflow:** Specialized agents—Task Master, Manager, Coder, Reviewer, Auditor, Storyteller—collaborate via managed handoffs so every run ends with a Manager-signed completion.
- **Tool-augmented reasoning:** Bundled Model Context Protocol servers (Playwright, Context7, Sequential Thinking) expand what each agent can do, from browsing to reflective planning, with shared streaming and audit trails.
- **Workspace-aware CLI:** `swarm-cli.py` pairs with `cli/env_cli.py` to initialize local workspaces, select environments, and run scripted or interactive tasks with consistent prompts.
- **Extensible by design:** Persona prompts live in `personas/`, MCP configuration sits in `setup/mcp.py`, and you can add new agents or tools without rewriting the orchestration layer.

## Test it out
Run the below command to try out the swarm locally
```bash
uv run swarm-cli.py --env
```

## Setup Guide

This project uses Codex CLI as the primary developer interface, and `uv` for Python tooling. Follow the sections below to prepare your environment.

## Install Codex CLI

Codex CLI powers the workflows defined in this repository. - https://github.com/openai/codex

```bash
npm install -g @openai/codex
```

## Install uv

The project manages Python environments and dependencies using `uv`. - https://docs.astral.sh/uv/getting-started/installation/

```bash
wget -qO- https://astral.sh/uv/install.sh | sh
```

## Disclaimer

- Midori AI does not support Windows and will not assist with installation on that OS.
- Where possible, prefer your system package manager (for example: `yay`, `apt`, or `dnf`) or the distro-provided packages over installing tools globally via `npm` or running arbitrary install scripts. Using your package manager generally provides safer, more maintainable installs and integrates better with your system.

