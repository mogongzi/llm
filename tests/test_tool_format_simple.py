#!/usr/bin/env python3
"""
Simple test for tool message formatting.
"""

import json
import pytest


def format_tool_messages(tool_calls_made):
    """Test version of the format_tool_messages function."""
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
    """Test tool message formatting functionality."""
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
    
    messages = format_tool_messages(mock_tool_calls)
    
    # Should generate exactly 2 messages
    assert len(messages) == 2
    
    # Check assistant message structure
    assistant_msg = messages[0]
    assert assistant_msg["role"] == "assistant"
    assert isinstance(assistant_msg["content"], list)
    assert len(assistant_msg["content"]) == 1
    
    tool_use = assistant_msg["content"][0]
    assert tool_use["type"] == "tool_use"
    assert tool_use["id"] == "toolu_123"
    assert tool_use["name"] == "calculate"
    assert tool_use["input"] == {"expression": "2 + 2"}
    
    # Check user message structure
    user_msg = messages[1]
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert len(user_msg["content"]) == 1
    
    tool_result = user_msg["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "toolu_123"
    assert tool_result["content"] == "2 + 2 = 4"


def test_conversation_flow():
    """Test complete conversation flow with tool messages."""
    mock_tool_calls = [
        {
            "tool_call": {
                "id": "toolu_456",
                "name": "calculate", 
                "input": {"expression": "5 * 3"}
            },
            "result": "5 * 3 = 15"
        }
    ]
    
    # Build complete conversation
    conversation = [
        {"role": "user", "content": "what is 5*3?"}
    ]
    
    tool_messages = format_tool_messages(mock_tool_calls)
    conversation.extend(tool_messages)
    conversation.append({"role": "assistant", "content": "Based on the calculation, 5 * 3 equals 15."})
    
    # Should have 4 messages total
    assert len(conversation) == 4
    
    # Check role sequence
    roles = [msg["role"] for msg in conversation]
    expected_roles = ["user", "assistant", "user", "assistant"]
    assert roles == expected_roles
    
    # Verify no consecutive same roles
    for i in range(len(conversation) - 1):
        current = conversation[i]["role"]
        next_role = conversation[i+1]["role"]
        assert current != next_role, f"Consecutive {current} messages at positions {i}, {i+1}"


def test_empty_tool_calls():
    """Test handling of empty tool calls."""
    messages = format_tool_messages([])
    assert messages == []
    
    messages = format_tool_messages(None)
    assert messages == []


def test_multiple_tool_calls():
    """Test formatting multiple tool calls in one message."""
    mock_tool_calls = [
        {
            "tool_call": {
                "id": "toolu_1",
                "name": "calculate", 
                "input": {"expression": "2 + 2"}
            },
            "result": "4"
        },
        {
            "tool_call": {
                "id": "toolu_2",
                "name": "calculate", 
                "input": {"expression": "3 * 3"}
            },
            "result": "9"
        }
    ]
    
    messages = format_tool_messages(mock_tool_calls)
    
    # Should still generate exactly 2 messages
    assert len(messages) == 2
    
    # Assistant message should have 2 tool_use blocks
    assistant_msg = messages[0]
    assert len(assistant_msg["content"]) == 2
    
    # User message should have 2 tool_result blocks
    user_msg = messages[1]
    assert len(user_msg["content"]) == 2
    
    # Check tool IDs match
    tool_use_ids = [block["id"] for block in assistant_msg["content"]]
    tool_result_ids = [block["tool_use_id"] for block in user_msg["content"]]
    assert set(tool_use_ids) == set(tool_result_ids)


if __name__ == "__main__":
    pytest.main([__file__])