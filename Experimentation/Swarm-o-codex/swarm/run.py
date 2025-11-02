
from agents import Agent
from agents import Runner
from agents import RunConfig
from contextlib import AsyncExitStack

from agents.logger import logger
from agents.mcp import MCPServerStdio
from agents.mcp import MCPServerStdioParams

from shared.streaming import console
from shared.streaming import stop_spinner
from shared.streaming import describe_event
from shared.handoff_tracker import HandoffTracker

#### This is the main def, this runs the logic for the swarm.
async def run(request: str, workdir: str, handoffs: list[Agent], run_config: RunConfig, mcp_params: MCPServerStdioParams, additional_mcp_servers: list[tuple[str, MCPServerStdioParams]]) -> None:
    build_request: str = f"Working in the `{workdir}`, the user asked the manager \"{request}\""
    handoff_instructions: str = "When you finish your work and are ready to hand off: First, in your message, clearly state what you accomplished and what the next agent needs to do (include specific file paths and requirements). Then call the appropriate transfer_to_<AgentName> handoff tool (in lowercase) as your final action. Do not add any text after calling the handoff tool."
    full_request: str = f"{build_request}. {handoff_instructions}"
    handoff_tracker = HandoffTracker(required_counts={"Task Master": 2, "Auditor": 1, "Coder": 1})

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

        result = Runner.run_streamed(handoffs[4], full_request, run_config=run_config, max_turns=55)

        async for event in result.stream_events():
            describe_event(event)
            if event.name in ("handoff_occurred", "handoff_occured"):
                item = getattr(event, "item", None)
                source = getattr(item, "source_agent", None)
                target = getattr(item, "target_agent", None)
                source_name = getattr(source, "name", "Unknown")
                target_name = getattr(target, "name", "Unknown")
                handoff_tracker.record(source_name, target_name)
        
        stop_spinner()

        if handoff_tracker.requirements_met():
            console.print("[dim]Handoff tracker: all required role handoffs observed.[/dim]")
        else:
            console.print("[bold yellow]Handoff tracker reminder: required role handoffs still missing.[/bold yellow]")
            for reminder in handoff_tracker.iter_missing():
                console.print(f" - {reminder}")
        
        if hasattr(result, 'stop_reason'):
            console.print(f"[dim]Run stopped: {getattr(result, 'stop_reason', 'unknown')}[/dim]")
        
        console.print(f"[dim]Result type: {type(result).__name__}[/dim]")
        console.print(f"[dim]Has final_output: {result.final_output is not None}[/dim]")

        if result.final_output is not None:
            console.print("\n[bold green]=== Final Output ===[/bold green]")
            console.print(result.final_output)
            console.print(f"[dim]For: `{request}`[/dim]")
