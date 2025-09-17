#!/usr/bin/env python3
"""
Unified LLM Debug Client

Combines functionality from debug_cli.py and try.py:
- Raw HTTP/SSE inspection
- Block-buffered Markdown streaming
- Provider testing with various parameters

Examples:
  python3 -m debug.debug --http "hello world"                    # Raw HTTP lines
  python3 -m debug.debug --raw "hello world"                     # Plain text output
  python3 -m debug.debug --block "hello world"                   # Block-buffered Markdown
  python3 -m debug.debug --live "hello world"                    # Test live rendering
  python3 -m debug.debug --interactive --provider azure          # Interactive mode
  python3 -m debug.debug --mock --mock-file mock.dat "test"      # Mock with custom file
"""

import sys
import os
import argparse
import json
import select
import shutil
import termios
import tty
import threading
import queue
from contextlib import contextmanager
from typing import Optional

import requests
from requests.exceptions import RequestException
from rich.console import Console
from rich.markdown import Markdown
from rich.text import Text

# Add parent directory to path for imports
sys.path.append('..')
from util.simple_pt_input import get_multiline_input
from render.block_buffered import BlockBuffer
from providers import get_provider
from streaming_client import StreamingClient

DEFAULT_URL = "http://127.0.0.1:8000/invoke"
COLOR_PROMPT = "bold green"
COLOR_MODEL = "cyan"

# Detect terminal width with smart fallback
def get_terminal_width():
    """Get terminal width with intelligent fallback."""
    try:
        # Try shutil first
        term_size = shutil.get_terminal_size()
        width = term_size.columns

        # If detection returns default (80) or very small, use reasonable fallback
        if width <= 80:
            # Try environment variables
            import os
            env_cols = os.environ.get('COLUMNS')
            if env_cols and env_cols.isdigit():
                width = int(env_cols)
            else:
                # Fallback to reasonable width for modern terminals
                width = 120

        # Be much more conservative to account for font rendering differences
        # Reduce by 25% to provide larger buffer for visual vs character width mismatches
        width = int(width * 0.75)

        return max(width, 100)  # Ensure minimum reasonable width
    except Exception:
        return 120  # Safe fallback

console = Console(soft_wrap=True, force_terminal=True, width=get_terminal_width())
_abort = False


@contextmanager
def raw_mode(file):
    """Context manager for raw terminal mode."""
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
    """Check if ESC key was pressed."""
    if not sys.stdin.isatty():
        return False
    rlist, _, _ = select.select([sys.stdin], [], [], timeout)
    if rlist:
        ch = os.read(sys.stdin.fileno(), 1)
        if ch == b"\x1b":  # ESC
            return True
    return False


def build_payload(provider, user_input: str, *, model: Optional[str] = None, max_tokens: Optional[int] = None) -> dict:
    """Build provider payload with optional parameters."""
    messages = [{"role": "user", "content": user_input}]
    kwargs = {}
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    else:
        # Default for debug client responsiveness
        kwargs["max_tokens"] = 2048
    return provider.build_payload(messages, model=model, **kwargs)


def build_mock_payload(mock_file: Optional[str], mock_delay: Optional[int]) -> dict:
    """Build payload for mock proxy requests."""
    payload: dict[str, object] = {}
    if mock_file:
        payload["file"] = mock_file
    if mock_delay is not None:
        payload["delay_ms"] = mock_delay
    return payload


def pretty_http_error(resp: requests.Response) -> None:
    """Pretty print HTTP error responses."""
    try:
        payload = resp.json()
        msg = json.dumps(payload, indent=2)
    except Exception:
        msg = resp.text
    console.print(f"[bold red]HTTP {resp.status_code}[/bold red]\n\n{msg}")


def event_iter_lines(resp: requests.Response):
    """Parse SSE event lines from HTTP response."""
    for raw in resp.iter_lines(decode_unicode=True):
        if not raw:
            continue
        if raw.startswith("data:"):
            yield raw[5:].lstrip()
        else:
            yield raw


def flush_markdown_block(block: str) -> None:
    """Flush completed markdown block to console."""
    if block:
        console.print(Markdown(block))


class SSEReader(threading.Thread):
    """Background thread to read SSE events."""
    def __init__(self, resp: requests.Response, out: "queue.Queue[str]", stop: threading.Event):
        super().__init__(daemon=True)
        self.resp = resp
        self.out = out
        self.stop = stop

    def run(self):
        try:
            for line in event_iter_lines(self.resp):
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


