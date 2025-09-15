from providers.bedrock import map_events


def test_map_events_basic_sequence():
    frames = [
        '{"type":"message_start","message":{"model":"m1"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":" World"}}',
        '{"type":"message_stop"}',
    ]
    events = list(map_events(iter(frames)))
    assert events == [("model", "m1"), ("text", "Hello"), ("text", " World"), ("done", None)]


def test_map_events_done_marker():
    frames = ["[DONE]"]
    events = list(map_events(iter(frames)))
    assert events == [("done", None)]


def test_bedrock_map_events_token_tracking_claude4():
    """Test token tracking with Claude 4 Sonnet pricing in Bedrock response."""
    frames = [
        '{"type":"message_start","message":{"model":"anthropic--claude-4-sonnet"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello world"}}',
        '{"type":"message_stop","amazon-bedrock-invocationMetrics":{"inputTokenCount":15,"outputTokenCount":25}}'
    ]

    events = list(map_events(iter(frames)))

    # Should emit model, text, tokens, and done events
    assert ("model", "anthropic--claude-4-sonnet") in events
    assert ("text", "Hello world") in events

    # Check token event exists and has correct format
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    # Parse token info: "total|input|output|cost"
    token_info = token_events[0]
    parts = token_info.split("|")
    assert len(parts) == 4

    total_tokens = int(parts[0])
    input_tokens = int(parts[1])
    output_tokens = int(parts[2])
    cost = float(parts[3])

    assert total_tokens == 40  # 15 + 25
    assert input_tokens == 15
    assert output_tokens == 25

    # Verify Claude 4 Sonnet pricing calculation: $0.00204/1K input, $0.00988/1K output
    expected_input_cost = (15 / 1000) * 0.00204
    expected_output_cost = (25 / 1000) * 0.00988
    expected_total_cost = expected_input_cost + expected_output_cost

    assert abs(cost - expected_total_cost) < 0.0001

    assert ("done", None) in events


def test_bedrock_map_events_usage_format():
    """Test token tracking with standard usage format (fallback)."""
    frames = [
        '{"type":"message_start","message":{"model":"anthropic--claude-4-sonnet"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Test"}}',
        '{"type":"message_stop","usage":{"input_tokens":10,"output_tokens":20}}'
    ]

    events = list(map_events(iter(frames)))

    # Should handle standard usage format as fallback
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    token_info = token_events[0]
    parts = token_info.split("|")

    total_tokens = int(parts[0])
    input_tokens = int(parts[1])
    output_tokens = int(parts[2])

    assert total_tokens == 30  # 10 + 20
    assert input_tokens == 10
    assert output_tokens == 20


def test_bedrock_map_events_no_usage_data():
    """Test that missing usage data doesn't break the event stream."""
    frames = [
        '{"type":"message_start","message":{"model":"anthropic--claude-4-sonnet"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Hello"}}',
        '{"type":"message_stop"}'
    ]

    events = list(map_events(iter(frames)))

    # Should emit text and done events, but no tokens event
    assert ("text", "Hello") in events
    assert ("done", None) in events

    # Should not emit any tokens events
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 0


def test_bedrock_map_events_zero_tokens():
    """Test handling of zero token usage."""
    frames = [
        '{"type":"message_stop","amazon-bedrock-invocationMetrics":{"inputTokenCount":0,"outputTokenCount":0}}'
    ]

    events = list(map_events(iter(frames)))

    # Should not emit tokens event for zero total tokens
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 0

    assert ("done", None) in events


def test_bedrock_map_events_thinking_tokens():
    """Test token tracking with thinking content."""
    frames = [
        '{"type":"message_start","message":{"model":"anthropic--claude-4-sonnet"}}',
        '{"type":"content_block_delta","delta":{"type":"thinking_delta","thinking":"Let me think..."}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Answer"}}',
        '{"type":"message_stop","amazon-bedrock-invocationMetrics":{"inputTokenCount":8,"outputTokenCount":50}}'
    ]

    events = list(map_events(iter(frames)))

    # Should emit thinking, text, and tokens events
    assert ("thinking", "Let me think...") in events
    assert ("text", "Answer") in events

    # Check token tracking still works with thinking
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    token_info = token_events[0]
    parts = token_info.split("|")

    total_tokens = int(parts[0])
    input_tokens = int(parts[1])
    output_tokens = int(parts[2])

    assert total_tokens == 58  # 8 + 50
    assert input_tokens == 8
    assert output_tokens == 50  # Should include thinking tokens
