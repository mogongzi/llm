from providers.bedrock import map_events as map_bedrock_events
from providers.azure import map_events as map_azure_events
from render.block_buffered import BlockBuffer


def _replay_to_blocks(mapper, frames):
    b = BlockBuffer()
    blocks = []
    for kind, value in mapper(iter(frames)):
        if kind == "text" and value:
            out = b.feed(value)
            if out:
                blocks.extend(out)
        elif kind == "done":
            rest = b.flush_remaining()
            if rest:
                blocks.append(rest)
            break
    return blocks


def test_golden_bedrock_stream_to_blocks():
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

    blocks = _replay_to_blocks(map_bedrock_events, frames)

    assert blocks == [
        "Intro line 1\nline 2\n\n",
        "```python\nprint('hi')\n```\n",
        "Final para.\n\n",
    ]


def test_golden_azure_stream_to_blocks():
    frames = [
        '{"id":"x","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"role":"assistant","content":"Intro line 1\\n"},"finish_reason":null}]}',
        '{"id":"y","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"line 2\\n\\n"},"finish_reason":null}]}',
        '{"id":"z1","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"```python\\n"},"finish_reason":null}]}',
        '{"id":"z2","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"print(\\"hi\\")\\n"},"finish_reason":null}]}',
        '{"id":"z3","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"```\\n"},"finish_reason":null}]}',
        '{"id":"w","object":"chat.completion.chunk","model":"gpt-5","choices":[{"index":0,"delta":{"content":"Final para.\\n\\n"},"finish_reason":"stop"}]}',
        '{"id":"w2","object":"chat.completion.chunk","model":"gpt-5","choices":[],"usage":{"completion_tokens":20,"prompt_tokens":10,"total_tokens":30}}',
    ]

    blocks = _replay_to_blocks(map_azure_events, frames)

    assert blocks == [
        "Intro line 1\nline 2\n\n",
        "```python\nprint(\"hi\")\n```\n",
        "Final para.\n\n",
    ]

