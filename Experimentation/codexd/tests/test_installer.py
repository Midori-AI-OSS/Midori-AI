from __future__ import annotations

from pathlib import Path

from codexd.installer import build_wrapper_script


def test_wrapper_script_points_to_project_and_uv_environment() -> None:
    script = build_wrapper_script(Path("/tmp/codexd"))

    assert "UV_PROJECT_ENVIRONMENT=/tmp/midoriai/codexd" in script
    assert 'exec uv run --project "/tmp/codexd" codexd "$@"' in script
