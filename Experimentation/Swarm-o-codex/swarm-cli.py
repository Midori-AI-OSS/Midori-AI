
import os
import asyncio

from copy import deepcopy
from dotenv import load_dotenv

from agents import Agent
from agents import Runner
from agents import Handoff
from openai import AsyncOpenAI
from agents import ModelSettings
from contextlib import AsyncExitStack

from agents.logger import logger
from agents.mcp import MCPServerStdio
from agents import OpenAIResponsesModel
from openai.types.shared import Reasoning
from agents.mcp import MCPServerStdioParams
from agents import OpenAIChatCompletionsModel

from shared.streaming import console
from shared.streaming import stop_spinner
from cli.env_cli import run_env_selector
from shared.getnetwork import get_local_ip
from shared.streaming import describe_event
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

load_dotenv(override=True)

api_key: str | None = os.getenv("OPENAI_API_KEY")

if api_key: pass
else: api_key = "hello wolrd"

logger.setLevel(0)

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

#### Edit the local params as you see fit
local_params_json = ["-y", "codex", "--oss", "-c", f"base_url=\"{local_ip_address}/v1\"", "-c", f"model=\"{local_model_str}\"", "-c", "model_provider=\"oss\"", "mcp-server"]
local_params_json = ["-y", "codex", "--oss", "mcp-server"]

local_params = MCPServerStdioParams({"command": "npx", "args": local_params_json})
cloud_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "mcp-server"]})

if local:
    model = OpenAIChatCompletionsModel(model=local_model_str, openai_client=local_openai)
    mcp_params = local_params
else:
    model = OpenAIResponsesModel(model=cloud_model_str, openai_client=AsyncOpenAI(api_key=api_key))
    mcp_params = cloud_params

playwright_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "@playwright/mcp@latest"]})
context_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "@upstash/context7-mcp@latest"]})
sequential_thinking_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "@modelcontextprotocol/server-sequential-thinking@latest"]})

# Add additional MCP servers by appending (name, params) tuples to this list.
additional_mcp_servers: list[tuple[str, MCPServerStdioParams]] = [
    ("Playwright", playwright_params),
    ("Context7", context_params),
    ("SequentialThinking", sequential_thinking_params),
]

reasoning = Reasoning(effort="high", generate_summary="detailed", summary="detailed")
base_model_settings = ModelSettings(reasoning=reasoning, parallel_tool_calls=False, tool_choice="required")

#### These are the models persona files, They are read on load, feel free to edit them
start_prompt = RECOMMENDED_PROMPT_PREFIX + " Use the MCP tool servers to help with the task. " + open('personas/META_PROMPT.md').read()
coder_prompt = start_prompt + open('personas/CODER.md').read()
auditor_prompt = start_prompt + open('personas/AUDITOR.md').read()
manager_prompt = start_prompt + open('personas/MANAGER.md').read()
task_master_prompt = start_prompt + open('personas/TASKMASTER.md').read()

#### These are the agent objs, they tell the system what agents are in the swarm
coder_agent = Agent(name="Coder", instructions=coder_prompt, model=model, model_settings=base_model_settings)
auditor_agent = Agent(name="Auditor", instructions=auditor_prompt, model=model, model_settings=base_model_settings)
manager_agent = Agent(name="Manager", instructions=manager_prompt, model=model, model_settings=base_model_settings)
task_master_agent = Agent(name="Task Master", instructions=task_master_prompt, model=model, model_settings=base_model_settings)

#### if you add a agent to the swarm it needs to be added here so that the other agents can "pass the mic" to it
handoffs: list[Agent] = []
handoffs.append(coder_agent)
handoffs.append(auditor_agent)
handoffs.append(manager_agent)
handoffs.append(task_master_agent)

#### This is the main def, this runs the logic for the swarm.
async def main(request: str, workdir: str) -> None:
    build_request: str = f"Working in the `{workdir}`, the user asked the task master \"{request}\""
    full_request: str = f"{build_request}, when you are done with your roles dutys, handoff to the next agent"
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

        result = Runner.run_streamed(task_master_agent, full_request, max_turns=15)

        async for event in result.stream_events():
            describe_event(event)
        
        stop_spinner()

        if result.final_output is not None:
            console.print("\n[bold green]=== Final Output ===[/bold green]")
            console.print(result.final_output)
            console.print(f"[dim]For: `{request}`[/dim]")

if __name__ == "__main__":
    workdir = run_env_selector()
    request: str = input(f"Enter Request for the Task Master ({local}): ")
    asyncio.run(main(request, workdir))
