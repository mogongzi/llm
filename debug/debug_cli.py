### python3 debug_cli.py --raw "generate hello world in python" | python3 richify.py
### python3 debug_cli.py --http "generate hello world in python"
### https://github.com/day50-dev/Streamdown python3 debug_cli.py --raw "how to calculate mse in java" | sd
### python3 debug_cli.py --raw "generate hello world in python" | bat --paging=never --style=plain --language=markdown
### python3 debug_cli.py --raw "write a simple nerual network by numpy" | rich - --markdown --force-terminal

import sys
import json
import requests

URL = "http://127.0.0.1:8000/invoke"


def build_payload(user_input: str):
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 65536,
        "messages": [
            {
                "role": "user",
                "content": user_input,
            }
        ],
    }


def stream_response(payload, raw=False, http=False):
    try:
        with requests.post(URL, json=payload, stream=True) as r:
            if not r.ok:
                print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
                return 1

            if http:
                # Print the raw SSE HTTP response line by line
                for line in r.iter_lines(decode_unicode=True):
                    if line:
                        print(line)
                return 0

            # Otherwise process as SSE
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue

                data = line[5:].lstrip()
                if data == "[DONE]":
                    break

                try:
                    evt = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if evt.get("type") == "content_block_delta":
                    delta = evt.get("delta", {})
                    if delta.get("type") == "text_delta":
                        text = delta.get("text", "")
                        if text:
                            if raw:
                                sys.stdout.write(text)
                            else:
                                sys.stdout.write(text)
                            sys.stdout.flush()

                if evt.get("type") == "message_stop":
                    break

    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1

    finally:
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python raw-cli.py [--raw|--http] \"your prompt here\"", file=sys.stderr)
        sys.exit(2)

    raw = False
    http = False
    args = []

    for arg in sys.argv[1:]:
        if arg == "--raw":
            raw = True
        elif arg == "--http":
            http = True
        else:
            args.append(arg)

    user_input = " ".join(args).strip()
    if not user_input:
        print("Error: empty prompt", file=sys.stderr)
        sys.exit(2)

    payload = build_payload(user_input)
    code = stream_response(payload, raw=raw, http=http)
    sys.exit(code)
