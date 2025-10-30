import json
from typing import Any

from agents import StreamEvent
from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.panel import Panel
from rich.text import Text
from rich.markup import escape

console = Console()


def maybe_get_attr(obj: Any, name: str, default: Any = None) -> Any:
    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


def format_message_content(content: list[Any]) -> str:
    parts: list[str] = []
    for block in content:
        block_type = maybe_get_attr(block, "type", "")
        if block_type == "output_text":
            text = maybe_get_attr(block, "text", "")
            if isinstance(text, dict):
                text = text.get("value", "")
            if text:
                parts.append(str(text))
        elif block_type == "output_refusal":
            refusal = maybe_get_attr(block, "refusal", "")
            if refusal:
                parts.append(f"[refusal] {refusal}")
    return "\n".join(part.strip() for part in parts if part.strip())


def summarize_tool_arguments(arguments: str | None) -> str:
    if not arguments:
        return ""
    try:
        parsed = json.loads(arguments)
        if isinstance(parsed, dict):
            return json.dumps(parsed, indent=2)
        return json.dumps(parsed, indent=2)
    except (json.JSONDecodeError, TypeError):
        return arguments or ""


def describe_event(event: StreamEvent) -> str | None:
    if event.type == "agent_updated_stream_event":
        agent_name = event.new_agent.name
        # Switch spinner to the new acting agent
        try:
            stop_spinner()
        except Exception:
            pass
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        console.print(Panel(
            f"[bold cyan]Switched to agent: {escape(agent_name)}[/bold cyan]",
            border_style="cyan"
        ))
        return None

    if event.type != "run_item_stream_event":
        return None

    item = event.item
    agent_name = getattr(item.agent, "name", "Unknown")

    if event.name == "message_output_created":
        message = getattr(item, "raw_item", None)
        if message is None:
            return None
        content = maybe_get_attr(message, "content", []) or []
        text = format_message_content(content)
        if not text:
            text = "(no text content)"
        # Ensure clean printing while spinner is paused
        try:
            stop_spinner()
        except Exception:
            pass
        console.print(f"[bold green]{escape(agent_name)}[/bold green]: {escape(text)}")
        # Resume spinner for the same agent to indicate continued activity
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    if event.name == "handoff_requested":
        raw_item = getattr(item, "raw_item", None)
        target = getattr(raw_item, "name", None)
        summary = f"{agent_name} requested a handoff"
        if target:
            summary += f" to `{target}`"
        arguments = summarize_tool_arguments(maybe_get_attr(raw_item, "arguments"))
        # Pause spinner to show the handoff details clearly
        try:
            stop_spinner()
        except Exception:
            pass
        if arguments:
            console.print(f"[yellow]{escape(summary)}[/yellow]")
            console.print(Panel(escape(arguments), title="Arguments", border_style="yellow"))
        else:
            console.print(f"[yellow]{escape(summary)}[/yellow]")
        # Resume spinner since the same agent is still acting until handoff occurs
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    if event.name == "handoff_occured":
        source = getattr(item, "source_agent", None)
        target = getattr(item, "target_agent", None)
        source_name = getattr(source, "name", "Unknown")
        target_name = getattr(target, "name", "Unknown")
        # Stop spinner; the next acting agent will start its own spinner on switch
        try:
            stop_spinner()
        except Exception:
            pass
        console.print(f"[bold magenta]Handoff completed: {escape(source_name)} -> {escape(target_name)}[/bold magenta]")
        return None

    if event.name == "tool_called":
        raw_item = getattr(item, "raw_item", None)
        tool_type = maybe_get_attr(raw_item, "type", "tool_call")
        tool_name = maybe_get_attr(raw_item, "name")
        call_id = maybe_get_attr(raw_item, "call_id")
        summary = f"{agent_name} invoked {tool_type}"
        if tool_name:
            summary += f" `{tool_name}`"
        if call_id:
            summary += f" (call_id={call_id})"
        arguments = summarize_tool_arguments(maybe_get_attr(raw_item, "arguments"))
        # Pause spinner during tool call details
        try:
            stop_spinner()
        except Exception:
            pass
        if arguments:
            console.print(f"[blue]{escape(summary)}[/blue]")
            console.print(Panel(escape(arguments), title="Tool Arguments", border_style="blue", expand=False))
        else:
            console.print(f"[blue]{escape(summary)}[/blue]")
        # Resume spinner for ongoing activity
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    if event.name == "tool_output":
        output = maybe_get_attr(item, "output")
        if output is None:
            output = maybe_get_attr(item, "raw_item")
        output_str = str(output)
        # Truncate very long outputs
        if len(output_str) > 500:
            output_str = output_str[:500] + "... (truncated)"
        try:
            stop_spinner()
        except Exception:
            pass
        console.print(Panel(escape(output_str), title=f"[cyan]{escape(agent_name)}[/cyan] Tool Output", border_style="cyan", expand=False))
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    if event.name == "reasoning_item_created":
        raw_item = getattr(item, "raw_item", None)
        summary = maybe_get_attr(raw_item, "summary")
        # Pause spinner to render reasoning block cleanly
        try:
            stop_spinner()
        except Exception:
            pass
        if summary:
            console.print(f"[magenta]{escape(agent_name)} reasoning: {escape(summary)}[/magenta]")
        else:
            console.print(f"[magenta]{escape(agent_name)} produced a reasoning item.[/magenta]")
        # Resume spinner after reasoning
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    if event.name == "mcp_list_tools":
        raw_item = getattr(item, "raw_item", None)
        server_name = maybe_get_attr(raw_item, "server_name", "unknown server")
        try:
            stop_spinner()
        except Exception:
            pass
        console.print(f"[dim]{escape(agent_name)} listed MCP tools from {escape(server_name)}.[/dim]")
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    if event.name == "mcp_approval_requested":
        raw_item = getattr(item, "raw_item", None)
        tool_name = maybe_get_attr(raw_item, "tool", "unknown tool")
        try:
            stop_spinner()
        except Exception:
            pass
        console.print(f"[yellow]{escape(agent_name)} requested MCP approval for {escape(tool_name)}.[/yellow]")
        try:
            start_spinner_for_agent(agent_name)
        except Exception:
            pass
        return None

    # Default event logging; keep spinner as-is
    console.print(f"[dim]{escape(agent_name)} emitted event `{escape(event.name)}`.[/dim]")
    return None


