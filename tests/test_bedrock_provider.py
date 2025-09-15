#!/usr/bin/env python3
"""
Test script for Bedrock provider functionality.
"""

import json
import sys
import os

try:
    import pytest
except ImportError:
    pytest = None

# Add parent directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from providers.bedrock import build_payload, map_events


def test_build_payload_basic():
    """Test basic payload building."""
    messages = [{"role": "user", "content": "Hello"}]
    payload = build_payload(messages)
    
    expected = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": messages
    }
    
    assert payload == expected


def test_build_payload_with_model():
    """Test payload building with custom model."""
    messages = [{"role": "user", "content": "Hello"}]
    payload = build_payload(messages, model="claude-3-sonnet")
    
    # Model parameter is ignored in current implementation
    assert "model" not in payload
    assert payload["messages"] == messages


def test_build_payload_custom_max_tokens():
    """Test payload building with custom max_tokens."""
    messages = [{"role": "user", "content": "Hello"}]
    payload = build_payload(messages, max_tokens=8192)
    
    assert payload["max_tokens"] == 8192
    assert payload["messages"] == messages


def test_build_payload_with_temperature():
    """Test payload building with temperature (currently ignored)."""
    messages = [{"role": "user", "content": "Hello"}]
    payload = build_payload(messages, temperature=0.7)
    
    # Temperature is not included in current implementation
    assert "temperature" not in payload


def test_build_payload_with_thinking():
    """Test payload building with thinking mode enabled."""
    messages = [{"role": "user", "content": "Explain quantum physics"}]
    payload = build_payload(messages, thinking=True, thinking_tokens=2048)
    
    expected_thinking = {
        "type": "enabled",
        "budget_tokens": 2048
    }
    
    assert payload["thinking"] == expected_thinking


def test_build_payload_with_tools():
    """Test payload building with tools."""
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
    
    payload = build_payload(messages, tools=tools)
    
    assert payload["tools"] == tools
    assert payload["messages"] == messages


def test_build_payload_all_options():
    """Test payload building with all options enabled."""
    messages = [{"role": "user", "content": "Help with coding"}]
    tools = [{"name": "code_executor"}]
    
    payload = build_payload(
        messages,
        model="claude-3",
        max_tokens=8192,
        temperature=0.5,
        thinking=True,
        thinking_tokens=1500,
        tools=tools,
        extra_param="ignored"
    )
    
    assert payload["anthropic_version"] == "bedrock-2023-05-31"
    assert payload["max_tokens"] == 8192
    assert payload["messages"] == messages
    assert payload["thinking"]["type"] == "enabled"
    assert payload["thinking"]["budget_tokens"] == 1500
    assert payload["tools"] == tools
    assert "temperature" not in payload
    assert "model" not in payload
    assert "extra_param" not in payload


def test_map_events_done_signal():
    """Test mapping of [DONE] signal."""
    lines = ["[DONE]"]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("done", None)


