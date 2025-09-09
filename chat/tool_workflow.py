"""Tool execution workflow management."""

from typing import List


def process_tool_execution(tool_calls_made: List[dict], conversation, 
                          session, use_thinking: bool, tools_enabled: bool, 
                          usage, available_tools, stream_and_render_func, format_tool_messages_func) -> None:
    """Handle the complete tool execution workflow."""
    if not tool_calls_made:
        return
    
    # Convert tool calls to conversation messages
    tool_messages = format_tool_messages_func(tool_calls_made)
    conversation.add_tool_messages(tool_messages)
    
    # Get Claude's response to tool results
    followup_reply, followup_tokens, followup_cost = session.handle_tool_followup(
        conversation.get_sanitized_history(), use_thinking, tools_enabled, 
        available_tools, stream_and_render_func
    )
    
    # Update usage tracking
    usage.update(followup_tokens, followup_cost)
    
    # Store Claude's final response
    conversation.add_assistant_message(followup_reply)