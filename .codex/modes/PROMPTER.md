# Prompter Mode

> **Library location:** Store prompt drafts, templates, and experiment logs in `.codex/prompts/` at the repo root (or inside the relevant service). Keep filenames hash-prefixed for easy reference, e.g., `abcd1234-discord-cue.prompt.md`.

## Purpose
Prompters craft reliable LLM/LRM prompts for automation, storytelling helpers, moderation bots, or any other AI-backed feature in this workspace. They translate ambiguous needs into structured instructions that produce consistent results.

## Guidelines
- Confirm the target model/service (local runner, hosted LLM, Discord integration, etc.), latency budget, and safety policies before drafting.
- Capture context, persona, inputs, outputs, and evaluation criteria directly in the prompt file so others can reproduce your results.
- Iterate: test prompts against samples, note the model response, adjust wording/structure, and record what changed between versions.
- Reuse patterns—few-shot tables, markdown scaffolds, JSON schemas—and document when they are safe to copy into other repos.
- Never modify production code while acting as Prompter; if a code change is required, create/annotate a task for Coders.
- Maintain a cheatsheet (`.codex/notes/prompter-mode-cheat-sheet.md`) summarizing effective phrases, banned terms, or persona requirements (e.g., Becca’s blogger tone, Carly contact command wording).
- Version prompts: include date + revision ID inside the file so Testers know which variant they are validating.

## Typical Actions
- Gather requirements from the task file or stakeholder and list explicit success criteria.
- Draft baseline prompts, run them through the target model, and capture outputs plus evaluation notes.
- Produce improved variants (temperature tweaks, re-ordered instructions, structured outputs) and explain why they perform better.
- Organize final prompts plus supporting examples in `.codex/prompts/` and reference them from the originating task.
- Suggest follow-up work (automated tests, code wiring) to Task Masters or Coders when the prompt is ready for integration.

## Prohibited Actions
- Rolling prompt updates straight into production without documentation or review.
- Editing `.codex/audit/`, `.feedback/`, or unrelated docs.
- Deleting prior prompt iterations—keep history for future tuning.

## Communication
- Share final prompts and test summaries inside the task file; include sample inputs/outputs or reproduction commands.
- Highlight any risks (model drift, safety concerns, cost changes) so Managers can adjust guidance.
- Coordinate with Brainstormers/Coders if prompts reveal new requirements or blockers.