class ThinkingSpinner:
    """Context manager for displaying a spinner while the model is thinking"""
    def __init__(self, agent_name: str, message: str = "thinking..."):
        self.agent_name = agent_name
        self.message = message
        self.live = None
    
    def __enter__(self):
        spinner = Spinner("dots", text=f"[bold yellow]{escape(self.agent_name)}[/bold yellow] {self.message}")
        self.live = Live(spinner, console=console, refresh_per_second=10)
        self.live.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.live:
            self.live.__exit__(exc_type, exc_val, exc_tb)


def create_thinking_spinner(agent_name: str, message: str = "thinking...") -> ThinkingSpinner:
    """Create a spinner to show that the model is thinking"""
    return ThinkingSpinner(agent_name, message)

# --- Spinner management helpers (module-level) ---
current_spinner = None  # type: Any | None
current_agent_name = None  # type: Any | None

def start_spinner_for_agent(agent_name: str, message: str = "acting...") -> None:
    """Start (or restart) a spinner for the given agent name."""
    global current_spinner, current_agent_name
    stop_spinner()
    try:
        spinner = create_thinking_spinner(agent_name, message)
        current_spinner = spinner
        current_agent_name = agent_name
        spinner.__enter__()
    except Exception:
        # Fail silently; streaming should never crash due to spinner issues
        current_spinner = None
        current_agent_name = agent_name

def stop_spinner() -> None:
    """Stop the current spinner if one is active."""
    global current_spinner, current_agent_name
    if current_spinner is not None:
        try:
            current_spinner.__exit__(None, None, None)
        finally:
            current_spinner = None
    # Keep current_agent_name for potential resume decisions
