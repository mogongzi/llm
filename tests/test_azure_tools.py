from providers.azure import build_payload, map_events, _build_openai_tools


def test_build_openai_tools():
    """Test building OpenAI tools from abstract tool definitions."""
    abstract_tools = [
        {
            "name": "calculate",
            "description": "Perform mathematical calculations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "Mathematical expression to evaluate"
                    }
                },
                "required": ["expression"]
            }
        }
    ]
    
    openai_tools = _build_openai_tools(abstract_tools)
    
    expected = [
        {
            "type": "function",
            "function": {
                "name": "calculate",
                "description": "Perform mathematical calculations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Mathematical expression to evaluate"
                        }
                    },
                    "required": ["expression"]
                }
            }
        }
    ]
    
    assert openai_tools == expected


def test_azure_build_payload_with_tools():
    """Test Azure payload building with tools."""
    messages = [{"role": "user", "content": "Calculate 2+2"}]
    tools = [
        {
            "name": "calculate",
            "description": "Perform calculations",
            "input_schema": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"}
                }
            }
        }
    ]
    
    payload = build_payload(messages, tools=tools, model="gpt-4o")
    
    # Check tools are converted and included
    assert "tools" in payload
    assert len(payload["tools"]) == 1
    assert payload["tools"][0]["type"] == "function"
    assert payload["tools"][0]["function"]["name"] == "calculate"
    assert payload["tools"][0]["function"]["parameters"]["type"] == "object"


def test_azure_tool_events_mapping():
    """Test mapping of OpenAI tool call streaming events."""
    # Simulate OpenAI streaming response with tool calls
    sse_lines = [
        '{"choices":[{"delta":{"role":"assistant"},"index":0}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"id":"call_123","function":{"name":"calculate","arguments":""}}]},"index":0}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":"{\\"expression\\""}}]},"index":0}]}',
        '{"choices":[{"delta":{"tool_calls":[{"index":0,"function":{"arguments":": \\"2+2\\"}"}}]},"index":0}]}',
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
    assert tool_info["name"] == "calculate"


if __name__ == "__main__":
    test_build_openai_tools()
    test_azure_build_payload_with_tools()
    test_azure_tool_events_mapping()
    print("All Azure tools tests passed!")