# Agent Notes

- Run locally: `uv run main.py`
- UI styling: `codex_local_conatinerd/style.py` (Qt stylesheet) and `codex_local_conatinerd/widgets.py` (custom-painted widgets)
- Design constraint: keep sharp/square corners (avoid `border-radius` and `addRoundedRect(...)`)
- Code style: Python 3.13+, type hints, minimal diffs (avoid drive-by refactors)
