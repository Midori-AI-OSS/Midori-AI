
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

local_model_str: str = "gpt-oss:120b"
cloud_model_str: str = "gpt-5"

#### Update this to change the ip, do not use localhost
local_ip_address: str = "192.168.10.27:11434"

if local:
    model = OpenAIChatCompletionsModel(model=local_model_str, openai_client=AsyncOpenAI(base_url=f"http://{local_ip_address}/v1", api_key="helloworld"))
else:
    model = OpenAIChatCompletionsModel(model=cloud_model_str, openai_client=AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY")))

local_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "-p", "ollama", "mcp-server"]})
cloud_params = MCPServerStdioParams({"command": "npx", "args": ["-y", "codex", "mcp-server"]})

model_settings = ModelSettings(reasoning=Reasoning(effort="high"))

gamedev_prompt = "You are an expert in building simple games using basic html + css + javascript with no dependencies. Save your work in a file called index.html in the current directory. Keep requests to codex short and easy. Always call codex with \"approval-policy\": \"never\" and \"sandbox\": \"workspace-write\"."
gamemanager_prompt = "You are an indie game connoisseur. Come up with an idea for a single page html + css + javascript game that a developer could build in about 50 lines of code. Format your request as a 3 sentence design brief for a game developer and call the Game Developer coder with your idea."

developer_agent = Agent(name="Game Developer", instructions=gamedev_prompt, model=model, model_settings=model_settings)
designer_agent = Agent(name="Game Designer", instructions=gamemanager_prompt, model=model, model_settings=model_settings, handoffs=[developer_agent],)

async def main() -> None:
    async with MCPServerStdio(name="Codex CLI", params=local_params, client_session_timeout_seconds=360000) as codex_mcp_server:
        developer_agent.mcp_servers = [codex_mcp_server]

        result = await Runner.run(designer_agent, "Implement a fun new game!", max_turns=5)
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
