
from agents import Agent
from agents import Runner
from agents.items import RunItem
from agents.items import ToolCallItem
from agents.items import HandoffCallItem
from agents.items import MessageOutputItem
from agents.handoffs import HandoffInputData

def format_handoff_items(handoff_data: HandoffInputData) -> str:
    """
    Format handoff items into readable text for the summarizer agent.
    
    Args:
        handoff_data: The handoff input data containing conversation history and items.
    
    Returns:
        Formatted text representation of the conversation context.
    """
    all_items = list(handoff_data.pre_handoff_items) + list(handoff_data.new_items)
    
    if not all_items:
        return "No prior context available."
    
    formatted_parts: list[str] = []
    
    for item in all_items:
        if isinstance(item, MessageOutputItem):
            raw_item = getattr(item, 'raw_item', None)
            if raw_item and hasattr(raw_item, 'content'):
                content = raw_item.content
                if isinstance(content, list) and len(content) > 0:
                    for block in content:
                        if hasattr(block, 'text'):
                            text = str(block.text)
                            formatted_parts.append(f"Message: {text}")
                            break
                elif isinstance(content, str):
                    formatted_parts.append(f"Message: {content}")
        
        elif isinstance(item, ToolCallItem):
            tool_name = getattr(item.raw_item, 'name', 'unknown')
            formatted_parts.append(f"Tool called: {tool_name}")
        
        elif isinstance(item, HandoffCallItem):
            formatted_parts.append("Handoff initiated")
    
    return "\n".join(formatted_parts)


def create_agent_summary_filter(summarizer_agent: Agent):
    """
    Create a handoff input filter that uses an agent to generate intelligent summaries.
    
    This prevents agents from being confused by previous agents' role statements by
    using an LLM to create a concise, context-aware summary of the handoff history.
    Preserves recent tool outputs so the next agent has necessary context.
    
    Args:
        summarizer_agent: The agent instance to use for summarization.
    
    Usage:
        summarizer = setup_summary_agent(model, base_model_settings)
        run_config = RunConfig(handoff_input_filter=create_agent_summary_filter(summarizer))
    
    Returns:
        An async input filter function for use with HandoffInputFilter.
    """
    async def filter_fn(h: HandoffInputData) -> HandoffInputData:
        context = format_handoff_items(h)
        result = await Runner.run(summarizer_agent, context, max_turns=5)
        
        all_items = list(h.pre_handoff_items) + list(h.new_items)
        recent_items = all_items[-10:] if len(all_items) > 10 else all_items
        
        return h.clone(input_history=result.final_output, pre_handoff_items=(), new_items=tuple(recent_items))
    
    return filter_fn
