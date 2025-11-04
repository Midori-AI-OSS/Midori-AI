# Swarm-o-codex

Swarm-o-codex is a persona-driven orchestration layer for large reasoning models (LRMs). It lets you run the same multi-agent workflow entirely on your own hardware or through your preferred cloud provider, giving you a portable swarm that can tackle coding, auditing, storytelling, and custom automation tasks.

## About the Project

- **Multi-backend execution:** Toggle between a local LRM (default `gpt-oss:20b`) and cloud APIs (`gpt-5` or your configured endpoint) with `SWARM_RUN_LOCAL`, keeping the rest of the workflow identical.
- **Persona-first workflow:** Specialized agents—Task Master, Manager, Coder, Reviewer, Auditor, Storyteller—collaborate via managed handoffs so every run ends with a Manager-signed completion.
- **Tool-augmented reasoning:** Bundled Model Context Protocol servers (Playwright, Context7, Sequential Thinking) expand what each agent can do, from browsing to reflective planning, with shared streaming and audit trails.
- **Workspace-aware CLI:** `swarm-cli.py` pairs with `cli/env_cli.py` to initialize local workspaces, select environments, and run scripted or interactive tasks with consistent prompts.
- **Extensible by design:** Persona prompts live in `personas/`, MCP configuration sits in `setup/mcp.py`, and you can add new agents or tools without rewriting the orchestration layer.

## Setup Guide

This project uses Codex CLI as the primary developer interface, and `uv` for Python tooling. Follow the sections below to prepare your environment.

## Install Git

Ensure Git is installed and configured.

```bash
# Placeholder: lead developer to add Git installation instructions
```

## Install Codex CLI

Codex CLI powers the workflows defined in this repository.

```bash
# Placeholder: lead developer to add Codex CLI installation instructions
```

## Install uv

The project manages Python environments and dependencies using `uv`.

```bash
# Placeholder: lead developer to add uv installation instructions
```
