
import atexit
import shutil
import tempfile

from pathlib import Path
from agents.mcp import MCPServerStdioParams

def setup_mcp(local_model_str: str, local_ip_address: str):
    #### Edit the local params as you see fit
    codex_home = Path(tempfile.mkdtemp(prefix="codex_midori_ai_"))
    config_lines = [f'model = "{local_model_str}"', 'model_provider = "midoriai"', '', '[model_providers.midoriai]', 'name = "Midori AI (local)"', f'base_url = "{local_ip_address}/v1"', 'wire_api = "chat"']
    config_path = codex_home / "config.toml"
    config_path.write_text("\n".join(config_lines) + "\n")

    atexit.register(lambda: shutil.rmtree(codex_home, ignore_errors=True))

    cloud_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "mcp-server"]})
    local_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "mcp-server"], "env": {"CODEX_HOME": str(codex_home)}})

    plan_tool_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "taskqueue-mcp"]})
    playwright_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "@playwright/mcp@latest"]})
    context_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "@upstash/context7-mcp@latest"]})
    sequential_thinking_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking@latest"]})

    # Add additional MCP servers by appending (name, params) tuples to this list.
    additional_mcp_servers: list[tuple[str, MCPServerStdioParams]] = [
        ("Plan", plan_tool_params),
        ("Context7", context_params),
        ("Playwright", playwright_params),
        ("SequentialThinking", sequential_thinking_params),
    ]

    return cloud_params, local_params, additional_mcp_servers