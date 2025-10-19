import json
from typing import Any

from agents import StreamEvent


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
        return f"\n=== Switched to agent: {event.new_agent.name} ==="

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
        return f"[{agent_name}] {text}"

    if event.name == "handoff_requested":
        raw_item = getattr(item, "raw_item", None)
        target = getattr(raw_item, "name", None)
        summary = f"{agent_name} requested a handoff"
        if target:
            summary += f" to `{target}`"
        arguments = summarize_tool_arguments(maybe_get_attr(raw_item, "arguments"))
        if arguments:
            summary += f" with arguments:\n{arguments}"
        return summary

    if event.name == "handoff_occured":
        source = getattr(item, "source_agent", None)
        target = getattr(item, "target_agent", None)
        source_name = getattr(source, "name", "Unknown")
        target_name = getattr(target, "name", "Unknown")
        return f"Handoff completed: {source_name} ➜ {target_name}"

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
        if arguments:
            summary += f"\nArguments:\n{arguments}"
        return summary

    if event.name == "tool_output":
        output = maybe_get_attr(item, "output")
        if output is None:
            output = maybe_get_attr(item, "raw_item")
        return f"{agent_name} received tool output:\n{output}"

    if event.name == "reasoning_item_created":
        raw_item = getattr(item, "raw_item", None)
        summary = maybe_get_attr(raw_item, "summary")
        if summary:
            return f"{agent_name} reasoning summary: {summary}"
        return f"{agent_name} produced a reasoning item."

    if event.name == "mcp_list_tools":
        raw_item = getattr(item, "raw_item", None)
        server_name = maybe_get_attr(raw_item, "server_name", "unknown server")
        return f"{agent_name} listed MCP tools from {server_name}."

    if event.name == "mcp_approval_requested":
        raw_item = getattr(item, "raw_item", None)
        tool_name = maybe_get_attr(raw_item, "tool", "unknown tool")
        return f"{agent_name} requested MCP approval for {tool_name}."

    return f"{agent_name} emitted event `{event.name}`."
