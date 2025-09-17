from streaming_client import StreamingClient
from providers.bedrock import map_events as map_bedrock_events
from providers.azure import map_events as map_azure_events


def _make_iter_lines(frames):
    def _iter_lines(url: str, json=None, params=None, timeout=60.0, session=None):
        for line in frames:
            yield line
    return _iter_lines


def test_golden_client_bedrock_text_and_tokens(monkeypatch):
    frames = [
        '{"type":"message_start","message":{"model":"anthropic--claude-4-sonnet"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Intro line 1\\n"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"line 2\\n\\n"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"```python\\n"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"print(\'hi\')\\n"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"```\\n"}}',
        '{"type":"content_block_delta","delta":{"type":"text_delta","text":"Final para.\\n\\n"}}',
        '{"type":"message_stop","amazon-bedrock-invocationMetrics":{"inputTokenCount":10,"outputTokenCount":20}}',
    ]

    client = StreamingClient()
    monkeypatch.setattr(client, "iter_sse_lines", _make_iter_lines(frames))

    result = client.send_message(
        url="http://example.test/invoke",
        payload={"messages": []},
        mapper=map_bedrock_events,
        provider_name="bedrock",
    )

    assert result.error is None
    assert result.text == (
        "Intro line 1\n" +
        "line 2\n\n" +
        "```python\n" +
        "print('hi')\n" +
        "```\n" +
        "Final para.\n\n"
    )
    assert result.tokens == 30  # 10 in + 20 out
    # Cost is computed in provider; verify reasonable positive float
    assert isinstance(result.cost, float) and result.cost > 0


def test_golden_client_azure_text_and_tokens(monkeypatch):
    frames = [
        '{"id":"x","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"role":"assistant","content":"Intro line 1\\n"},"finish_reason":null}]}',
        '{"id":"y","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"line 2\\n\\n"},"finish_reason":null}]}',
        '{"id":"z1","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"```python\\n"},"finish_reason":null}]}',
        '{"id":"z2","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"print(\\"hi\\")\\n"},"finish_reason":null}]}',
        '{"id":"z3","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"```\\n"},"finish_reason":null}]}',
        '{"id":"w","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"Final para.\\n\\n"},"finish_reason":null}]}',
        '{"id":"w1","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}',
        '{"id":"w2","object":"chat.completion.chunk","model":"gpt-5","choices":[],"usage":{"completion_tokens":20,"prompt_tokens":10,"total_tokens":30}}',
    ]

    client = StreamingClient()
    monkeypatch.setattr(client, "iter_sse_lines", _make_iter_lines(frames))

    result = client.send_message(
        url="http://example.test/invoke",
        payload={"messages": []},
        mapper=map_azure_events,
        provider_name="azure",
    )

    assert result.error is None
    assert result.text == (
        "Intro line 1\n" +
        "line 2\n\n" +
        "```python\n" +
        'print("hi")\n' +
        "```\n" +
        "Final para.\n\n"
    )
    assert result.tokens == 30  # 10 in + 20 out
    # Cost is computed in provider; verify reasonable positive float
    assert isinstance(result.cost, float) and result.cost > 0
