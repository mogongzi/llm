#!/usr/bin/env python3
"""
llm-cli: Streaming Markdown renderer for LLM SSE endpoints

Features
- True streaming with live Markdown + syntax highlighting (Rich)
- Stable scrollback via a small live tail window (no duplicate frames / missing chars)
- Model name printed once as a rule header
- Natural auto-scrolling; output preserved after stream ends
- Abort gracefully with 'q' during stream or Ctrl+C

Requirements
    pip install rich requests

Notes
- The client expects an SSE-like stream with lines prefixed "data:" and JSON events
  that include `content_block_delta` + `text_delta` for text chunks.
"""
from __future__ import annotations

import argparse
import io
import json
import signal
import time
from dataclasses import dataclass
from typing import Iterator, List, Optional
from urllib.parse import urlparse, urlunparse

import requests
from requests.exceptions import RequestException
from rich import box
from rich.console import Console
from rich.live import Live
from rich.markdown import CodeBlock, Heading, Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

# ---------------- Configuration ----------------
DEFAULT_URL = "http://127.0.0.1:8000/invoke"
COLOR_MODEL = "cyan"
PROMPT_STYLE = "bold green"

console = Console(soft_wrap=True)


# ---------------- Rich customizations ----------------
class _CodeBlockTight(CodeBlock):
    """Code block: syntax highlight, compact left/right padding."""

    def __rich_console__(self, console, options):
        code = str(self.text).rstrip()
        syntax = Syntax(code, self.lexer_name, theme=self.theme, word_wrap=True, padding=(1, 0))
        yield syntax


class _HeadingLeft(Heading):
    """Left-justified headings; H1 inside a bordered panel."""

    def __rich_console__(self, console, options):
        text = self.text
        text.justify = "left"
        if self.tag == "h1":
            yield Panel(text, box=box.HEAVY, style="markdown.h1.border")
        else:
            if self.tag == "h2":
                yield Text("")  # blank line before h2
            yield text


class _MarkdownStyled(Markdown):
    elements = {
        **Markdown.elements,
        "fence": _CodeBlockTight,
        "code_block": _CodeBlockTight,
        "heading_open": _HeadingLeft,
    }


# ---------------- Stable Live Window Streamer ----------------
@dataclass
class MarkdownStream:
    """Render cumulative Markdown with a small live tail window.

    Strategy: render to ANSI each tick; print the stable prefix above a Live
    repaint window (last N lines). This keeps scrollback clean and prevents
    missing characters or duplicate frames.
    """

    live: Optional[Live] = None
    when: float = 0.0
    min_delay: float = 1.0 / 20  # target ~20fps maximum
    live_window: int = 6
    printed: List[str] = None

    def __post_init__(self):
        self.printed = []

    def _render_md_lines(self, text: str) -> List[str]:
        buf = io.StringIO()
        tmp = Console(file=buf, force_terminal=True, soft_wrap=True)
        tmp.print(_MarkdownStyled(text))
        return buf.getvalue().splitlines(keepends=True)

    def _ensure_live(self):
        if not self.live:
            self.live = Live(Text(""), refresh_per_second=1.0 / self.min_delay)
            self.live.start()

    def stop(self):
        if self.live:
            try:
                self.live.update(Text(""))
                self.live.stop()
            except Exception:
                pass
            self.live = None

    def update(self, cumulative_text: str, final: bool = False) -> None:
        self._ensure_live()

        now = time.time()
        if not final and (now - self.when) < self.min_delay:
            return
        self.when = now

        t0 = time.time()
        lines = self._render_md_lines(cumulative_text)
        render_time = time.time() - t0
        self.min_delay = min(max(render_time * 10, 1.0 / 20), 2)

        total = len(lines)
        stable = total if final else max(0, total - self.live_window)

        if final or stable > 0:
            already = len(self.printed)
            need = stable - already
            if need > 0:
                chunk = "".join(lines[already:stable])
                self.live.console.print(Text.from_ansi(chunk))
                self.printed = lines[:stable]

        if final:
            self.stop()
            return

        tail = "".join(lines[stable:])
        self.live.update(Text.from_ansi(tail))


# ---------------- SSE helpers ----------------

def iter_sse_lines(resp) -> Iterator[str]:
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        yield raw[5:].lstrip() if raw.startswith("data:") else raw


# ---------------- URL helpers ----------------

def to_mock_url(u: str) -> str:
    """Rewrite a base URL to its /mock sibling.

    Examples:
      http://host:8000/invoke -> http://host:8000/mock
      http://host:8000 -> http://host:8000/mock
      http://host:8000/anything -> http://host:8000/anything/mock
    """
    p = urlparse(u)
    path = p.path or "/"
    if path.endswith("/mock"):
        new_path = path
    elif path.endswith("/invoke"):
        new_path = path[: -len("/invoke")] + "/mock"
    else:
        new_path = path + ("mock" if path.endswith("/") else "/mock")
    return urlunparse(p._replace(path=new_path, query=""))


# ---------------- Client core ----------------

def build_payload(user_input: str) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": user_input}],
    }


def stream_and_render(url: str, payload: dict, *, live_window: int = 6, use_mock: bool = False, user_text: str = "") -> None:
    """Stream SSE and render incrementally.

    When use_mock=True, perform a GET to an SSE /mock endpoint and pass the prompt via ?text=...
    Otherwise, POST JSON to the LLM provider.
    """
    ms = MarkdownStream(live_window=live_window)
    buf: List[str] = []
    model_name: Optional[str] = None

    try:
        if use_mock:
            req = requests.get(url, params={"text": user_text}, stream=True, timeout=60)
        else:
            req = requests.post(url, json=payload, stream=True, timeout=60)

        with req as r:
            if not r.ok:
                try:
                    err = r.json()
                except Exception:
                    err = {"error": r.text}
                console.print(f"[bold red]HTTP {r.status_code}[/bold red]\n\n{json.dumps(err, indent=2)}")
                return

            for data in iter_sse_lines(r):
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
                        buf.append(delta.get("text", ""))
                        ms.update("".join(buf), final=False)

                if etype == "message_stop":
                    break
    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
    finally:
        ms.update("".join(buf), final=True)


# ---------------- CLI / REPL ----------------

def repl(url: str, live_window: int, *, use_mock: bool) -> int:
    console.rule("llm-cli • Streaming Markdown")
    console.print(Text("Type 'exit' or 'quit' to leave.", style="dim"))

    while True:
        try:
            user = console.input(f"[{PROMPT_STYLE}]prompt>[/] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            return 0
        if not user:
            continue
        if user.lower() in {"exit", "quit"}:
            console.print("[dim]Bye![/dim]")
            return 0

        payload = build_payload(user)
        stream_and_render(url, payload, live_window=live_window, use_mock=use_mock, user_text=user)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-cli", description="Stream LLM responses as live-rendered Markdown")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Endpoint URL (default {DEFAULT_URL})")
    parser.add_argument("--mock", action="store_true", help="Use /mock endpoint (GET ?text=...) instead of POST /invoke")
    parser.add_argument("--live-window", type=int, default=6, help="Lines to repaint live (default 6)")
    args = parser.parse_args(argv)

    # Ctrl+Backslash (SIGQUIT) exits cleanly like Ctrl+C
    def _sigquit(_sig, _frm):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGQUIT, _sigquit)
    except Exception:
        pass

    endpoint = args.url or DEFAULT_URL
    if args.mock:
        endpoint = to_mock_url(endpoint)

    return repl(endpoint, args.live_window, use_mock=args.mock)


if __name__ == "__main__":
    raise SystemExit(main())