#!/usr/bin/env python3
"""
LLM CLI — streaming with **block-buffered** Markdown (provider-aware)
- Streams tokens but prints ONLY completed blocks (paragraphs / fenced code)
- Avoids mid-line ANSI slicing → no missing characters
- Auto-scrolls naturally; keeps clean scroll back
- One model-name rule; no extra separators
- Abort: press 'Esc' (or Cmd+\\ / Ctrl+\\ for SIGQUIT)

Requirements:
    pip install rich requests

Usage:
    python debug/try.py --url http://127.0.0.1:8000/invoke --provider bedrock
"""
from __future__ import annotations

import argparse
import json
import os
import select
import sys
import termios
import tty
import threading
import queue
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.markdown import Markdown
from rich.prompt import Prompt
import sys
sys.path.append('..')
from simple_pt_input import get_multiline_input
from rich.text import Text
from render.block_buffered import BlockBuffer
from providers import get_provider

DEFAULT_URL = "http://127.0.0.1:8000/invoke"
COLOR_PROMPT = "bold green"
COLOR_MODEL = "cyan"

console = Console(soft_wrap=True)
_abort = False

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


def check_for_esc(timeout: float = 0.0) -> bool:
    if not sys.stdin.isatty():
        return False
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        ch = os.read(sys.stdin.fileno(), 1)
        if ch == b"\x1b":  # ESC
            return True
    return False


def build_payload(provider, user_input: str, *, model: Optional[str] = None) -> dict:
    messages = [{"role": "user", "content": user_input}]
    # Keep a modest default for responsiveness in this debug CLI
    return provider.build_payload(messages, model=model, max_tokens=2048)


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


class _SSEReader(threading.Thread):
    def __init__(self, resp: requests.Response, out: "queue.Queue[str]", stop: threading.Event):
        super().__init__(daemon=True)
        self.resp = resp
        self.out = out
        self.stop = stop

    def run(self):
        try:
            for line in _event_iter_lines(self.resp):
                if self.stop.is_set():
                    break
                try:
                    self.out.put(line, timeout=0.1)
                except Exception:
                    break
        except Exception:
            pass
        finally:
            try:
                self.resp.close()
            except Exception:
                pass


def stream_response(url: str, provider, payload: dict) -> Optional[str]:
    global _abort
    _abort = False
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as r:
            if not r.ok:
                _pretty_http_error(r)
                return None

            model_name: Optional[str] = None
            buf = BlockBuffer()

            stop = threading.Event()
            q: "queue.Queue[str]" = queue.Queue(maxsize=1000)
            reader = _SSEReader(r, q, stop)
            reader.start()

            def _iter_from_queue():
                global _abort
                while True:
                    # non-blocking abort on Esc
                    if _abort or check_for_esc(0.05):
                        _abort = True
                        stop.set()
                        try:
                            r.close()
                        except Exception:
                            pass
                        return
                    try:
                        item = q.get(timeout=0.05)
                    except queue.Empty:
                        if not reader.is_alive():
                            return
                        continue
                    if item:
                        yield item

            with raw_mode(sys.stdin):
                for kind, value in provider.map_events(_iter_from_queue()):
                    if _abort:
                        break
                    if kind == "model":
                        model_name = value or model_name
                        if model_name:
                            console.rule(f"[bold {COLOR_MODEL}]{model_name}")
                    elif kind == "text":
                        for block in buf.feed(value or ""):
                            _flush(block)
                    elif kind == "done":
                        break

            # Flush whatever remains (partial paragraph/last line)
            rest = buf.flush_remaining()
            if rest:
                _flush(rest)
            if _abort:
                console.print("\n[red]Aborted[/red]")
            return None

    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
        return None


def interactive_loop(url: str, provider, model: Optional[str]) -> None:
    console.rule("LLM CLI • Live Markdown")
    console.print(Text("Type 'exit' or 'quit' to leave. Ctrl+J for new line, Enter to submit. Press Esc during stream, or Cmd+\\\\ (Mac)/Ctrl+\\\\ to abort.", style="dim"))

    while True:
        try:
            user_input = get_multiline_input(console, COLOR_PROMPT)
            if user_input is None:
                console.print("[dim]Bye![/dim]")
                return
            user_input = user_input.strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            return

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            console.print("[dim]Bye![/dim]")
            return

        payload = build_payload(provider, user_input, model=model)
        stream_response(url, provider, payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Stream LLM responses and render Markdown by completed blocks.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Inference endpoint (default: {DEFAULT_URL})")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "bedrock"), choices=["bedrock", "azure"], help="Provider adapter to use (default: bedrock)")
    parser.add_argument("--model", help="Optional model name to send to provider")
    args = parser.parse_args(argv)

    try:
        provider = get_provider(args.provider)
        interactive_loop(args.url, provider, args.model)
        return 0
    except KeyboardInterrupt:
        console.print("\n[dim]Bye![/dim]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
