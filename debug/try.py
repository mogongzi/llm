#!/usr/bin/env python3
"""
LLM CLI — streaming with **block-buffered** Markdown
- Streams tokens but prints ONLY completed blocks (paragraphs / fenced code)
- Avoids mid-line ANSI slicing → no missing characters
- Auto-scrolls naturally; keeps clean scrollback
- One model-name rule; no extra separators
- Abort: press 'q' (or Cmd+\\ / Ctrl+\\ for SIGQUIT)

Requirements:
    pip install rich requests

Usage:
    python llm_cli.py --url http://127.0.0.1:8000/invoke
"""
from __future__ import annotations

import argparse
import json
import os
import select
import signal
import sys
import termios
import tty
from contextlib import contextmanager
from typing import Optional

import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
from rich.text import Text

DEFAULT_URL = "http://127.0.0.1:8000/invoke"
COLOR_PROMPT = "bold green"
COLOR_MODEL = "cyan"

console = Console(soft_wrap=True)
_abort = False

from render.block_buffered import BlockBuffer


@contextmanager
def raw_mode(file):
    if not file.isatty():
        yield
        return
    old_attrs = termios.tcgetattr(file.fileno())
    try:
        tty.setcbreak(file.fileno())
        yield
    finally:
        termios.tcsetattr(file.fileno(), termios.TCSADRAIN, old_attrs)


def check_for_q(timeout: float = 0.0) -> bool:
    if not sys.stdin.isatty():
        return False
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        ch = os.read(sys.stdin.fileno(), 1)
        if ch in (b"q", b"Q"):
            return True
    return False


def build_payload(user_input: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [{"role": "user", "content": user_input}],
    }


def _pretty_http_error(resp: requests.Response) -> None:
    try:
        payload = resp.json()
        msg = json.dumps(payload, indent=2)
    except Exception:
        msg = resp.text
    console.print(f"[bold red]HTTP {resp.status_code}[/bold red]\n\n{msg}")


def _event_iter_lines(resp: requests.Response):
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if raw.startswith("data:"):
            yield raw[5:].lstrip()
        else:
            yield raw


def _flush(block: str) -> None:
    if block:
        console.print(Markdown(block))


def stream_response(url: str, payload: dict) -> Optional[str]:
    global _abort
    _abort = False
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as r:
            if not r.ok:
                _pretty_http_error(r)
                return None

            model_name: Optional[str] = None
            buf = BlockBuffer()

            with raw_mode(sys.stdin):
                for data in _event_iter_lines(r):
                    if _abort or check_for_q(0):
                        console.print("\n[red]Aborted[/red]")
                        break
                    if data == "[DONE]":
                        break
                    try:
                        evt = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    etype = evt.get("type")
                    if etype == "message_start" and isinstance(evt.get("message"), dict):
                        model_name = evt["message"].get("model") or model_name
                        if model_name:
                            console.rule(f"[bold {COLOR_MODEL}]{model_name}")

                    if etype == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            for block in buf.feed(delta.get("text", "")):
                                _flush(block)

                    # Try to flush completed blocks from 'pending'
                    if etype == "message_stop":
                        break

            # Flush whatever remains (partial paragraph/last line)
            rest = buf.flush_remaining()
            if rest:
                _flush(rest)
            return None

    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
        return None


def interactive_loop(url: str) -> None:
    console.rule("LLM CLI • Live Markdown")
    console.print(Text("Type 'exit' or 'quit' to leave. Press 'q' during stream, or Cmd+\\ (Mac)/Ctrl+\\ to abort.", style="dim"))

    while True:
        try:
            user_input = Prompt.ask(Text("prompt>", style=COLOR_PROMPT)).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            return

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            console.print("[dim]Bye![/dim]")
            return

        payload = build_payload(user_input)
        stream_response(url, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream LLM responses and render Markdown by completed blocks.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Inference endpoint (default: {DEFAULT_URL})")
    args = parser.parse_args(argv)

    try:
        interactive_loop(args.url)
        return 0
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
