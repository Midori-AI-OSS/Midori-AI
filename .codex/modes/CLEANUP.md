# Cleanup Mode (Pipeline Hygiene)

## Purpose
Cleanup Mode prevents subagents from stepping on each other by centralizing cleanup into a single, explicit step. It is for safely pruning temporary artifacts (especially blog pipeline leftovers) after a run is complete.

## Default behavior (safe)
- Only touch files under `/tmp/agents-artifacts/`.
- Do not delete or modify files inside the workspace repository working tree (including `.codex/blog/staging/`) unless explicitly instructed.
- Do not run git commands that change state (no fetch/pull/checkout/submodule update; no `git add`/commit).

## Blog pipeline cleanup (common)
1) Confirm the run is finished (no gatherers/prompter actively writing artifacts).
2) Verify the final handoff exists:
   - `/tmp/agents-artifacts/blogger-handoff.md`
3) Remove only clearly-intermediate files in `/tmp/agents-artifacts/` created by the gatherers/helpers, for example:
   - `change-diff-gatherer-diff-*.patch`
   - `change-diff-gatherer-sum-*.md`
   - helper logs or scratch outputs you created for the run

## Optional staging cleanup (only if explicitly requested)
If asked to clean `.codex/blog/staging/`, do not delete inputs while another run might still be reading them. Prefer leaving staged briefs in place, or do cleanup only after the Coordinator confirms nothing else will read them.

## Prohibited actions
- Deleting `.codex/blog/staging/` files as part of Blog-Prompter or any evidence-gathering mode.
- Deleting `blogger-handoff.md`.
