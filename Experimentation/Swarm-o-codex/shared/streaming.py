import os
import json

from typing import Any
from typing import Optional
from collections import deque

from agents import StreamEvent
from rich.console import Console
from rich.panel import Panel
from rich.markup import escape
from rich.spinner import Spinner
from rich.live import Live

console = Console()

#### TODO - Review the streamed "Event: type=raw_response_event, name=unknown", I think its the streamed tokens from the model but not sure.
####        Now we handle raw_response_event and try to extract streaming text, but the structure might vary by model.
####        If streaming text isn't displaying properly, we may need to inspect the actual event structure more deeply.

# Env-tunable settings
DEBUG_EVENTS = os.getenv("SWARM_DEBUG_EVENTS", "0").strip().lower() in {"1", "true", "yes", "on"}
ENABLE_EVENT_BUFFERING = os.getenv("SWARM_ENABLE_EVENT_BUFFERING", "1").strip().lower() in {"1", "true", "yes", "on"}
BUFFER_SIZE = int(os.getenv("SWARM_EVENT_BUFFER_SIZE", "5"))
HIGHLIGHT_CODEX = os.getenv("SWARM_HIGHLIGHT_CODEX", "1").strip().lower() in {"1", "true", "yes", "on"}

# Global state for tracking tool output accumulation (for streaming display)
_tool_output_accumulators: dict[str, list[str]] = {}
_active_codex_calls: set[str] = set()

# Track streaming reasoning state
_streaming_reasoning_active: bool = False
_current_agent_name: str = ""
_reasoning_accumulator: list[str] = []

# Track Codex streaming state
_streaming_codex_active: bool = False
_codex_accumulator: list[str] = []

class EventBuffer:
    """
    Buffer for reordering streaming events to show reasoning before tool calls.
    
    This class implements a look-ahead buffer that can detect reasoning events
    arriving after tool calls and reorder them for better display flow.
    """
    
    def __init__(self, buffer_size: int = BUFFER_SIZE):
        self.buffer: deque[tuple[StreamEvent, Any]] = deque(maxlen=buffer_size)
        self.buffer_size = buffer_size
    
    def should_reorder(self) -> bool:
        """Check if buffer contains reasoning after tool calls that should be reordered."""
        if len(self.buffer) < 2:
            return False
        
        # Look for pattern: tool_call followed by reasoning
        for i in range(len(self.buffer) - 1):
            curr_event, _ = self.buffer[i]
            if curr_event.type == "run_item_stream_event":
                curr_name = getattr(curr_event, "name", "")
                if curr_name in ["tool_called", "handoff_requested"]:
                    # Check if reasoning comes after
                    for j in range(i + 1, len(self.buffer)):
                        next_event, _ = self.buffer[j]
                        if next_event.type == "run_item_stream_event":
                            next_name = getattr(next_event, "name", "")
                            if next_name == "reasoning_item_created":
                                return True
        return False
    
    def get_reordered_events(self) -> list[tuple[StreamEvent, Any]]:
        """Extract events from buffer in optimal display order (reasoning first)."""
        if not self.should_reorder():
            # Return all events in original order
            result = list(self.buffer)
            self.buffer.clear()
            return result
        
        # Separate reasoning events from others
        reasoning_events = []
        other_events = []
        
        for event, tracker in self.buffer:
            if event.type == "run_item_stream_event" and getattr(event, "name", "") == "reasoning_item_created":
                reasoning_events.append((event, tracker))
            else:
                other_events.append((event, tracker))
        
        self.buffer.clear()
        
        # Return reasoning first, then others
        return reasoning_events + other_events
    
    def add(self, event: StreamEvent, handoff_tracker: Optional[Any] = None) -> list[tuple[StreamEvent, Any]]:
        """
        Add event to buffer and return events ready for display.
        
        Returns:
            List of (event, tracker) tuples ready to be displayed.
        """
        self.buffer.append((event, handoff_tracker))
        
        # If buffer is full, process and return events
        if len(self.buffer) >= self.buffer_size:
            return self.get_reordered_events()
        
        return []
    
    def flush(self) -> list[tuple[StreamEvent, Any]]:
        """Flush any remaining events in buffer."""
        return self.get_reordered_events()


def is_codex_tool(tool_name: str, raw_item: Any = None) -> bool:
    """Detect if a tool call is from Codex MCP."""
    if not tool_name:
        return False
    
    # Check tool name
    tool_name_lower = tool_name.lower()
    if "codex" in tool_name_lower or tool_name_lower.startswith("mcp_codex"):
        return True
    
    # Check if raw_item has server metadata indicating Codex
    if raw_item:
        server_name = maybe_get_attr(raw_item, "server_name", "")
        if server_name and "codex" in server_name.lower():
            return True
    
    return False


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
        else:
            # Handle Content objects with .text attribute (e.g., reasoning_item content)
            text = maybe_get_attr(block, "text", "")
            if text:
                parts.append(str(text))
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


