from providers.azure import build_payload, map_events


def test_azure_build_payload_basic():
    messages = [{"role": "user", "content": "Hello"}]
    body = build_payload(messages, model="gpt-4o", max_tokens=128, temperature=0.2)
    assert body["model"] == "gpt-4o"
    # Should have system message prepended automatically
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"] == "Use Markdown formatting when appropriate."
    assert body["messages"][1] == {"role": "user", "content": "Hello"}
    assert body["stream"] is True
    assert body["max_completion_tokens"] == 128
    assert body["temperature"] == 0.2


def test_azure_map_events_sequence():
    frames = [
        '{"id":"x","object":"chat.completion.chunk","model":"gpt-4o","choices":[{"index":0,"delta":{"role":"assistant","content":"Hello"},"finish_reason":null}]}',
        '{"id":"y","object":"chat.completion.chunk","model":"gpt-4o","choices":[{"index":0,"delta":{"content":" World"},"finish_reason":null}]}',
        '{"id":"z","object":"chat.completion.chunk","model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}'
    ]
    events = list(map_events(iter(frames)))
    # Model may be emitted multiple times; ensure first is present and text aggregation works
    assert events[0] == ("model", "gpt-4o")
    assert ("text", "Hello") in events
    assert ("text", " World") in events
    assert events[-1] == ("done", None)


def test_azure_build_payload_without_model_omits_model_key():
    messages = [{"role": "user", "content": "Hello"}]
    body = build_payload(messages, model=None, max_tokens=None)
    assert "model" not in body
    # Should have system message prepended automatically
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][1] == {"role": "user", "content": "Hello"}
    assert body["stream"] is True


def test_azure_build_payload_preserves_existing_system_message():
    """Test that existing system messages are not overridden."""
    messages = [
        {"role": "system", "content": "Custom system prompt"},
        {"role": "user", "content": "Hello"}
    ]
    body = build_payload(messages, model="gpt-4o")
    # Should preserve existing system message
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "system"
    assert body["messages"][0]["content"] == "Custom system prompt"
    assert body["messages"][1] == {"role": "user", "content": "Hello"}


def test_azure_map_events_azure_like_stream():
    # Simulate Azure OpenAI Chat Completions SSE as provided
    frames = [
        '{"choices":[],"created":0,"id":"","model":"","object":""}',
        '{"choices":[{"delta":{"content":"","role":"assistant"},"finish_reason":null,"index":0}],"created":1756097033,"id":"x","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{"content":"I"},"finish_reason":null,"index":0}],"created":1756097033,"id":"x","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{"content":"."},"finish_reason":null,"index":0}],"created":1756097033,"id":"x","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{},"finish_reason":"stop","index":0}],"created":1756097033,"id":"x","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
    ]
    events = list(map_events(iter(frames)))
    # Should emit model exactly once and only non-empty
    models = [v for (k, v) in events if k == "model"]
    assert models == ["gpt-5-2025-08-07"]
    # Text chunks should include 'I' and '.' and end with done
    texts = [v for (k, v) in events if k == "text"]
    assert texts == ["I", "."]
    assert events[-1] == ("done", None)


def test_azure_payload_includes_stream_options():
    """Test that stream_options are included in the payload for token tracking."""
    messages = [{"role": "user", "content": "Hello"}]
    body = build_payload(messages, model="gpt-5")

    assert "stream_options" in body
    assert body["stream_options"]["include_usage"] is True


def test_azure_map_events_token_tracking_gpt5():
    """Test token tracking with GPT-5 pricing in Azure OpenAI response."""
    # Simulate Azure OpenAI response with usage data (based on actual API behavior)
    frames = [
        '{"choices":[{"delta":{"content":"Hello","role":"assistant"},"finish_reason":null,"index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{"content":" world"},"finish_reason":null,"index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{},"finish_reason":"stop","index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk","usage":{"completion_tokens":549,"prompt_tokens":10,"total_tokens":559}}'
    ]

    events = list(map_events(iter(frames)))

    # Should emit model, text, and tokens events
    assert ("model", "gpt-5-2025-08-07") in events
    assert ("text", "Hello") in events
    assert ("text", " world") in events

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

    assert total_tokens == 559
    assert input_tokens == 10
    assert output_tokens == 549

    # Verify GPT-5 pricing calculation: $0.00091/1K input, $0.00677/1K output
    expected_input_cost = (10 / 1000) * 0.00091
    expected_output_cost = (549 / 1000) * 0.00677
    expected_total_cost = expected_input_cost + expected_output_cost

    assert abs(cost - expected_total_cost) < 0.0001


def test_azure_map_events_token_tracking_with_reasoning():
    """Test token tracking with reasoning tokens in completion_tokens_details."""
    frames = [
        '{"choices":[{"delta":{"content":"Thinking..."},"finish_reason":null,"index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{},"finish_reason":"stop","index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk","usage":{"completion_tokens":549,"completion_tokens_details":{"reasoning_tokens":512,"accepted_prediction_tokens":0,"audio_tokens":0,"rejected_prediction_tokens":0},"prompt_tokens":10,"prompt_tokens_details":{"audio_tokens":0,"cached_tokens":0},"total_tokens":559}}'
    ]

    events = list(map_events(iter(frames)))

    # Should still handle token tracking correctly even with detailed breakdown
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    token_info = token_events[0]
    parts = token_info.split("|")

    total_tokens = int(parts[0])
    input_tokens = int(parts[1])
    output_tokens = int(parts[2])

    assert total_tokens == 559
    assert input_tokens == 10
    assert output_tokens == 549  # Total completion tokens including reasoning


