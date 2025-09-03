from __future__ import annotations

import json
from typing import Dict, Iterator, List, Optional, Tuple


Event = Tuple[str, Optional[str]]  # ("model"|"text"|"done", value)


def build_payload(
    messages: List[dict], *, model: Optional[str] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None, **_: dict
) -> dict:
    """Construct an OpenAI Chat Completions streaming payload.

    Requires `model`. Includes `stream: true`.
    """
    body: Dict = {
        "messages": messages,
        "stream": True,
    }
    if model is not None:
        body["model"] = model
    if max_tokens is not None:
        body["max_completion_tokens"] = max_tokens
    if temperature is not None:
        body["temperature"] = temperature
    return body


def map_events(lines: Iterator[str]) -> Iterator[Event]:
    """Map OpenAI Chat Completions SSE chunks to unified events.

    Emits:
    - ("model", name) on first chunk carrying `model`
    - ("text", delta) for each `choices[0].delta.content` string
    - ("done", None) on `[DONE]` or when a `finish_reason` is observed
    """
    sent_model = False
    for data in lines:
        if data == "[DONE]":
            yield ("done", None)
            break
        try:
            evt: Dict = json.loads(data)
        except json.JSONDecodeError:
            continue

        model = evt.get("model")
        if not sent_model and isinstance(model, str) and model:
            yield ("model", model)
            sent_model = True

        choices = evt.get("choices") or []
        for ch in choices:
            delta = ch.get("delta") or {}
            content = delta.get("content")
            if isinstance(content, str) and content:
                yield ("text", content)

        # Signal completion if provider indicates finish
        for ch in choices:
            if ch.get("finish_reason") is not None:
                yield ("done", None)
                return
