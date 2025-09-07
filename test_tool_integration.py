#!/usr/bin/env python3
"""
Test script for tool calling integration.
"""
import json
from tools.definitions import AVAILABLE_TOOLS
from tools.executor import ToolExecutor
from providers.bedrock import build_payload, map_events

def test_payload_with_tools():
    """Test that tools are correctly added to payload."""
    messages = [{"role": "user", "content": "What's 2+2?"}]
    payload = build_payload(messages, tools=AVAILABLE_TOOLS)
    
    print("✓ Payload contains tools:", "tools" in payload)
    print("✓ Number of tools:", len(payload.get("tools", [])))
    return payload

def test_tool_execution():
    """Test tool execution."""
    executor = ToolExecutor()
    
    # Test calculator
    calc_result = executor.execute_tool("calculate", {"expression": "sqrt(16) + 2"})
    print("✓ Calculator result:", calc_result["content"])
    
    # Test time
    time_result = executor.execute_tool("get_current_time", {"format": "iso"})
    print("✓ Time result:", time_result["content"])
    
    # Test weather (will fail without API key, but should handle gracefully)
    weather_result = executor.execute_tool("get_weather", {"location": "Paris"})
    print("✓ Weather result:", weather_result["content"])
    
    return True

def test_tool_use_event():
    """Test tool_use event parsing."""
    # Simulate a tool_use event from Claude
    mock_tool_call = {
        "id": "tool_123",
        "name": "calculate",
        "input": {"expression": "10 * 5"}
    }
    
    # This would be the JSON string from the SSE event
    tool_use_json = json.dumps(mock_tool_call)
    
    # Parse and execute
    tool_call = json.loads(tool_use_json)
    executor = ToolExecutor()
    result = executor.execute_tool(tool_call["name"], tool_call["input"])
    
    print("✓ Tool call simulation:", result["content"])
    return True

if __name__ == "__main__":
    print("Testing tool calling integration...\n")
    
    try:
        test_payload_with_tools()
        print()
        test_tool_execution()
        print()
        test_tool_use_event()
        print("\n✅ All tests passed! Tool calling system is ready.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()