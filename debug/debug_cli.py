"""
Minimal SSE debug client

Examples:
  python -m debug.debug_cli --provider="bedrock" --http "hello world"
  python3 debug/debug_cli.py --http "hello world"
  python3 debug/debug_cli.py --provider azure --url http://127.0.0.1:8000/invoke "hi"
"""

import sys
import os
import argparse
import requests

DEFAULT_URL = "http://127.0.0.1:8000/invoke"

from providers import get_provider


def build_payload(provider, user_input: str, *, model: str | None = None, max_tokens: int | None = None):
    messages = [{"role": "user", "content": user_input}]
    kwargs = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return provider.build_payload(messages, model=model, **kwargs)


def stream_response(url: str, provider, payload, raw=False, http=False):
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as r:
            if not r.ok:
                print(f"HTTP {r.status_code}: {r.text}", file=sys.stderr)
                return 1

            if http:
                # Print the raw SSE HTTP response line by line
                for line in r.iter_lines(decode_unicode=True):
                    if line:
                        print(line)
                return 0

            # Otherwise process as SSE using the provider adapter
            def iter_sse(r):
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data:"):
                        yield line[5:].lstrip()
                    else:
                        yield line

            for kind, value in provider.map_events(iter_sse(r)):
                if kind == "text" and value:
                    sys.stdout.write(value)
                    sys.stdout.flush()
                elif kind == "done":
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Minimal SSE debug client")
    p.add_argument("prompt", nargs="+", help="Prompt text to send")
    p.add_argument("--url", default=DEFAULT_URL, help=f"Endpoint URL (default: {DEFAULT_URL})")
    p.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "bedrock"), choices=["bedrock", "azure"], help="Provider adapter to use")
    p.add_argument("--model", help="Optional model name for the provider")
    p.add_argument("--http", action="store_true", help="Print raw HTTP lines (SSE)")
    p.add_argument("--raw", action="store_true", help="Alias for plain text output (default)")
    p.add_argument("--max-tokens", type=int, help="Optional max_tokens to include in payload")
    args = p.parse_args(argv)

    provider = get_provider(args.provider)
    user_input = " ".join(args.prompt).strip()
    if not user_input:
        print("Error: empty prompt", file=sys.stderr)
        return 2
    payload = build_payload(provider, user_input, model=args.model, max_tokens=args.max_tokens)
    return stream_response(args.url, provider, payload, raw=args.raw, http=args.http)


if __name__ == "__main__":
    raise SystemExit(main())