def test_azure_map_events_no_usage_data():
    """Test that missing usage data triggers fallback estimation."""
    frames = [
        '{"choices":[{"delta":{"content":"Hello"},"finish_reason":null,"index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{},"finish_reason":"stop","index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}'
    ]

    events = list(map_events(iter(frames)))

    # Should emit text and done events, plus estimated tokens
    assert ("text", "Hello") in events
    assert ("done", None) in events

    # Should emit estimated tokens as fallback
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    # Should be marked as estimated
    token_info = token_events[0]
    assert token_info.startswith("~"), "Should use estimated tokens when usage data is missing"


def test_azure_map_events_zero_tokens():
    """Test handling of zero token usage."""
    frames = [
        '{"choices":[],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk","usage":{"completion_tokens":0,"prompt_tokens":0,"total_tokens":0}}'
    ]

    events = list(map_events(iter(frames)))

    # Should not emit tokens event for zero total tokens
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 0


def test_azure_map_events_fallback_token_estimation():
    """Test fallback token estimation when usage data is not provided."""
    frames = [
        '{"choices":[{"delta":{"content":"Hello","role":"assistant"},"finish_reason":null,"index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{"content":" world! How are you doing today?"},"finish_reason":null,"index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{},"finish_reason":"stop","index":0}],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',  # finish_reason
        '{"choices":[],"created":1757928640,"id":"test","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}'  # Empty chunk, no usage data
    ]

    events = list(map_events(iter(frames)))

    # Should emit text and estimated tokens events
    assert ("text", "Hello") in events
    assert ("text", " world! How are you doing today?") in events

    # Check for estimated token event
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    # Parse estimated token info: "~total|~input|~output|cost"
    token_info = token_events[0]
    assert token_info.startswith("~"), "Token estimation should be prefixed with ~"

    parts = token_info.split("|")
    assert len(parts) == 4

    # Verify estimated values are reasonable
    estimated_total = int(parts[0].lstrip("~"))
    estimated_input = int(parts[1].lstrip("~"))
    estimated_output = int(parts[2].lstrip("~"))
    estimated_cost = float(parts[3])

    assert estimated_total > 0
    assert estimated_input > 0
    assert estimated_output > 0
    assert estimated_cost > 0
    assert estimated_total == estimated_input + estimated_output

    # Estimated output should be reasonable for the text length
    # "Hello world! How are you doing today?" = 7 words, so ~9 tokens estimated
    assert 5 <= estimated_output <= 15  # Reasonable range


def test_azure_map_events_estimated_tokens_parsing():
    """Test that streaming client can parse estimated tokens correctly."""
    # Simulate estimated token event
    token_info = "~25|~10|~15|0.000125"
    parts = token_info.split("|")

    # Test parsing logic from streaming client
    total_str = parts[0].lstrip("~")
    total_tokens = int(total_str) if total_str.isdigit() else 0
    cost = float(parts[3]) if parts[3] else 0.0

    assert total_tokens == 25
    assert cost == 0.000125


def test_azure_map_events_real_world_sequence():
    """Test with real Azure OpenAI response sequence from actual logs."""
    frames = [
        '{"choices":[{"delta":{"content":"Here","role":"assistant"},"finish_reason":null,"index":0}],"created":1757929526,"id":"chatcmpl-CG03ypUtcd7zUw0jqTuFwJFmPFWqb","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{"content":"\'s a simple"},"finish_reason":null,"index":0}],"created":1757929526,"id":"chatcmpl-CG03ypUtcd7zUw0jqTuFwJFmPFWqb","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{"content":" Hello, world!"},"finish_reason":null,"index":0}],"created":1757929526,"id":"chatcmpl-CG03ypUtcd7zUw0jqTuFwJFmPFWqb","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[{"delta":{},"finish_reason":"stop","index":0}],"created":1757929526,"id":"chatcmpl-CG03ypUtcd7zUw0jqTuFwJFmPFWqb","model":"gpt-5-2025-08-07","object":"chat.completion.chunk"}',
        '{"choices":[],"created":1757929526,"id":"chatcmpl-CG03ypUtcd7zUw0jqTuFwJFmPFWqb","model":"gpt-5-2025-08-07","object":"chat.completion.chunk","usage":{"completion_tokens":799,"completion_tokens_details":{"reasoning_tokens":704},"prompt_tokens":24,"total_tokens":823}}'
    ]

    events = list(map_events(iter(frames)))

    # Should emit model, text chunks, tokens, and done
    assert ("model", "gpt-5-2025-08-07") in events
    assert ("text", "Here") in events
    assert ("text", "'s a simple") in events
    assert ("text", " Hello, world!") in events
    assert ("done", None) in events

    # Check token event
    token_events = [v for (k, v) in events if k == "tokens"]
    assert len(token_events) == 1

    token_info = token_events[0]
    parts = token_info.split("|")
    assert len(parts) == 4

    total_tokens = int(parts[0])
    input_tokens = int(parts[1])
    output_tokens = int(parts[2])
    cost = float(parts[3])

    # Verify actual values from logs
    assert total_tokens == 823
    assert input_tokens == 24
    assert output_tokens == 799

    # Verify GPT-5 cost calculation
    expected_input_cost = (24 / 1000) * 0.00091
    expected_output_cost = (799 / 1000) * 0.00677
    expected_total_cost = expected_input_cost + expected_output_cost
    assert abs(cost - expected_total_cost) < 0.0001
