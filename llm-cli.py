#!/usr/bin/env python3
"""
llm-cli: Streaming Markdown renderer for LLM SSE endpoints

Features
- True streaming with live Markdown + syntax highlighting (Rich)
- Stable Scroll back via a small live tail window (no duplicate frames / missing chars)
- Model name printed once as a rule header
- Natural auto-scrolling; output preserved after stream ends
- Abort gracefully with 'Esc' during stream or Ctrl+C

Requirements
    pip install rich requests

Notes
- The client expects an SSE-like stream with lines prefixed "data:" and JSON events
  that include `content_block_delta` + `text_delta` for text chunks.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
from contextlib import contextmanager
from typing import Iterator, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse
from requests.exceptions import RequestException
from rich.console import Console
from rich.text import Text
from sse_client import iter_sse_lines
from providers import get_provider
from render.markdown_live import MarkdownStream
from simple_pt_input import get_multiline_input

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


# ---------------- Input helpers ----------------

@contextmanager
def _raw_mode(file):
    """Best-effort cbreak mode so single-key presses are readable without Enter.

    No-ops on non-TTYs or platforms without termios/tty.
    """
    try:
        import termios  # type: ignore
        import tty  # type: ignore
    except Exception:
        # Unsupported platform or import error; proceed without raw mode
        yield
        return

    try:
        if not hasattr(file, "isatty") or not file.isatty():
            yield
            return
        fd = file.fileno()
        old_attrs = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            yield
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
    except Exception:
        # Fallback if anything goes wrong
        yield


def _esc_pressed(timeout: float = 0.0) -> bool:
    """Return True if ESC was pressed within timeout seconds.

    Uses select+os.read in a non-blocking way; returns False on non-TTY or unsupported platforms.
    """
    try:
        import select
        import os as _os
    except Exception:
        return False
    if not hasattr(sys.stdin, "isatty") or not sys.stdin.isatty():
        return False
    try:
        rlist, _, _ = select.select([sys.stdin], [], [], timeout)
        if rlist:
            ch = _os.read(sys.stdin.fileno(), 1)
            return ch == b"\x1b"  # ESC
    except Exception:
        return False
    return False


# ---------------- Client core ----------------

def stream_and_render(
    url: str,
    payload: dict,
    *,
    mapper,
    live_window: int = 6,
    use_mock: bool = False,
    timeout: float = 30.0,
    mock_file: Optional[str] = None,
    show_rule: bool = True,
) -> Tuple[str, int, float]:
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
        # Pass through optional mock delay from env var set by argparse
        mock_delay = os.getenv("LLM_MOCK_DELAY_MS")
        if use_mock and mock_delay:
            params["delay_ms"] = mock_delay
        method = "GET" if use_mock else "POST"
        with _raw_mode(sys.stdin):
            # Show a distinct waiting indicator until first content arrives
            ms.start_waiting("Waiting for response…")
            for kind, value in mapper(
                iter_sse_lines(
                    url,
                    method=method,
                    json=(None if use_mock else payload),
                    params=(params or None),
                    timeout=timeout,
                )
            ):
                if _ABORT or _esc_pressed(0.0):
                    _ABORT = True
                    break
                if kind == "model":
                    # First signal received; hide waiting indicator
                    ms.stop_waiting()
                    model_name = value or model_name
                    if show_rule and model_name:
                        console.rule(f"[bold {COLOR_MODEL}]{model_name}")
                elif kind == "thinking":
                    # First thinking token hides waiting indicator
                    ms.stop_waiting()
                    ms.add_thinking(value or "")
                elif kind == "text":
                    # First token will also hide the waiting indicator if still visible
                    ms.stop_waiting()
                    buf.append(value or "")
                    ms.add_response(value or "")
                elif kind == "tokens":
                    # Parse token info: "tokens|input_tokens|output_tokens|cost"
                    if value and "|" in value:
                        parts = value.split("|")
                        if len(parts) >= 4:
                            total_tokens = int(parts[0]) if parts[0].isdigit() else 0
                            cost = float(parts[3]) if parts[3] else 0.0
                            return "".join(buf), total_tokens, cost
                    # Fallback for old format
                    tokens = int(value) if value and value.isdigit() else 0
                    return "".join(buf), tokens, 0.0
                elif kind == "done":
                    break
    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
    finally:
        ms.update("".join(buf), final=True)
        if _ABORT:
            console.print("[dim]Aborted[/dim]")
    return "".join(buf), 0, 0.0


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
    console.rule("Talk 2 LLM • AI Core")
    console.print(Text("Type 'exit' or 'quit' to leave. Press Esc during stream, or Ctrl+C.", style="dim"))

    # Minimal in-memory conversation history
    history: List[dict] = []
    total_tokens_used = 0
    total_cost = 0.0
    max_tokens_limit = 200000  # Default limit, can be made configurable
    thinking_mode = False  # Track thinking mode state

    while True:
        try:
            # Format token info for display
            if total_tokens_used > 0:
                percentage = (total_tokens_used / max_tokens_limit) * 100
                if total_tokens_used >= 1000:
                    token_part = f"{total_tokens_used/1000:.1f}k/{max_tokens_limit/1000:.0f}k ({percentage:.1f}%)"
                else:
                    token_part = f"{total_tokens_used}/{max_tokens_limit} ({percentage:.1f}%)"
                
                # Format cost display
                if total_cost >= 0.01:
                    cost_part = f"${total_cost:.3f}"
                elif total_cost >= 0.001:
                    cost_part = f"${total_cost:.4f}"
                else:
                    cost_part = f"${total_cost:.6f}"
                
                token_display = f"{token_part} {cost_part}"
            else:
                token_display = None

            # Extract user messages from conversation history for navigation
            user_history = [msg["content"] for msg in history if msg["role"] == "user"]
            user, use_thinking, thinking_mode = get_multiline_input(console, PROMPT_STYLE, token_display, thinking_mode, user_history)
            if user == "__EXIT__":
                console.print("[dim]Bye![/dim]")
                return 0
            if user is None:
                continue  # Command executed or empty input
            user = user.strip()
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
        payload = provider.build_payload(history, model=model, max_tokens=max_tokens, thinking=use_thinking)
        reply_text, tokens_used, cost_used = stream_and_render(
            url,
            payload,
            mapper=provider.map_events,
            live_window=live_window,
            use_mock=use_mock,
            timeout=timeout,
            mock_file=mock_file,
            show_rule=show_rule,
        )
        # Update token and cost tracking
        if tokens_used > 0:
            total_tokens_used += tokens_used
        if cost_used > 0:
            total_cost += cost_used

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
    parser.add_argument("--mock-delay", type=int, default=0, help="Initial delay in ms before first mock chunk (maps to /mock?delay_ms=...)")
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
        if args.mock_delay and args.mock_delay > 0:
            os.environ["LLM_MOCK_DELAY_MS"] = str(args.mock_delay)

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
