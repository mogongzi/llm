from providers.anthropic import map_events


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

