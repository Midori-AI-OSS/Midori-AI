
import os
import asyncio

from dotenv import load_dotenv

from agents import Agent
from agents import Runner
from openai import AsyncOpenAI
from agents import ModelSettings

from agents.logger import logger
from agents.mcp import MCPServerStdio
from agents.mcp import MCPServerStdioParams
from openai.types.shared import Reasoning
from agents import OpenAIChatCompletionsModel

from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

load_dotenv(override=True)

logger.setLevel(10)

#### Change this for cloud support
local: bool = True

#### This only works with LRMs not LLMs
local_model_str: str = "gpt-oss:20b"
cloud_model_str: str = "gpt-5"

#### Update this to change the ip, do not use localhost
local_ip_address: str = "192.168.10.27:11434"

#### Edit the local params as you see fit, 
#### you will need to setup a ollama profile or make your codex local friendly...
local_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "-p", "ollama", "mcp-server"]})
cloud_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "mcp-server"]})

if local:
    model = OpenAIChatCompletionsModel(model=local_model_str, openai_client=AsyncOpenAI(base_url=f"http://{local_ip_address}/v1", api_key="helloworld"))
    mcp_params = local_params
else:
    model = OpenAIChatCompletionsModel(model=cloud_model_str, openai_client=AsyncOpenAI(api_key=(os.getenv("OPENAI_API_KEY") | "no api key")))
    mcp_params = cloud_params

model_settings = ModelSettings(reasoning=Reasoning(effort="high"))

#### These are the models persona files, They are read on load, feel free to edit them
coder_prompt = open('personas/CODER.md').read()
auditor_prompt = open('personas/AUDITOR.md').read()
manager_prompt = open('personas/MANAGER.md').read()
task_master_prompt = open('personas/TASKMASTER.md').read()

#### These are the agent objs, they tell the system what agents are in the swarm
coder_agent = Agent(name="Coder", instructions=coder_prompt, model=model, model_settings=model_settings)
auditor_agent = Agent(name="Auditor", instructions=auditor_prompt, model=model, model_settings=model_settings)
manager_agent = Agent(name="Manager", instructions=manager_prompt, model=model, model_settings=model_settings)
task_master_agent = Agent(name="Task Master", instructions=task_master_prompt, model=model, model_settings=model_settings)

#### if you add a agent to the swarm it needs to be added here so that the other agents can "pass the mic" to it
handoffs: list[Agent] = []
handoffs.append(coder_agent)
handoffs.append(auditor_agent)
handoffs.append(manager_agent)
handoffs.append(task_master_agent)


#### This is the main def, this runs the logic for the swarm.
async def main(request) -> None:
    async with MCPServerStdio(name="MCP-Servers", params=mcp_params, client_session_timeout_seconds=360000) as mcp_server:

        for agent in handoffs:
            agent.handoffs = [a for a in handoffs if a.name != agent.name]
            agent.mcp_servers = [mcp_server]

        result = await Runner.run(task_master_agent, request, max_turns=15)

        print(result.final_output)


if __name__ == "__main__":
    request: str = input("Enter Request for the Task Master: ")
    asyncio.run(main(request))