def stream_response_http(url: str, provider, payload: dict, use_mock: bool = False,
                        mock_file: Optional[str] = None, mock_delay: Optional[int] = None,
                        timeout: float = 60.0) -> int:
    """Stream response showing raw HTTP lines (--http mode)."""
    try:
        if use_mock:
            payload = build_mock_payload(mock_file, mock_delay) or {}

        response = requests.post(url, json=payload, stream=True, timeout=timeout)

        with response:
            if not response.ok:
                print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
                return 1

            # Print raw HTTP lines
            for line in response.iter_lines(decode_unicode=True):
                if line:
                    print(line)
            return 0

    except RequestException as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1


def stream_response_raw(url: str, provider, payload: dict, use_mock: bool = False,
                       mock_file: Optional[str] = None, mock_delay: Optional[int] = None,
                       timeout: float = 60.0) -> int:
    """Stream response as plain text (--raw mode)."""
    try:
        if use_mock:
            payload = build_mock_payload(mock_file, mock_delay) or {}
        response = requests.post(url, json=payload, stream=True, timeout=timeout)

        with response:
            if not response.ok:
                print(f"HTTP {response.status_code}: {response.text}", file=sys.stderr)
                return 1

            # Process as SSE and output plain text
            def iter_sse(r):
                for line in r.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    if line.startswith("data:"):
                        yield line[5:].lstrip()
                    else:
                        yield line

            for kind, value in provider.map_events(iter_sse(response)):
                if kind == "text" and value:
                    sys.stdout.write(value)
                    sys.stdout.flush()
                elif kind == "done":
                    break

    except RequestException as e:
        print(f"Request error: {e}", file=sys.stderr)
        return 1
    finally:
        try:
            sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception:
            pass

    return 0


def stream_response_block(url: str, provider, payload: dict, use_mock: bool = False,
                         mock_file: Optional[str] = None, mock_delay: Optional[int] = None,
                         timeout: float = 60.0,
                         live_window: int = 6) -> Optional[str]:
    """Stream response with block-buffered Markdown rendering (--block mode)."""
    global _abort
    _abort = False

    try:
        if use_mock:
            payload = build_mock_payload(mock_file, mock_delay) or {}

        response = requests.post(url, json=payload, stream=True, timeout=timeout)

        with response:
            if not response.ok:
                pretty_http_error(response)
                return None

            model_name: Optional[str] = None
            buf = BlockBuffer()

            stop = threading.Event()
            q: "queue.Queue[str]" = queue.Queue(maxsize=1000)
            reader = SSEReader(response, q, stop)
            reader.start()

            def iter_from_queue():
                global _abort
                while True:
                    # Check for abort on ESC key
                    if _abort or check_for_esc(0.05):
                        _abort = True
                        stop.set()
                        try:
                            response.close()
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
                for kind, value in provider.map_events(iter_from_queue()):
                    if _abort:
                        break
                    if kind == "model":
                        model_name = value or model_name
                        if model_name:
                            console.rule(f"[bold {COLOR_MODEL}]{model_name}")
                    elif kind == "text":
                        for block in buf.feed(value or ""):
                            flush_markdown_block(block)
                    elif kind == "done":
                        break

            # Flush remaining content
            rest = buf.flush_remaining()
            if rest:
                flush_markdown_block(rest)
            if _abort:
                console.print("\n[red]Aborted[/red]")
            return None

    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
        return None


def stream_response_live(url: str, provider, payload: dict, use_mock: bool = False,
                        mock_file: Optional[str] = None, mock_delay: Optional[int] = None,
                        timeout: float = 60.0,
                        live_window: int = 6) -> int:
    """Stream response with live rendering using StreamingClient (--live mode)."""
    console.print(f"[dim]Testing live rendering with StreamingClient...[/dim]")

    try:
        # Create StreamingClient
        client = StreamingClient()

        # Exact parity with llm-cli: always use StreamingClient.stream_with_live_rendering
        # The only difference in mock mode is the payload content and the URL (/mock).
        effective_payload = (
            build_mock_payload(mock_file, mock_delay) if use_mock else payload
        ) or {}

        result = client.stream_with_live_rendering(
            url=url,
            payload=effective_payload,
            mapper=provider.map_events,
            console=console,
            use_thinking=False,
            provider_name=provider.__name__.split('.')[-1] if hasattr(provider, '__name__') else "bedrock",
            show_model_name=True,
            live_window=live_window,
        )

        # Unified final result reporting
        if result.aborted:
            console.print(f"\n[dim]Stream aborted[/dim]")
        elif result.error:
            console.print(f"\n[red]Error: {result.error}[/red]")
        else:
            console.print(f"\n[dim]Final: {result.tokens} tokens, cost ${result.cost:.4f}[/dim]")
            if result.tool_calls:
                console.print(f"[dim]Tools used: {len(result.tool_calls)}[/dim]")

        return 0

    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
        return 1
    except Exception as e:
        console.print(f"[red]Unexpected error[/red]: {e}")
        return 1


