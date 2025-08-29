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
import re
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

# Regex for fenced code start/end at beginning of a line
OPEN_FENCE_RE = re.compile(r"(?m)^(?P<fence>`{3,}|~{3,})[ \t]*[^\n]*\n")
# Closing fence must use same char (` or ~) with length >= opening
CLOSE_FENCE_FMT = r"(?m)^(?:%s{3,})\s*$\n"


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

            # Accumulate tokens here, but only print finished blocks
            pending = ""
            in_code = False
            close_re: Optional[re.Pattern[str]] = None

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
                            pending += delta.get("text", "")

                    # Try to flush completed blocks from 'pending'
                    while True:
                        if in_code:
                            assert close_re is not None
                            m = close_re.search(pending)
                            if not m:
                                break  # wait for the rest of the code block
                            end = m.end()
                            _flush(pending[:end])
                            pending = pending[end:]
                            in_code = False
                            close_re = None
                            # continue scanning for more blocks in pending
                            continue
                        else:
                            # If we see a paragraph boundary before a fence, flush the paragraph
                            para_idx = pending.find("\n\n")
                            m_open = OPEN_FENCE_RE.search(pending)

                            if para_idx != -1 and (m_open is None or para_idx < m_open.start()):
                                end = para_idx + 2
                                _flush(pending[:end])
                                pending = pending[end:]
                                continue

                            # If we see a fence, possibly flush text before it, then enter code mode
                            if m_open:
                                start = m_open.start()
                                if start > 0:
                                    _flush(pending[:start])
                                    pending = pending[start:]
                                    # update indices relative to new pending
                                    m_open = OPEN_FENCE_RE.match(pending)
                                    assert m_open

                                fence = m_open.group("fence")[0]  # '`' or '~'
                                close_re = re.compile(CLOSE_FENCE_FMT % re.escape(fence))
                                in_code = True
                                # now check if the fence closes within current pending
                                m_close = close_re.search(pending[m_open.end():])
                                if m_close:
                                    end = m_open.end() + m_close.end()
                                    _flush(pending[:end])
                                    pending = pending[end:]
                                    in_code = False
                                    close_re = None
                                    continue
                                else:
                                    break  # need more text to finish the code block

                            # No paragraph end, no fence start → wait for more
                            break

                    if etype == "message_stop":
                        break

            # Flush whatever remains (partial paragraph/last line)
            if pending:
                _flush(pending)
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
