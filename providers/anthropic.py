from __future__ import annotations

import json
from typing import Dict, Iterator, Optional, Tuple, List


Event = Tuple[str, Optional[str]]  # ("model"|"text"|"done", value)


def build_payload(
    messages: List[dict], *, model: Optional[str] = None, max_tokens: int = 4096, temperature: Optional[float] = None, **_: dict
) -> dict:
    """Construct Anthropic-style chat payload.

    Notes:
    - Do not include a 'model' key by default; many Anthropic endpoints select model via path/config.
    - Keep structure aligned with existing behavior for backward compatibility.
    """
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }


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
