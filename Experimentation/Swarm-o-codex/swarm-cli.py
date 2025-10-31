
import os
import logging
import asyncio
import tempfile
import atexit
import shutil

from pathlib import Path
from copy import deepcopy
from dotenv import load_dotenv

from agents import Agent
from agents import Runner
from agents import Handoff
from agents import handoff
from agents import RunConfig
from openai import AsyncOpenAI
from agents import ModelSettings
from contextlib import AsyncExitStack

from agents.logger import logger
from agents.mcp import MCPServerStdio
from agents import OpenAIResponsesModel
from openai.types.shared import Reasoning
from agents.mcp import MCPServerStdioParams
from agents import OpenAIChatCompletionsModel
from agents.extensions import handoff_filters

from shared.streaming import console
from shared.streaming import stop_spinner
from cli.env_cli import run_env_selector
from shared.getnetwork import get_local_ip
from shared.streaming import describe_event
from shared.handoff_utils import create_agent_summary_filter

from setup.mcp import setup_mcp
from setup.prompts import setup_agents
from setup.prompts import setup_summary_agent

load_dotenv(override=True)

api_key: str | None = os.getenv("OPENAI_API_KEY")

if api_key: pass
else: api_key = "hello wolrd"

# Configure logging level (default to ERROR to reduce noise). Override with SWARM_LOG_LEVEL.
_log_level = os.getenv("SWARM_LOG_LEVEL", "ERROR").upper()
try:
    log_level_value = getattr(logging, _log_level, logging.ERROR)
    logger.setLevel(log_level_value)
    # Also configure root logger to suppress MCP validation warnings
    logging.getLogger().setLevel(log_level_value)
except Exception:
    logger.setLevel(logging.ERROR)
    logging.getLogger().setLevel(logging.ERROR)

known_endpoints: list[str] = ["https://api.groq.com/openai"]

#### Change / set this for cloud support
local_env = os.getenv("SWARM_RUN_LOCAL", "true").strip().lower()
local: bool = local_env not in ("0", "false", "no", "off")

#### This only works with LRMs not LLMs 
#### (If your using ollama make sure you have context set to >= 32000)
local_model_str: str = "gpt-oss:20b"
cloud_model_str: str = "gpt-5"

#### Update this to change the ip, do not use localhost
local_ip_address: str = f"http://{get_local_ip(fallback='192.168.10.27')}:11434"

remote_openai_base_url: str = os.getenv("SWARM_REMOTE_OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")

#### Local only Async friendly OpenAI obj, changes not needed most of the time...
local_openai = AsyncOpenAI(base_url=f"{local_ip_address}/v1", api_key=api_key)

#### This sets up the params for MCP servers, go check the setup mcp.py folder!
cloud_params, local_params, additional_mcp_servers = setup_mcp(local_model_str, local_ip_address)

if local:
    model = OpenAIChatCompletionsModel(model=local_model_str, openai_client=local_openai)
    mcp_params = local_params
else:
    model = OpenAIResponsesModel(model=cloud_model_str, openai_client=AsyncOpenAI(api_key=api_key))
    mcp_params = cloud_params

reasoning = Reasoning(effort="low", generate_summary="detailed", summary="detailed")
base_model_settings = ModelSettings(reasoning=reasoning, parallel_tool_calls=False, tool_choice="required")

handoffs = setup_agents(model, base_model_settings)
summarizer = setup_summary_agent(model, base_model_settings)
run_config = RunConfig(handoff_input_filter=create_agent_summary_filter(summarizer))

#### This is the main def, this runs the logic for the swarm.
async def main(request: str, workdir: str) -> None:
    build_request: str = f"Working in the `{workdir}`, the user asked the manager \"{request}\""
    handoff_instructions: str = "When you finish your work and are ready to hand off, call the appropriate transfer_to_<AgentName> handoff tool (in lowercase) using the tool-calling interface. Do not print code or markdown, do not use code, do not include backticks, and do not add any text after the tool call. "
    full_request: str = f"{build_request}. {handoff_instructions}"
    async with AsyncExitStack() as stack:
        mcp_server_configs = [("PrimaryMCP", mcp_params), *additional_mcp_servers]
        mcp_servers: list[MCPServerStdio] = []
        for name, params in mcp_server_configs:
            server = await stack.enter_async_context(MCPServerStdio(name=name, params=params, client_session_timeout_seconds=360000))
            if not server.session:
                logger.warning(f"Skipping MCP server '{name}' because it failed to start.")
                continue
            mcp_servers.append(server)

        for agent in handoffs:
            agent.handoffs = [a for a in handoffs if a.name != agent.name]
            agent.mcp_servers = mcp_servers # type: ignore

        result = Runner.run_streamed(handoffs[4], full_request, run_config=run_config)

        async for event in result.stream_events():
            describe_event(event)
        
        stop_spinner()
        
        if hasattr(result, 'stop_reason'):
            console.print(f"[dim]Run stopped: {getattr(result, 'stop_reason', 'unknown')}[/dim]")
        
        console.print(f"[dim]Result type: {type(result).__name__}[/dim]")
        console.print(f"[dim]Has final_output: {result.final_output is not None}[/dim]")

        if result.final_output is not None:
            console.print("\n[bold green]=== Final Output ===[/bold green]")
            console.print(result.final_output)
            console.print(f"[dim]For: `{request}`[/dim]")

if __name__ == "__main__":
    workdir = run_env_selector()
    request: str = input(f"Enter Request for the Task Master ({local}): ")
    console.print()

    try:
        asyncio.run(main(request, workdir))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as error:
        console.print(f"\n[bold red]Error: {error}[/bold red]")
        import traceback
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
