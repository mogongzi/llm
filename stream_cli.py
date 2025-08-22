import sys
import json
import requests

# ANSI color codes
COLOR_PROMPT = "\033[1;32m"  # Bold green
COLOR_MODEL = "\033[36m"     # Cyan
COLOR_RESET = "\033[0m"

URL = "http://127.0.0.1:8000/invoke"

def build_payload(user_input: str):
    """Create the JSON body for the request."""
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [
            {
                "role": "user",
                "content": user_input
            }
        ]
    }

def stream_response(payload):
    """Send request and stream the response."""
    try:
        r = requests.post(URL, json=payload, stream=True)
    except requests.exceptions.RequestException as e:
        print(f"[error] {e}", file=sys.stderr)
        return

    if not r.ok:
        print(f"[HTTP {r.status_code}] {r.text}", file=sys.stderr)
        return

    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue

        data = line[5:].lstrip()
        if data == "[DONE]":
            print()  # newline at end
            break

        try:
            evt = json.loads(data)
        except json.JSONDecodeError:
            continue

        # Show model name when message starts
        if evt.get("type") == "message_start" and "model" in evt.get("message", {}):
            model_name = evt["message"]["model"]
            print(f"\n{COLOR_MODEL}{model_name}{COLOR_RESET}: ", end="", flush=True)

        # Print incremental text
        if evt.get("type") == "content_block_delta":
            delta = evt.get("delta", {})
            if delta.get("type") == "text_delta":
                sys.stdout.write(delta.get("text", ""))
                sys.stdout.flush()

        # End of message
        if evt.get("type") == "message_stop":
            print()  # newline
            break

if __name__ == "__main__":
    try:
        while True:
            user_input = input(f"{COLOR_PROMPT}prompt>{COLOR_RESET} ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"exit", "quit"}:
                print("Bye!")
                break
            payload = build_payload(user_input)
            stream_response(payload)
    except KeyboardInterrupt:
        print("\nBye!")
