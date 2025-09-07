#!/usr/bin/env python3
"""
Simple test for tool message formatting.
"""

import json

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

def test():
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
    
    print("=== Tool Message Format Test ===")
    print(f"Generated {len(messages)} messages")
    
    for i, msg in enumerate(messages):
        print(f"\nMessage {i+1}:")
        print(json.dumps(msg, indent=2))
    
    # Test conversation flow
    conversation = [
        {"role": "user", "content": "what is 2+2?"}
    ]
    conversation.extend(messages)
    conversation.append({"role": "assistant", "content": "Based on the calculation, 2 + 2 equals 4."})
    
    print(f"\n=== Complete Conversation ({len(conversation)} messages) ===")
    roles = [msg["role"] for msg in conversation]
    print(f"Role sequence: {' -> '.join(roles)}")
    
    # Verify no consecutive same roles
    for i in range(len(conversation) - 1):
        current = conversation[i]["role"]
        next_role = conversation[i+1]["role"]
        if current == next_role:
            print(f"❌ ERROR: Consecutive {current} messages!")
            return False
    
    print("✅ Perfect alternating conversation!")
    return True

if __name__ == "__main__":
    test()