from __future__ import annotations

from pathlib import Path


def build_wrapper_script(project_root: Path) -> str:
    return "\n".join(
        [
            "#!/usr/bin/env sh",
            "export UV_PROJECT_ENVIRONMENT=/tmp/midoriai/codexd",
            "export UV_COMPILE_BYTECODE=1",
            f'exec uv run --project "{project_root}" codexd "$@"',
            "",
        ],
    )
