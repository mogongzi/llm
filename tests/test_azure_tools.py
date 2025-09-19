from providers.azure import build_payload, map_events, _build_openai_tools


def test_build_openai_tools():
    """Test building OpenAI tools from abstract tool definitions."""
    abstract_tools = [
        {
            "name": "get_current_time",
            "description": "Get current date/time",
            "input_schema": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string"},
                    "format": {"type": "string", "enum": ["iso", "human", "unix"]}
                },
                "required": []
            }
        }
    ]
    
    openai_tools = _build_openai_tools(abstract_tools)
    
    expected = [
        {
            "type": "function",
            "function": {
                "name": "get_current_time",
                "description": "Get current date/time",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "timezone": {"type": "string"},
                        "format": {"type": "string", "enum": ["iso", "human", "unix"]}
                    },
                    "required": []
                }
            }
        }
    ]
    
    assert openai_tools == expected


def test_azure_build_payload_with_tools():
    """Test Azure payload building with tools."""
    messages = [{"role": "user", "content": "What time is it?"}]
    tools = [
        {
            "name": "get_current_time",
            "description": "Get current time",
            "input_schema": {
                "type": "object",
                "properties": {
                    "timezone": {"type": "string"}
                }
            }
        }
    ]
    
    payload = build_payload(messages, tools=tools, model="gpt-4o")
    
    # Check tools are converted and included
    assert "tools" in payload
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["function"]["name"] == "get_current_time"
    assert payload["tools"][0]["function"]["parameters"]["type"] == "object"


def test_azure_tool_events_mapping():
    """Test mapping of OpenAI tool call streaming events."""
    # Simulate OpenAI streaming response with tool calls
    sse_lines = [
        '{"choices":[{"delta":{"role":"assistant"},"index":0}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_123","function":{"name":"get_current_time","arguments":""}}]},"index":0}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"timezone\\""}}]},"index":0}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":" : \\"UTC\\"}"}}]},"index":0}]}',
        '{"choices":[{"finish_reason":"tool_calls","index":0}]}'
    ]
    
    events = list(map_events(iter(sse_lines)))
    
    # Should emit tool_start, tool_input_delta events, then tool_ready
    event_types = [event[0] for event in events]
    assert "tool_start" in event_types
    assert "tool_input_delta" in event_types  
    assert "tool_ready" in event_types
    
    # Check tool_start event contains proper JSON
    tool_start_event = next(event for event in events if event[0] == "tool_start")
    assert tool_start_event[1] is not None
    import json
    tool_info = json.loads(tool_start_event[1])
    assert tool_info["id"] == "call_123"
    assert tool_info["name"] == "get_current_time"


if __name__ == "__main__":
    test_build_openai_tools()
    test_azure_build_payload_with_tools()
    test_azure_tool_events_mapping()
    print("All Azure tools tests passed!")
