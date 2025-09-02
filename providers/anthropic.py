from __future__ import annotations

import json
from typing import Dict, Iterator, Optional, Tuple


Event = Tuple[str, Optional[str]]  # ("model"|"text"|"done", value)


def map_events(lines: Iterator[str]) -> Iterator[Event]:
    """Map Anthropic-style JSON SSE frames to a simple event interface.

    Emits:
    - ("model", model_name) on message_start
    - ("text", text_chunk) on content_block_delta.text_delta
    - ("done", None) on message_stop or [DONE]
    """
    for data in lines:
        if data == "[DONE]":
            yield ("done", None)
            break
        try:
            evt: Dict = json.loads(data)
        except json.JSONDecodeError:
            continue
        etype = evt.get("type")
        if etype == "message_start" and isinstance(evt.get("message"), dict):
            model = evt["message"].get("model")
            if model:
                yield ("model", model)
        elif etype == "content_block_delta":
            delta = evt.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield ("text", text)
        elif etype == "message_stop":
            yield ("done", None)
            break