def describe_event(event: StreamEvent, handoff_tracker: Optional[Any] = None) -> str | None:
    global _streaming_reasoning_active, _current_agent_name, _reasoning_accumulator
    global _streaming_codex_active, _codex_accumulator
    
    # Debug: always log event type and name with more detail
    if DEBUG_EVENTS:
        event_type = getattr(event, 'type', 'unknown')
        event_name = getattr(event, 'name', 'unknown')
        # Show more details about the event
        console.print(f"[dim cyan]━━━ Event: type={event_type}, name={event_name} ━━━[/dim cyan]")
        if hasattr(event, 'item'):
            item = getattr(event, 'item', None)
            if item:
                raw_item = getattr(item, 'raw_item', None)
                if raw_item:
                    console.print(f"[dim]  Raw item type: {type(raw_item).__name__}[/dim]")
                    console.print(f"[dim]  Raw item attrs: {list(vars(raw_item).keys()) if hasattr(raw_item, '__dict__') else 'N/A'}[/dim]")
    
    # Handle raw_response_event - these are streaming tokens from the LLM
    if event.type == "raw_response_event":
        # Try to extract the streaming content
        chunk_data = None
        
        # Check various possible attributes for the chunk content
        if hasattr(event, 'chunk'):
            chunk_data = getattr(event, 'chunk', None)
        elif hasattr(event, 'delta'):
            chunk_data = getattr(event, 'delta', None)
        elif hasattr(event, 'content'):
            chunk_data = getattr(event, 'content', None)
        elif hasattr(event, 'data'):
            chunk_data = getattr(event, 'data', None)
        elif hasattr(event, 'response'):
            chunk_data = getattr(event, 'response', None)
        
        # Identify event type and extract delta text
        text_content = None
        event_subtype = None
        
        if chunk_data:
            chunk_type = type(chunk_data).__name__
            event_subtype = getattr(chunk_data, 'type', chunk_type)
            
            # Handle ResponseReasoningTextDeltaEvent and ResponseTextDeltaEvent
            if 'TextDelta' in chunk_type or event_subtype in ['response.output_item.text.delta', 'response.reasoning_text.delta']:
                # Extract delta text
                delta = getattr(chunk_data, 'delta', None)
                if isinstance(delta, str):
                    text_content = delta
                elif delta and hasattr(delta, 'text'):
                    text_content = getattr(delta, 'text', None)
                elif delta and hasattr(delta, 'content'):
                    text_content = getattr(delta, 'content', None)
                elif isinstance(delta, dict):
                    text_content = delta.get('text') or delta.get('content')
        
        if text_content and str(text_content).strip():
            # Determine if this is reasoning or regular text
            chunk_type = type(chunk_data).__name__ if chunk_data else ""
            is_reasoning = 'Reasoning' in chunk_type
            
            # Display the streaming token with appropriate formatting
            if is_reasoning:
                # Start reasoning accumulation if not already active
                if not _streaming_reasoning_active:
                    _streaming_reasoning_active = True
                    _reasoning_accumulator = []
                
                # Accumulate reasoning text
                _reasoning_accumulator.append(str(text_content))
                
                # Print token in dim for live feedback
                console.print(f"[dim]{escape(str(text_content))}[/dim]", end="")
            elif _streaming_codex_active:
                # This is Codex output streaming
                _codex_accumulator.append(str(text_content))
                
                if DEBUG_EVENTS:
                    console.print(f"[dim green]>>> Codex chunk: {len(str(text_content))} chars[/dim green]")
                
                # Print token in dim for live feedback
                console.print(f"[dim]{escape(str(text_content))}[/dim]", end="")
            else:
                # Close reasoning panel if it was active
                if _streaming_reasoning_active:
                    _streaming_reasoning_active = False
                    # Display accumulated reasoning in a Panel
                    full_reasoning = ''.join(_reasoning_accumulator)
                    console.print()  # New line after streaming
                    panel = Panel(f"[dim]{escape(full_reasoning)}[/dim]", title=f"[magenta]{escape(_current_agent_name)} Reasoning[/magenta]", border_style="magenta", expand=False)
                    console.print(panel)
                    _reasoning_accumulator = []
                
                # Display regular text
                console.print(f"[white]{escape(str(text_content))}[/white]", end="")
            return None
        elif DEBUG_EVENTS and chunk_data:
            chunk_type = type(chunk_data).__name__
            # Only show debug for TextDelta events to reduce noise
            if 'TextDelta' in chunk_type:
                console.print(f"[dim yellow]  {chunk_type} - no text extracted[/dim yellow]")
                console.print(f"[dim]    delta attr: {getattr(chunk_data, 'delta', 'N/A')}[/dim]")
        return None
    
    
    if event.type == "agent_updated_stream_event":
        agent_name = event.new_agent.name
        _current_agent_name = agent_name
        panel = Panel(f"[bold cyan]Switched to agent: {escape(agent_name)}[/bold cyan]", border_style="cyan")
        console.print(panel)
        return None

    if event.type != "run_item_stream_event":
        return None

    item = event.item
    agent_name = getattr(item.agent, "name", "Unknown")

    # Process reasoning FIRST before any other events
    if event.name == "reasoning_item_created":
        # Close reasoning panel if still open from streaming
        if _streaming_reasoning_active:
            _streaming_reasoning_active = False
            # Display accumulated reasoning in a Panel
            full_reasoning = ''.join(_reasoning_accumulator)
            console.print()  # New line after streaming
            panel = Panel(f"[dim]{escape(full_reasoning)}[/dim]", title=f"[dim magenta]{escape(agent_name)} Reasoning[/dim magenta]", border_style="dim magenta", expand=False)
            console.print(panel)
            _reasoning_accumulator = []
        
        # Skip displaying the full reasoning panel since we already streamed it
        # This prevents duplicate reasoning display
        return None

    if event.name == "message_output_created":
        message = getattr(item, "raw_item", None)
        if message is None:
            return None
        content = maybe_get_attr(message, "content", []) or []
        text = format_message_content(content)
        if not text:
            return None
        console.print(f"[bold green]{escape(agent_name)}[/bold green]: {escape(text)}")
        return None

    if event.name == "handoff_requested":
        raw_item = getattr(item, "raw_item", None)
        target = getattr(raw_item, "name", None)
        summary = f"{agent_name} requested a handoff"
        if target:
            summary += f" to `{target}`"
        arguments = summarize_tool_arguments(maybe_get_attr(raw_item, "arguments"))
        if arguments:
            console.print(f"[yellow]{escape(summary)}[/yellow]")
            panel = Panel(escape(arguments), title="Handoff Arguments", border_style="yellow")
            console.print(panel)
        else:
            console.print(f"[yellow]{escape(summary)}[/yellow]")
        console.print(f"[dim]Waiting for handoff to complete...[/dim]")
        return None

    if event.name == "handoff_occurred" or event.name == "handoff_occured":
        source = getattr(item, "source_agent", None)
        target = getattr(item, "target_agent", None)
        source_name = getattr(source, "name", "Unknown")
        target_name = getattr(target, "name", "Unknown")
        
        # Record handoff if tracker is provided
        if handoff_tracker is not None:
            handoff_tracker.record(source_name, target_name)
        
        console.print(f"[bold magenta]Handoff completed: {escape(source_name)} -> {escape(target_name)}[/bold magenta]")
        return None

    if event.name == "tool_called":
        raw_item = getattr(item, "raw_item", None)
        tool_type = maybe_get_attr(raw_item, "type", "tool_call")
        tool_name = maybe_get_attr(raw_item, "name")
        call_id = maybe_get_attr(raw_item, "call_id")
        
        # Check if this is a Codex tool for special highlighting
        is_codex = HIGHLIGHT_CODEX and is_codex_tool(tool_name, raw_item)
        
        if is_codex:
            # Track this Codex call for streaming
            if call_id:
                _active_codex_calls.add(call_id)
                _tool_output_accumulators[call_id] = []
            
            # Start Codex streaming accumulation
            _streaming_codex_active = True
            _codex_accumulator = []
            
            if DEBUG_EVENTS:
                console.print(f"[dim green]>>> Codex streaming STARTED (call_id={call_id})[/dim green]")
            
            # Enhanced display for Codex tools
            summary = f"{agent_name} invoked Codex MCP"
            if tool_name:
                summary += f" -> `{tool_name}`"
            console.print(f"[bold yellow]{escape(summary)}[/bold yellow]")
            
            arguments = summarize_tool_arguments(maybe_get_attr(raw_item, "arguments"))
            if arguments:
                panel = Panel(escape(arguments), title="[bold yellow]Codex Tool Arguments[/bold yellow]", border_style="yellow", expand=False)
                console.print(panel)
        else:
            # Regular tool display
            summary = f"{agent_name} invoked {tool_type}"
            if tool_name:
                summary += f" `{tool_name}`"
            if call_id:
                summary += f" (call_id={call_id})"
            arguments = summarize_tool_arguments(maybe_get_attr(raw_item, "arguments"))
            if arguments:
                console.print(f"[blue]{escape(summary)}[/blue]")
                panel = Panel(escape(arguments), title="Tool Arguments", border_style="blue", expand=False)
                console.print(panel)
            else:
                console.print(f"[blue]{escape(summary)}[/blue]")
        return None

    if event.name == "tool_output":
        raw_item = getattr(item, "raw_item", None)
        tool_name = maybe_get_attr(raw_item, "name", "")
        call_id = maybe_get_attr(raw_item, "call_id", "")
        is_codex = HIGHLIGHT_CODEX and is_codex_tool(tool_name, raw_item)
        
        output = maybe_get_attr(item, "output")
        if output is None:
            output = raw_item
        output_str = str(output)
        
        # Check if this was a streaming Codex call
        if is_codex and _streaming_codex_active:
            if DEBUG_EVENTS:
                console.print(f"\n[dim green]>>> Codex streaming ENDED. Accumulated {len(_codex_accumulator)} chunks[/dim green]")
            
            # Display accumulated Codex output in a Panel
            full_output = ''.join(_codex_accumulator) if _codex_accumulator else output_str
            console.print()  # New line after streaming
            panel = Panel(f"[dim]{escape(full_output)}[/dim]", title=f"[dim yellow]{escape(agent_name)} Codex Output[/dim yellow]", border_style="dim yellow", expand=False)
            console.print(panel)
            _streaming_codex_active = False
            _codex_accumulator = []
            
            # Clean up tracking
            if call_id in _active_codex_calls:
                _active_codex_calls.discard(call_id)
            if call_id in _tool_output_accumulators:
                del _tool_output_accumulators[call_id]
        elif is_codex:
            # Codex output without streaming (fallback)
            # Truncate very long outputs
            if len(output_str) > 500:
                output_str = output_str[:500] + "... (truncated)"
            
            panel = Panel(escape(output_str), title=f"[bold yellow]{escape(agent_name)} Codex Output[/bold yellow]", border_style="yellow", expand=False)
            console.print(panel)
        else:
            # Regular tool output display
            # Truncate very long outputs
            if len(output_str) > 500:
                output_str = output_str[:500] + "... (truncated)"
            
            panel = Panel(escape(output_str), title=f"[cyan]{escape(agent_name)}[/cyan] Tool Output", border_style="cyan", expand=False)
            console.print(panel)
        return None

    if event.name == "mcp_list_tools":
        raw_item = getattr(item, "raw_item", None)
        server_name = maybe_get_attr(raw_item, "server_name", "unknown server")
        console.print(f"[dim]{escape(agent_name)} listed MCP tools from {escape(server_name)}.[/dim]")
        return None

    if event.name == "mcp_approval_requested":
        raw_item = getattr(item, "raw_item", None)
        tool_name = maybe_get_attr(raw_item, "tool", "unknown tool")
        console.print(f"[yellow]{escape(agent_name)} requested MCP approval for {escape(tool_name)}.[/yellow]")
        return None

    # Handle streaming tool output deltas (for progressive display)
    if event.name in ["tool_output_delta", "tool_output_chunk", "tool_call_delta"]:
        raw_item = getattr(item, "raw_item", None)
        tool_name = maybe_get_attr(raw_item, "name", "")
        call_id = maybe_get_attr(raw_item, "call_id", "")
        is_codex = HIGHLIGHT_CODEX and (is_codex_tool(tool_name, raw_item) or call_id in _active_codex_calls)
        
        # Extract the delta/chunk content
        delta_content = maybe_get_attr(raw_item, "delta", "")
        if not delta_content:
            delta_content = maybe_get_attr(raw_item, "chunk", "")
        if not delta_content:
            delta_content = maybe_get_attr(raw_item, "content", "")
        if not delta_content:
            # Try to get from output field
            delta_content = maybe_get_attr(item, "output", "")
        
        if delta_content and is_codex:
            # Accumulate and display streaming output
            if call_id:
                if call_id not in _tool_output_accumulators:
                    _tool_output_accumulators[call_id] = []
                _tool_output_accumulators[call_id].append(str(delta_content))
            
            # Display the streaming chunk with special formatting
            console.print(f"[bold cyan]│[/bold cyan] [white]{escape(str(delta_content))}[/white]", end="")
        elif DEBUG_EVENTS:
            console.print(f"[dim]Stream delta for {tool_name}: {len(str(delta_content))} chars[/dim]")
        
        return None

    if DEBUG_EVENTS:
        console.print(f"[dim]{escape(agent_name)} emitted event `{escape(event.name)}`.[/dim]")
    
    # Catch any unhandled events for debugging
    if event.name not in [
        "reasoning_item_created", "message_output_created", "handoff_requested", 
        "handoff_occurred", "handoff_occured", "tool_called", "tool_output", 
        "mcp_list_tools", "mcp_approval_requested",
        "tool_output_delta", "tool_output_chunk", "tool_call_delta"
    ] and event.type not in ["raw_response_event"]:
        console.print(f"[dim yellow]Unhandled event: type={escape(event.type)}, name={escape(event.name)}[/dim yellow]")
    
    return None