def interactive_mode(url: str, provider, model: Optional[str], use_mock: bool = False,
                    mock_file: Optional[str] = None, mock_delay: Optional[int] = None,
                    timeout: float = 60.0,
                    live_window: int = 6) -> None:
    """Interactive mode with block-buffered Markdown rendering."""
    console.rule("LLM Debug CLI • Interactive Mode")
    console.print(Text("Type 'exit' or 'quit' to leave. Ctrl+J for new line, Enter to submit. Press Esc during stream.", style="dim"))

    while True:
        try:
            user_input, _, _, _ = get_multiline_input(console, COLOR_PROMPT)
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
        stream_response_block(
            url,
            provider,
            payload,
            use_mock,
            mock_file,
            mock_delay,
            timeout,
            live_window,
        )


def to_mock_url(url: str) -> str:
    """Convert invoke URL to mock URL."""
    return url.replace("/invoke", "/mock")


def main(argv: list[str] | None = None) -> int:
    """Main entry point with unified argument parsing."""
    parser = argparse.ArgumentParser(description="Unified LLM debug client with multiple output modes")

    # Core connection settings
    parser.add_argument("prompt", nargs="*", help="Prompt text to send (not used in interactive mode)")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Endpoint URL (default: {DEFAULT_URL})")
    parser.add_argument("--provider", default="bedrock", choices=["bedrock", "azure"],
                       help="Provider adapter to use (default: bedrock)")

    # Output mode selection (mutually exclusive)
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--http", action="store_true", help="Print raw HTTP/SSE lines")
    mode_group.add_argument("--raw", action="store_true", help="Plain text output (no formatting)")
    mode_group.add_argument("--block", action="store_true", help="Block-buffered Markdown rendering")
    mode_group.add_argument("--interactive", action="store_true", help="Interactive mode with Markdown")
    mode_group.add_argument("--live", action="store_true", help="Test live rendering with StreamingClient")

    # Model and token settings
    parser.add_argument("--model", help="Model name to send to provider")
    parser.add_argument("--max-tokens", type=int, help="Max tokens for provider payload")

    # Mock/testing settings
    parser.add_argument("--mock", action="store_true", help="Use mock endpoint instead of real provider")
    parser.add_argument("--mock-file", help="Mock data file to stream")
    parser.add_argument("--mock-delay", type=int, default=0, help="Mock delay in milliseconds")

    # Debug/tuning settings
    parser.add_argument("--timeout", type=float, default=60.0, help="HTTP timeout in seconds")
    parser.add_argument("--live-window", type=int, default=6, help="Live rendering window size")

    args = parser.parse_args(argv)

    # Validate arguments
    if not args.interactive and not args.prompt:
        print("Error: prompt required unless using --interactive mode", file=sys.stderr)
        return 2

    # Set up mock delay environment variable if specified
    if args.mock_delay and args.mock_delay > 0:
        os.environ["LLM_MOCK_DELAY_MS"] = str(args.mock_delay)

    # Get provider and build URL
    provider = get_provider(args.provider)
    url = to_mock_url(args.url) if args.mock else args.url

    # Handle interactive mode
    if args.interactive:
        interactive_mode(
            url,
            provider,
            args.model,
            args.mock,
            args.mock_file,
            args.mock_delay,
            args.timeout,
            args.live_window,
        )
        return 0

    # Handle non-interactive modes
    user_input = " ".join(args.prompt).strip()
    if not user_input:
        print("Error: empty prompt", file=sys.stderr)
        return 2

    payload = build_payload(provider, user_input, model=args.model, max_tokens=args.max_tokens)

    # Route to appropriate output handler
    if args.http:
        return stream_response_http(
            url,
            provider,
            payload,
            args.mock,
            args.mock_file,
            args.mock_delay,
            args.timeout,
        )
    elif args.raw:
        return stream_response_raw(
            url,
            provider,
            payload,
            args.mock,
            args.mock_file,
            args.mock_delay,
            args.timeout,
        )
    elif args.block:
        stream_response_block(
            url,
            provider,
            payload,
            args.mock,
            args.mock_file,
            args.mock_delay,
            args.timeout,
            args.live_window,
        )
        return 0
    elif args.live:
        return stream_response_live(
            url,
            provider,
            payload,
            args.mock,
            args.mock_file,
            args.mock_delay,
            args.timeout,
            args.live_window,
        )
    else:
        # Default to raw mode if no mode specified
        return stream_response_raw(
            url,
            provider,
            payload,
            args.mock,
            args.mock_file,
            args.mock_delay,
            args.timeout,
        )


if __name__ == "__main__":
    raise SystemExit(main())
