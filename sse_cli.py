#!/usr/bin/env python3
"""
LLM CLI with live Markdown rendering using the Rich library.
- Streams Server-Sent Events (SSE-style) from a local /invoke endpoint
- Renders incremental markdown in-place (Live) as content arrives
- Shows model name as a simple separator line once known
- Auto-scrolls in real-time (no overflow dots)
- Supports aborting current stream with:
    - Pressing 'q' during streaming
    - Cmd+\\ (Mac) or Ctrl+\\ (others) signal

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
from rich.live import Live
from rich.prompt import Prompt
from rich.text import Text

DEFAULT_URL = "http://127.0.0.1:8000/invoke"

COLOR_PROMPT = "bold green"
COLOR_MODEL = "cyan"

console = Console(force_terminal=True, force_interactive=True, highlight=False, soft_wrap=True)
_abort = False


# ---------------- Key capture helpers ----------------
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


# ---------------- Signal handlers ----------------
def _signal_handler(sig, frame):
    global _abort
    _abort = True
    console.print("\n[red]Aborted by signal[/red]")


signal.signal(signal.SIGQUIT, _signal_handler)


# ---------------- HTTP helpers ----------------
def build_payload(user_input: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [
            {"role": "user", "content": user_input}
        ],
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


# ---------------- Streaming ----------------
def stream_response(url: str, payload: dict) -> Optional[str]:
    global _abort
    _abort = False
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as r:
            if not r.ok:
                _pretty_http_error(r)
                return None

            md_text = ""
            model_name: Optional[str] = None

            with raw_mode(sys.stdin), Live(console=console, refresh_per_second=24, transient=False, auto_refresh=True, vertical_overflow="visible") as live:
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
                            md_text += delta.get("text", "")

                    live.update(Markdown(md_text), refresh=True)

                    if etype == "message_stop":
                        break

            if not _abort:
                console.print(Markdown(md_text))
            return md_text

    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
        return None


# ---------------- Interactive loop ----------------
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
    parser = argparse.ArgumentParser(description="Stream LLM responses and render markdown live in the console.")
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
