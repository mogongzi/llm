from providers.azure import build_payload, map_events


def test_azure_build_payload_basic():
    messages = [{"role": "user", "content": "Hello"}]
    body = build_payload(messages, model="gpt-4o", max_tokens=128, temperature=0.2)
    assert body["model"] == "gpt-4o"
    assert body["messages"] == messages
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
    assert body["messages"] == messages
    assert body["stream"] is True


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
