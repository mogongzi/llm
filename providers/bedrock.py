from __future__ import annotations

import json
from typing import Dict, Iterator, Optional, Tuple, List


Event = Tuple[str, Optional[str]]  # ("model"|"text"|"thinking"|"done"|"tokens", value)


def build_payload(
    messages: List[dict], *, model: Optional[str] = None, max_tokens: int = 4096, temperature: Optional[float] = None, thinking: bool = False, thinking_tokens: int = 1024, **_: dict
) -> dict:
    """Construct Bedrock/Anthropic-style chat payload.

    Notes:
    - Do not include a 'model' key by default; many Bedrock endpoints select model via path/config.
    - Keep structure aligned with existing behavior for backward compatibility.
    """
    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if thinking:
        payload["thinking"] = {
            "type": "enabled",
            "budget_tokens": thinking_tokens
        }

    return payload


def map_events(lines: Iterator[str]) -> Iterator[Event]:
    """Map Bedrock/Anthropic JSON SSE frames to a simple event interface.

    Emits:
    - ("model", model_name) on message_start
    - ("thinking", text_chunk) on content_block_delta.thinking_delta
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
            if delta.get("type") == "thinking_delta":
                thinking = delta.get("thinking", "")
                if thinking:
                    yield ("thinking", thinking)
            elif delta.get("type") == "text_delta":
                text = delta.get("text", "")
                if text:
                    yield ("text", text)
        elif e_type == "message_stop":
            # Extract token usage and cost if available
            usage = evt.get("amazon-bedrock-invocationMetrics") or evt.get("usage")
            if usage:
                input_tokens = usage.get("inputTokenCount", 0) or usage.get("input_tokens", 0)
                output_tokens = usage.get("outputTokenCount", 0) or usage.get("output_tokens", 0)
                total_tokens = input_tokens + output_tokens
                if total_tokens > 0:
                    # Calculate cost (Claude 3.5 Sonnet pricing: $3/1M input, $15/1M output)
                    input_cost = (input_tokens / 1000000) * 3.0
                    output_cost = (output_tokens / 1000000) * 15.0
                    total_cost = input_cost + output_cost

                    # Format: "tokens|input_tokens|output_tokens|cost"
                    token_info = f"{total_tokens}|{input_tokens}|{output_tokens}|{total_cost:.6f}"
                    yield ("tokens", token_info)
            yield ("done", None)
            break