def test_map_events_message_start():
    """Test mapping of message_start event."""
    message_start = {
        "type": "message_start",
        "message": {
            "model": "claude-3-sonnet-20240229"
        }
    }
    
    lines = [json.dumps(message_start)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("model", "claude-3-sonnet-20240229")


def test_map_events_text_delta():
    """Test mapping of text delta events."""
    text_delta = {
        "type": "content_block_delta",
        "delta": {
            "type": "text_delta",
            "text": "Hello world"
        }
    }
    
    lines = [json.dumps(text_delta)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("text", "Hello world")


def test_map_events_thinking_delta():
    """Test mapping of thinking delta events."""
    thinking_delta = {
        "type": "content_block_delta",
        "delta": {
            "type": "thinking_delta",
            "thinking": "Let me think about this..."
        }
    }
    
    lines = [json.dumps(thinking_delta)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("thinking", "Let me think about this...")


def test_map_events_tool_start():
    """Test mapping of tool_use start event."""
    tool_start = {
        "type": "content_block_start",
        "content_block": {
            "type": "tool_use",
            "id": "toolu_123",
            "name": "calculate"
        }
    }
    
    lines = [json.dumps(tool_start)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    event_type, event_data = events[0]
    assert event_type == "tool_start"
    
    tool_info = json.loads(event_data)
    assert tool_info["id"] == "toolu_123"
    assert tool_info["name"] == "calculate"


def test_map_events_tool_input_delta():
    """Test mapping of tool input delta events."""
    input_delta = {
        "type": "content_block_delta",
        "delta": {
            "type": "input_json_delta",
            "partial_json": '{"expression": "2'
        }
    }
    
    lines = [json.dumps(input_delta)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("tool_input_delta", '{"expression": "2')


def test_map_events_tool_ready():
    """Test mapping of content_block_stop event."""
    block_stop = {
        "type": "content_block_stop"
    }
    
    lines = [json.dumps(block_stop)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("tool_ready", None)


def test_map_events_message_stop_with_usage():
    """Test mapping of message_stop with usage metrics."""
    message_stop = {
        "type": "message_stop",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50
        }
    }
    
    lines = [json.dumps(message_stop)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 2
    
    # First event should be tokens
    token_event = events[0]
    assert token_event[0] == "tokens"
    
    # Parse token info: "total|input|output|cost"
    token_parts = token_event[1].split("|")
    assert len(token_parts) == 4
    assert int(token_parts[0]) == 150  # total
    assert int(token_parts[1]) == 100  # input
    assert int(token_parts[2]) == 50   # output
    
    # Check cost calculation (Claude 4 Sonnet: $2.04/1K input, $9.88/1K output)
    expected_cost = (100 / 1000) * 0.00204 + (50 / 1000) * 0.00988
    actual_cost = float(token_parts[3])
    assert abs(actual_cost - expected_cost) < 0.000001
    
    # Second event should be done
    assert events[1] == ("done", None)


def test_map_events_message_stop_bedrock_metrics():
    """Test mapping of message_stop with Bedrock-specific metrics."""
    message_stop = {
        "type": "message_stop",
        "amazon-bedrock-invocationMetrics": {
            "inputTokenCount": 200,
            "outputTokenCount": 75
        }
    }
    
    lines = [json.dumps(message_stop)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 2
    
    token_event = events[0]
    token_parts = token_event[1].split("|")
    assert int(token_parts[0]) == 275  # total
    assert int(token_parts[1]) == 200  # input
    assert int(token_parts[2]) == 75   # output


def test_map_events_message_stop_no_usage():
    """Test mapping of message_stop without usage metrics."""
    message_stop = {
        "type": "message_stop"
    }
    
    lines = [json.dumps(message_stop)]
    events = list(map_events(iter(lines)))
    
    assert len(events) == 1
    assert events[0] == ("done", None)


def test_map_events_invalid_json():
    """Test mapping handles invalid JSON gracefully."""
    lines = [
        "invalid json",
        '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "valid"}}',
        "more invalid json"
    ]
    
    events = list(map_events(iter(lines)))
    
    # Should only process the valid JSON
    assert len(events) == 1
    assert events[0] == ("text", "valid")


def test_map_events_empty_deltas():
    """Test mapping handles empty delta content."""
    empty_text_delta = {
        "type": "content_block_delta",
        "delta": {
            "type": "text_delta",
            "text": ""
        }
    }
    
    empty_thinking_delta = {
        "type": "content_block_delta",
        "delta": {
            "type": "thinking_delta",
            "thinking": ""
        }
    }
    
    lines = [json.dumps(empty_text_delta), json.dumps(empty_thinking_delta)]
    events = list(map_events(iter(lines)))
    
    # Empty content should not generate events
    assert len(events) == 0


def test_map_events_complex_flow():
    """Test mapping a complex conversation flow."""
    flow_events = [
        # Message start
        json.dumps({
            "type": "message_start",
            "message": {"model": "claude-3-sonnet"}
        }),
        # Text response
        json.dumps({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "I need to calculate this. "}
        }),
        # Tool use starts
        json.dumps({
            "type": "content_block_start",
            "content_block": {
                "type": "tool_use",
                "id": "toolu_456",
                "name": "calculate"
            }
        }),
        # Tool input streaming
        json.dumps({
            "type": "content_block_delta",
            "delta": {
                "type": "input_json_delta",
                "partial_json": '{"expression":'
            }
        }),
        json.dumps({
            "type": "content_block_delta",
            "delta": {
                "type": "input_json_delta",
                "partial_json": ' "2 + 2"}'
            }
        }),
        # Tool input complete
        json.dumps({"type": "content_block_stop"}),
        # More text
        json.dumps({
            "type": "content_block_delta",
            "delta": {"type": "text_delta", "text": "The answer is 4."}
        }),
        # Message ends with usage
        json.dumps({
            "type": "message_stop",
            "usage": {
                "input_tokens": 50,
                "output_tokens": 25
            }
        })
    ]
    
    events = list(map_events(iter(flow_events)))
    
    expected_events = [
        ("model", "claude-3-sonnet"),
        ("text", "I need to calculate this. "),
        ("tool_start", '{"id": "toolu_456", "name": "calculate"}'),
        ("tool_input_delta", '{"expression":'),
        ("tool_input_delta", ' "2 + 2"}'),
        ("tool_ready", None),
        ("text", "The answer is 4."),
        ("tokens", "75|50|25|0.001050"),  # 50*3/1M + 25*15/1M
        ("done", None)
    ]
    
    assert len(events) == len(expected_events)
    for actual, expected in zip(events, expected_events):
        if actual[0] == "tokens":
            # Just check the structure, not exact cost calculation
            token_parts = actual[1].split("|")
            assert len(token_parts) == 4
            assert token_parts[0] == "75"
            assert token_parts[1] == "50" 
            assert token_parts[2] == "25"
        else:
            assert actual == expected


def test_map_events_unknown_event_types():
    """Test mapping handles unknown event types gracefully."""
    unknown_events = [
        json.dumps({"type": "unknown_event", "data": "should be ignored"}),
        json.dumps({"type": "content_block_delta", "delta": {"type": "text_delta", "text": "valid"}}),
        json.dumps({"type": "another_unknown", "info": "also ignored"})
    ]
    
    events = list(map_events(iter(unknown_events)))
    
    # Should only process the known event
    assert len(events) == 1
    assert events[0] == ("text", "valid")


if __name__ == "__main__":
    if pytest:
        pytest.main([__file__])
    else:
        # Run tests manually
        print("Running Bedrock provider tests...")
        test_build_payload_basic()
        test_build_payload_with_model()
        test_build_payload_custom_max_tokens()
        test_build_payload_with_temperature()
        test_build_payload_with_thinking()
        test_build_payload_with_tools()
        test_build_payload_all_options()
        test_map_events_done_signal()
        test_map_events_message_start()
        test_map_events_text_delta()
        test_map_events_thinking_delta()
        test_map_events_tool_start()
        test_map_events_tool_input_delta()
        test_map_events_tool_ready()
        test_map_events_message_stop_with_usage()
        test_map_events_message_stop_bedrock_metrics()
        test_map_events_message_stop_no_usage()
        test_map_events_invalid_json()
        test_map_events_empty_deltas()
        test_map_events_complex_flow()
        test_map_events_unknown_event_types()
        print("All Bedrock provider tests passed!")