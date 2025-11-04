
import os
import logging
import asyncio
import argparse
import traceback

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
from cli.env_cli import run_env_selector
from shared.getnetwork import get_local_ip
from shared.streaming import describe_event
from shared.handoff_utils import create_agent_summary_filter

from swarm.run import run
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

known_endpoints: list[str] = [
    "https://ai-proxy.midori-ai.xyz",
    "https://api.groq.com/openai",
    "https://openrouter.ai/api",
    "https://api.arliai.com",
    ]

#### Change / set this for cloud support
local_env = os.getenv("SWARM_RUN_LOCAL", "true").strip().lower()
local: bool = local_env not in ("0", "false", "no", "off")

#### This only works with LRMs not LLMs 
#### (If your using ollama make sure you have context set to >= 32000)
local_model_str: str = "gpt-oss:120b"
cloud_model_str: str = "gpt-5"

#### Update this to change the ip, do not use localhost
pre_local_ip: str = get_local_ip(fallback='192.168.10.27')
pre_local_port: str = "11434"
local_ip_address: str = f"http://{pre_local_ip}:{pre_local_port}"

remote_openai_base_url: str = os.getenv("SWARM_REMOTE_OPENAI_BASE_URL", "https://api.openai.com").rstrip("/")

#### This sets up the params for MCP servers, go check the setup mcp.py folder!
cloud_params, local_params, additional_mcp_servers = setup_mcp(local_model_str, local_ip_address)

if local:
    #### Local only Async friendly OpenAI obj, changes not needed most of the time...
    local_openai = AsyncOpenAI(base_url=f"{local_ip_address}/v1", api_key=api_key)
    model = OpenAIChatCompletionsModel(model=local_model_str, openai_client=local_openai)
    status_text = "Offline"; mcp_params = local_params
else:
    model = OpenAIResponsesModel(model=cloud_model_str, openai_client=AsyncOpenAI(api_key=api_key))
    status_text = "Cloud"; mcp_params = cloud_params

reasoning = Reasoning(effort="medium", generate_summary="detailed", summary="detailed")
base_model_settings = ModelSettings(reasoning=reasoning, parallel_tool_calls=True, tool_choice="auto", temperature=0.1, truncation="auto")

handoffs = setup_agents(model, base_model_settings)
summarizer = setup_summary_agent(model, base_model_settings)
run_config = RunConfig(handoff_input_filter=create_agent_summary_filter(summarizer))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Swarm CLI")
    parser.add_argument("--env", dest="env", nargs="?", const="local", default=None, help="Environment name to open.")
    parser.add_argument("--task", dest="task", default=None, help="Task/request to run non-interactively")
    args, _ = parser.parse_known_args()

    workdir, init_prompt = run_env_selector(env_name=args.env)
    
    # If the folder needs initialization, run the init task first
    if init_prompt:
        console.print("[bold cyan]Initializing local work folder with template...[/bold cyan]")
        try:
            asyncio.run(run(init_prompt, workdir, handoffs, run_config, mcp_params, additional_mcp_servers))
            console.print("\n[bold green]Local work folder initialized successfully![/bold green]\n")
        except Exception as error:
            console.print(f"\n[bold red]Failed to initialize local work folder: {error}[/bold red]")
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
            console.print("\n[yellow]Continuing with empty folder...[/yellow]\n")
    
    request: str = args.task if args.task else input(f"Enter Request ({status_text}): ")
    console.print()

    try:
        asyncio.run(run(request, workdir, handoffs, run_config, mcp_params, additional_mcp_servers))
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
    except Exception as error:
        console.print(f"\n[bold red]Error: {error}[/bold red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
