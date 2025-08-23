#!/usr/bin/env python3
"""
LLM CLI with live Markdown rendering using Rich + abort support.
- Streams SSE-like tokens from /invoke
- Renders markdown live
- Auto-scrolls during streaming and prints final output at end
- Abort hotkeys / signals:
    • Ctrl+C (SIGINT) — abort current request or exit when idle
    • q / Q (pressed while streaming) — abort current request
    • SIGTERM / SIGHUP / SIGQUIT — graceful abort (e.g., Terminal close)

Note: Command+Q is handled by the macOS app (Terminal/iTerm) and is not
forwarded to child processes. We can’t capture it reliably. This script
catches the OS signals typically sent on app close and provides a
single-key 'q' abort while streaming.

Requirements:
    pip install rich requests

Usage:
    python llm_cli.py --url http://127.0.0.1:8000/invoke
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import termios
import tty
from contextlib import contextmanager
from select import select
from threading import Event
from typing import Optional

import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.align import Align

DEFAULT_URL = "http://127.0.0.1:8000/invoke"

COLOR_PROMPT = "bold green"
COLOR_MODEL = "cyan"

console = Console()
ABORT = Event()


# ---------- Signals & keyboard helpers ----------

def _set_abort_handlers() -> None:
    def handler(signum, frame):
        ABORT.set()
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP, signal.SIGQUIT):
        try:
            signal.signal(sig, handler)
        except Exception:
            pass  # not all signals exist on all platforms


@contextmanager
def raw_key_capture(enabled: bool = True):
    """Put stdin into raw mode so single-key presses (e.g., 'q') are readable.
    Restores terminal settings on exit. No-op if stdin is not a TTY or disabled.
    """
    if not enabled or not sys.stdin.isatty():
        yield
        return
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)  # cbreak = read per-char; does not disable Ctrl+C
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _poll_abort_key(timeout: float = 0.0) -> bool:
    """Return True if user pressed 'q'/'Q'. Non-blocking when timeout=0."""
    if not sys.stdin.isatty():
        return False
    rlist, _, _ = select([sys.stdin], [], [], timeout)
    if rlist:
        ch = os.read(sys.stdin.fileno(), 1)
        if ch in (b"q", b"Q"):
            ABORT.set()
            return True
    return ABORT.is_set()


# ---------- Request / streaming ----------
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
    console.print(Panel.fit(
        Text.from_markup(
            f"[bold red]HTTP {resp.status_code}[/bold red]\n\n{msg}"
        ),
        title="Request Failed",
        border_style="red",
    ))


def _event_iter_lines(resp: requests.Response):
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if raw.startswith("data:"):
            yield raw[5:].lstrip()
        else:
            yield raw


def stream_response(url: str, payload: dict) -> Optional[str]:
    ABORT.clear()
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as r:
            if not r.ok:
                _pretty_http_error(r)
                return None

            md_text = ""
            model_name: Optional[str] = None

            renderable = Panel(Markdown(""), title="[dim]Awaiting tokens…[/dim]", border_style="blue")
            with raw_key_capture(True), Live(renderable, console=console, refresh_per_second=24, transient=False, auto_refresh=True) as live:
                for data in _event_iter_lines(r):
                    if ABORT.is_set() or _poll_abort_key(0):
                        console.print("\n[bold red]⏹ Aborted[/bold red]")
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

                    if etype == "content_block_delta":
                        delta = evt.get("delta", {})
                        if delta.get("type") == "text_delta":
                            md_text += delta.get("text", "")

                    title_txt = (f"[bold {COLOR_MODEL}]{model_name}[/bold {COLOR_MODEL}]" if model_name else "[dim]Streaming…[/dim]")

                    renderable = Panel(
                        Align.left(Markdown(md_text)),
                        title=title_txt,
                        border_style="cyan",
                        expand=True,
                    )
                    live.update(renderable, refresh=True)

                    if etype == "message_stop":
                        break

            # Always finalize with the last known content and place cursor at bottom
            if md_text:
                console.print(Align.left(Markdown(md_text)))
            return md_text

    except RequestException as e:
        if not ABORT.is_set():
            console.print(Panel.fit(str(e), title="[red]Network error[/red]", border_style="red"), justify="left")
        return None


# ---------- UI Loop ----------
def interactive_loop(url: str) -> None:
    _set_abort_handlers()
    console.rule("LLM CLI • Live Markdown (press [bold]q[/bold] to abort)")
    console.print(Text("Type 'exit' or 'quit' to leave. Ctrl+C also exits when idle.", style="dim"))

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
