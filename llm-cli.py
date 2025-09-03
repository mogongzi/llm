#!/usr/bin/env python3
"""
llm-cli: Streaming Markdown renderer for LLM SSE endpoints

Features
- True streaming with live Markdown + syntax highlighting (Rich)
- Stable Scroll back via a small live tail window (no duplicate frames / missing chars)
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
import json
import os
import signal
from dataclasses import dataclass
from typing import Iterator, List, Optional
from urllib.parse import urlparse, urlunparse

import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.text import Text

from sse_client import iter_sse_lines
from providers import get_provider
from render.markdown_live import MarkdownStream

# ---------------- Configuration ----------------
DEFAULT_URL = "http://127.0.0.1:8000/invoke"
COLOR_MODEL = "cyan"
PROMPT_STYLE = "bold green"

console = Console(soft_wrap=True)
_ABORT = False

# ---------------- SSE helpers ----------------

def iter_sse_lines_response(resp) -> Iterator[str]:
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

def stream_and_render(
    url: str,
    payload: dict,
    *,
    mapper,
    live_window: int = 6,
    use_mock: bool = False,
    user_text: str = "",
    timeout: float = 60.0,
    mock_file: Optional[str] = None,
    show_rule: bool = True,
) -> str:
    """Stream SSE and render incrementally.

    When use_mock=True, perform a GET to an SSE /mock endpoint and pass the prompt via ?text=...
    Otherwise, POST JSON to the LLM provider.
    """
    ms = MarkdownStream(live_window=live_window)
    buf: List[str] = []
    model_name: Optional[str] = None

    global _ABORT
    _ABORT = False
    try:
        params = {}
        if use_mock and mock_file:
            params["file"] = mock_file
        method = "GET" if use_mock else "POST"
        for kind, value in mapper(
            iter_sse_lines(
                url,
                method=method,
                json=(None if use_mock else payload),
                params=(params or None),
                timeout=timeout,
            )
        ):
            if _ABORT:
                break
            if kind == "model":
                model_name = value or model_name
                if show_rule and model_name:
                    console.rule(f"[bold {COLOR_MODEL}]{model_name}")
            elif kind == "text":
                buf.append(value or "")
                ms.update("".join(buf), final=False)
            elif kind == "done":
                break
    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
    finally:
        ms.update("".join(buf), final=True)
        if _ABORT:
            console.print("[dim]Aborted[/dim]")
    return "".join(buf)


# ---------------- CLI / REPL ----------------

def repl(
    url: str,
    live_window: int,
    *,
    use_mock: bool,
    timeout: float,
    mock_file: Optional[str],
    show_rule: bool,
    provider,
    model: Optional[str],
    max_tokens: int,
) -> int:
    console.rule("llm-cli • Streaming Markdown")
    console.print(Text("Type 'exit' or 'quit' to leave.", style="dim"))

    # Minimal in-memory conversation history
    history: List[dict] = []

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

        # Conversation: append user message and send full history
        history.append({"role": "user", "content": user})
        payload = provider.build_payload(history, model=model, max_tokens=max_tokens)
        reply_text = stream_and_render(
            url,
            payload,
            mapper=provider.map_events,
            live_window=live_window,
            use_mock=use_mock,
            user_text=user,
            timeout=timeout,
            mock_file=mock_file,
            show_rule=show_rule,
        )
        # Append assistant reply to history
        history.append({"role": "assistant", "content": reply_text})


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-cli", description="Stream LLM responses as live-rendered Markdown")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Endpoint URL (default {DEFAULT_URL})")
    parser.add_argument("--provider", default=os.getenv("LLM_PROVIDER", "bedrock"), choices=["bedrock", "azure"], help="Provider adapter to use (default: bedrock)")
    parser.add_argument("--model", help="Model name to send to provider (e.g., gpt-4o, claude-3)")
    parser.add_argument("--max-tokens", type=int, default=4096, help="Max tokens for provider payload (default 4096)")
    parser.add_argument("--mock", action="store_true", help="Use /mock endpoint (GET) instead of POST /invoke")
    parser.add_argument("--mock-file", help="Mock data file to stream (maps to /mock?file=...)")
    parser.add_argument("--live-window", type=int, default=6, help="Lines to repaint live (default 6)")
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds (default 60)")
    parser.add_argument("--no-rule", action="store_true", help="Do not print the model rule header")
    args = parser.parse_args(argv)

    # Signals: SIGINT/SIGTERM abort current stream; SIGQUIT exits.
    def _sigint(_sig, _frm):
        global _ABORT
        _ABORT = True
    def _sigterm(_sig, _frm):
        global _ABORT
        _ABORT = True
    def _sigquit(_sig, _frm):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGINT, _sigint)
        signal.signal(signal.SIGTERM, _sigterm)
        signal.signal(signal.SIGQUIT, _sigquit)
    except Exception:
        pass

    endpoint = args.url or os.getenv("LLM_URL", DEFAULT_URL)
    provider = get_provider(args.provider)
    if args.mock:
        endpoint = to_mock_url(endpoint)

    return repl(
        endpoint,
        args.live_window,
        use_mock=args.mock,
        timeout=args.timeout,
        mock_file=args.mock_file,
        show_rule=not args.no_rule,
        provider=provider,
        model=args.model,
        max_tokens=args.max_tokens,
    )


if __name__ == "__main__":
    raise SystemExit(main())
