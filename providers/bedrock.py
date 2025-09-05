from __future__ import annotations

import json
from typing import Dict, Iterator, Optional, Tuple, List


Event = Tuple[str, Optional[str]]  # ("model"|"text"|"done"|"tokens", value)


def build_payload(
    messages: List[dict], *, model: Optional[str] = None, max_tokens: int = 4096, temperature: Optional[float] = None, **_: dict
) -> dict:
    """Construct Bedrock/Anthropic-style chat payload.

    Notes:
    - Do not include a 'model' key by default; many Bedrock endpoints select model via path/config.
    - Keep structure aligned with existing behavior for backward compatibility.
    """
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }


def map_events(lines: Iterator[str]) -> Iterator[Event]:
    """Map Bedrock/Anthropic JSON SSE frames to a simple event interface.

    Emits:
    - ("model", model_name) on message_start
    - ("text", text_chunk) on content_block_delta.text_delta
    - ("tokens", token_count_str) on message_stop with usage info
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
        e_type = evt.get("type")
        if e_type == "message_start" and isinstance(evt.get("message"), dict):
            model = evt["message"].get("model")
            if model:
                yield ("model", model)
        elif e_type == "content_block_delta":
            delta = evt.get("delta", {})
            if delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield ("text", text)
        elif e_type == "message_stop":
            # Extract token usage if available
            usage = evt.get("amazon-bedrock-invocationMetrics") or evt.get("usage")
            if usage:
                input_tokens = usage.get("inputTokenCount", 0) or usage.get("input_tokens", 0)
                output_tokens = usage.get("outputTokenCount", 0) or usage.get("output_tokens", 0)
                total_tokens = input_tokens + output_tokens
                if total_tokens > 0:
                    yield ("tokens", str(total_tokens))
            yield ("done", None)
            break
