import time

from agents import Agent
from agents import Runner
from agents import RunConfig
from contextlib import AsyncExitStack

from agents.logger import logger
from agents.mcp import MCPServerStdio
from agents.mcp import MCPServerStdioParams

from shared.streaming import console
from shared.streaming import describe_event
from shared.streaming import EventBuffer
from shared.streaming import ENABLE_EVENT_BUFFERING
from shared.handoff_tracker import HandoffTracker

#### This is the main def, this runs the logic for the swarm.
async def run(request: str, workdir: str, handoffs: list[Agent], run_config: RunConfig, mcp_params: MCPServerStdioParams, additional_mcp_servers: list[tuple[str, MCPServerStdioParams]]) -> None:
    start_time = time.perf_counter()
    
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

        # Initialize event buffer if enabled
        event_buffer = EventBuffer() if ENABLE_EVENT_BUFFERING else None

        async for event in result.stream_events():
            if event_buffer:
                # Use buffering to reorder events (reasoning before tool calls)
                events_to_display = event_buffer.add(event, handoff_tracker)
                for buffered_event, buffered_tracker in events_to_display:
                    describe_event(buffered_event, buffered_tracker)
            else:
                # Direct pass-through without buffering
                describe_event(event, handoff_tracker)
        
        # Flush any remaining buffered events
        if event_buffer:
            remaining_events = event_buffer.flush()
            for buffered_event, buffered_tracker in remaining_events:
                describe_event(buffered_event, buffered_tracker)

        if handoff_tracker.requirements_met():
            console.print("[dim]Handoff tracker: all required role handoffs observed.[/dim]")
        else:
            console.print("[bold yellow]Handoff tracker reminder: required role handoffs still missing.[/bold yellow]")
            for reminder in handoff_tracker.iter_missing():
                console.print(f" - {reminder}")
        
        # Log stop reason and result details for debugging
        stop_reason = getattr(result, 'stop_reason', None)
        console.print(f"[dim]Result type: {type(result).__name__}[/dim]")
        console.print(f"[dim]Stop reason: {stop_reason if stop_reason else 'not available'}[/dim]")
        console.print(f"[dim]Has final_output: {result.final_output is not None}[/dim]")
        
        # Check the active agent at the end of the run
        active_agent_name = getattr(result, 'agent', None)
        if active_agent_name:
            active_agent_name = getattr(active_agent_name, 'name', 'Unknown')
        else:
            active_agent_name = 'Unknown'
        console.print(f"[dim]Active agent at completion: {active_agent_name}[/dim]")

        # CRITICAL: Only allow Manager to complete the run with final output
        if result.final_output is not None:
            if active_agent_name != "Manager":
                console.print(f"\n[bold red]ERROR: Run completed with final_output but active agent is '{active_agent_name}', not 'Manager'![/bold red]")
                console.print(f"[bold red]Only the Manager agent can complete workflow runs.[/bold red]")
                console.print(f"[yellow]This indicates the agent failed to properly hand off. Check the agent's last actions.[/yellow]")
                console.print(f"\n[bold yellow]=== Invalid Final Output (from {active_agent_name}) ===[/bold yellow]")
                console.print(result.final_output)
                console.print(f"[dim]For: `{request}`[/dim]")
                console.print(f"\n[bold red]Run did NOT complete successfully - missing proper Manager handoff[/bold red]")
            else:
                console.print("\n[bold green]=== Final Output ===[/bold green]")
                console.print(result.final_output)
                console.print(f"[dim]For: `{request}`[/dim]")
        
        else:
            # No final output - run ended without proper completion
            console.print(f"\n[bold yellow]Run ended without final output[/bold yellow]")
            if stop_reason:
                console.print(f"[yellow]Reason: {stop_reason}[/yellow]")
            if not handoff_tracker.requirements_met():
                console.print(f"[yellow]Missing required handoffs - workflow incomplete[/yellow]")
        
        # Log execution time
        end_time = time.perf_counter()
        duration = end_time - start_time
        console.print(f"\n[bold cyan]Run completed in {duration:.2f} seconds[/bold cyan]")
        logger.info(f"Run completed in {duration:.2f} seconds for request: {request}")
