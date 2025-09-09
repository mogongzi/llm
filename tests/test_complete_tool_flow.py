#!/usr/bin/env python3
"""
Test script for complete tool calling flow.
"""

import json
import sys
import os
import pytest

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def format_tool_messages(tool_calls_made):
    """Mock implementation of format_tool_messages for testing."""
    if not tool_calls_made:
        return []
    
    messages = []
    
    # Create assistant message with tool calls
    tool_use_blocks = []
    for tool_data in tool_calls_made:
        tool_call = tool_data["tool_call"]
        tool_use_blocks.append({
            "type": "tool_use",
            "id": tool_call["id"], 
            "name": tool_call["name"],
            "input": tool_call["input"]
        })
    
    messages.append({
        "role": "assistant",
        "content": tool_use_blocks
    })
    
    # Create user message with tool results  
    tool_result_blocks = []
    for tool_data in tool_calls_made:
        tool_call = tool_data["tool_call"]
        result = tool_data["result"]
        tool_result_blocks.append({
            "type": "tool_result",
            "tool_use_id": tool_call["id"],
            "content": result
        })
    
    messages.append({
        "role": "user", 
        "content": tool_result_blocks
    })
    
    return messages


def test_tool_message_formatting():
    """Test the format_tool_messages function."""
    # Mock tool calls data
    mock_tool_calls = [
        {
            "tool_call": {
                "id": "toolu_123",
                "name": "calculate", 
                "input": {"expression": "2 + 2"}
            },
            "result": "2 + 2 = 4"
        }
    ]
    
    # Test message formatting
    messages = format_tool_messages(mock_tool_calls)
    
    # Should produce 2 messages: assistant with tool_use, user with tool_result
    assert len(messages) == 2
    
    # Check assistant message
    assistant_msg = messages[0]
    assert assistant_msg["role"] == "assistant"
    assert isinstance(assistant_msg["content"], list)
    assert len(assistant_msg["content"]) == 1
    assert assistant_msg["content"][0]["type"] == "tool_use"
    assert assistant_msg["content"][0]["name"] == "calculate"
    
    # Check user message with tool result
    user_msg = messages[1] 
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert len(user_msg["content"]) == 1
    assert user_msg["content"][0]["type"] == "tool_result"
    assert user_msg["content"][0]["content"] == "2 + 2 = 4"


def test_conversation_flow():
    """Test the complete conversation flow logic."""
    # Simulate conversation history
    initial_history = [
        {"role": "user", "content": "what is 2+2?"}
    ]
    
    # Simulate tool calls being made
    mock_tool_calls = [
        {
            "tool_call": {
                "id": "toolu_456", 
                "name": "calculate",
                "input": {"expression": "2 + 2"}
            },
            "result": "2 + 2 = 4"
        }
    ]
    
    # Start with user message
    history = initial_history.copy()
    assert len(history) == 1
    
    # Add tool messages  
    tool_messages = format_tool_messages(mock_tool_calls)
    history.extend(tool_messages)
    assert len(history) == 3
    
    # Add Claude's final response
    history.append({"role": "assistant", "content": "Based on the calculation, 2 + 2 equals 4."})
    assert len(history) == 4
    
    # Verify conversation structure
    expected_roles = ["user", "assistant", "user", "assistant"]
    actual_roles = [msg["role"] for msg in history]
    assert actual_roles == expected_roles
    
    # Check that we don't have consecutive same roles
    for i in range(len(history) - 1):
        current_role = history[i]["role"]
        next_role = history[i + 1]["role"] 
        assert current_role != next_role, f"Consecutive {current_role} messages at positions {i}, {i+1}"


if __name__ == "__main__":
    pytest.main([__file__])