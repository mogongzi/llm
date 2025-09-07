#!/usr/bin/env python3
"""
Test script for complete tool calling flow.
"""

import json
import sys
import os

# Add current directory to path to import our modules
sys.path.append('.')

def test_tool_message_formatting():
    """Test the format_tool_messages function."""
    
    # Import the function we want to test
    exec(open('llm-cli.py').read(), globals())
    # Now format_tool_messages should be available
    
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
    
    print("=== Tool Message Formatting Test ===")
    print(f"Input tool calls: {len(mock_tool_calls)}")
    print(f"Output messages: {len(messages)}")
    
    # Should produce 2 messages: assistant with tool_use, user with tool_result
    assert len(messages) == 2, f"Expected 2 messages, got {len(messages)}"
    
    # Check assistant message
    assistant_msg = messages[0]
    print(f"Assistant message: {json.dumps(assistant_msg, indent=2)}")
    assert assistant_msg["role"] == "assistant"
    assert isinstance(assistant_msg["content"], list)
    assert len(assistant_msg["content"]) == 1
    assert assistant_msg["content"][0]["type"] == "tool_use"
    assert assistant_msg["content"][0]["name"] == "calculate"
    
    # Check user message with tool result
    user_msg = messages[1] 
    print(f"User message: {json.dumps(user_msg, indent=2)}")
    assert user_msg["role"] == "user"
    assert isinstance(user_msg["content"], list)
    assert len(user_msg["content"]) == 1
    assert user_msg["content"][0]["type"] == "tool_result"
    assert user_msg["content"][0]["content"] == "2 + 2 = 4"
    
    print("✅ Tool message formatting test passed!")
    return True

def test_conversation_flow():
    """Test the complete conversation flow logic."""
    
    print("\n=== Conversation Flow Logic Test ===")
    
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
    
    # Test message integration - function should be available from previous exec
    
    # Start with user message
    history = initial_history.copy()
    print(f"Initial history: {len(history)} messages")
    
    # Add tool messages  
    tool_messages = format_tool_messages(mock_tool_calls)
    history.extend(tool_messages)
    print(f"After adding tool messages: {len(history)} messages")
    
    # Add Claude's final response
    history.append({"role": "assistant", "content": "Based on the calculation, 2 + 2 equals 4."})
    print(f"After final response: {len(history)} messages")
    
    # Verify conversation structure
    expected_roles = ["user", "assistant", "user", "assistant"]
    actual_roles = [msg["role"] for msg in history]
    
    print(f"Expected roles: {expected_roles}")
    print(f"Actual roles: {actual_roles}")
    
    assert actual_roles == expected_roles, f"Role sequence mismatch"
    
    # Check that we don't have consecutive same roles
    for i in range(len(history) - 1):
        current_role = history[i]["role"]
        next_role = history[i + 1]["role"] 
        assert current_role != next_role, f"Consecutive {current_role} messages at positions {i}, {i+1}"
    
    print("✅ Conversation flow test passed!")
    return True

if __name__ == "__main__":
    try:
        test_tool_message_formatting()
        test_conversation_flow() 
        print("\n🎉 All tests passed! Complete tool calling flow is ready.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)