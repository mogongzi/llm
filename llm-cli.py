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
from tools.definitions import AVAILABLE_TOOLS
from tools.executor import ToolExecutor

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
    tool_executor: Optional[ToolExecutor] = None,
) -> Tuple[str, int, float, List[dict]]:
    """Stream SSE and render incrementally.

    When use_mock=True, perform a GET to an SSE /mock endpoint and pass the prompt via ?text=...
    Otherwise, POST JSON to the LLM provider.
    """
    ms = MarkdownStream(live_window=live_window)
    buf: List[str] = []
    model_name: Optional[str] = None
    
    # Tool call state
    current_tool = None
    tool_input_buffer = ""
    tool_calls_made = []  # Collect all tool calls in this turn
    
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
                elif kind == "tool_start":
                    # Tool use starting - store tool info
                    ms.stop_waiting()
                    if tool_executor and value:
                        import json
                        try:
                            # Store current tool info and initialize input buffer
                            current_tool = json.loads(value)
                            tool_input_buffer = ""
                            console.print(f"[yellow]🔧 Using {current_tool.get('name')} tool...[/yellow]")
                        except json.JSONDecodeError:
                            console.print(f"[red]Error: Invalid tool start format[/red]")
                elif kind == "tool_input_delta":
                    # Accumulate streaming tool input
                    if value:
                        tool_input_buffer += value
                elif kind == "tool_ready":
                    # Tool input complete - execute the tool and store result
                    if tool_executor and current_tool:
                        import json
                        try:
                            # Parse the complete tool input (default to empty dict if no input was streamed)
                            tool_input = json.loads(tool_input_buffer) if tool_input_buffer else {}
                            tool_name = current_tool.get("name")
                            tool_id = current_tool.get("id")
                            
                            # Execute the tool
                            result = tool_executor.execute_tool(tool_name, tool_input)
                            
                            # Display tool result to user
                            if "error" in result:
                                console.print(f"[red]Tool error: {result['error']}[/red]")
                                tool_result_content = result['content']
                            else:
                                console.print(f"[green]✓ {result['content']}[/green]")
                                tool_result_content = result['content']
                            
                            # Store the complete tool call for sending back to Claude
                            tool_calls_made.append({
                                "tool_call": {
                                    "id": tool_id,
                                    "name": tool_name,
                                    "input": tool_input
                                },
                                "result": tool_result_content
                            })
                            
                        except json.JSONDecodeError:
                            console.print(f"[red]Error: Invalid tool input JSON: {tool_input_buffer}[/red]")
                        finally:
                            # Clean up for next tool
                            current_tool = None
                            tool_input_buffer = ""
                elif kind == "tokens":
                    # Parse token info: "tokens|input_tokens|output_tokens|cost"
                    if value and "|" in value:
                        parts = value.split("|")
                        if len(parts) >= 4:
                            total_tokens = int(parts[0]) if parts[0].isdigit() else 0
                            cost = float(parts[3]) if parts[3] else 0.0
                            return "".join(buf), total_tokens, cost, tool_calls_made
                    # Fallback for old format
                    tokens = int(value) if value and value.isdigit() else 0
                    return "".join(buf), tokens, 0.0, tool_calls_made
                elif kind == "done":
                    break
    except RequestException as e:
        console.print(f"[red]Network error[/red]: {e}")
        # Try to get more details from the response
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_text = e.response.text
                console.print(f"[red]Response body[/red]: {error_text}")
            except:
                console.print(f"[red]Status code[/red]: {e.response.status_code}")
    except Exception as e:
        console.print(f"[red]Unexpected error[/red]: {e}")
        import traceback
        console.print(f"[red]Details[/red]: {traceback.format_exc()}")
    finally:
        ms.update("".join(buf), final=True)
        if _ABORT:
            console.print("[dim]Aborted[/dim]")
    return "".join(buf), 0, 0.0, tool_calls_made


# ---------------- Tool Result Handling ----------------

def format_tool_messages(tool_calls_made: List[dict]) -> List[dict]:
    """
    Format tool calls and results into Anthropic API message format.
    
    Args:
        tool_calls_made: List of tool calls with results
        
    Returns:
        List of properly formatted messages for the conversation
    """
    if not tool_calls_made:
        return []
    
    messages = []
    
    # Create assistant message with tool calls
    tool_use_blocks = []
    for tool_data in tool_calls_made:
        tool_call = tool_data["tool_call"]
        tool_use_blocks.append({
            "type": "tool_use",
            "id": tool_call["id"], 
            "name": tool_call["name"],
            "input": tool_call["input"]
        })
    
    messages.append({
        "role": "assistant",
        "content": tool_use_blocks
    })
    
    # Create user message with tool results  
    tool_result_blocks = []
    for tool_data in tool_calls_made:
        tool_call = tool_data["tool_call"]
        result = tool_data["result"]
        tool_result_blocks.append({
            "type": "tool_result",
            "tool_use_id": tool_call["id"],
            "content": result
        })
    
    messages.append({
        "role": "user", 
        "content": tool_result_blocks
    })
    
    return messages

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
    tools_enabled = False  # Track tools mode state
    
    # Initialize tool executor
    tool_executor = ToolExecutor()

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
            user, use_thinking, thinking_mode, tools_enabled = get_multiline_input(console, PROMPT_STYLE, token_display, thinking_mode, user_history, tools_enabled)
            if user == "__EXIT__":
                console.print("[dim]Bye![/dim]")
                return 0
            if user is None:
                continue  # Command executed or empty input
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            return 0
        if user.lower() in {"exit", "quit"}:
            console.print("[dim]Bye![/dim]")
            return 0

        # Conversation: append user message and send full history
        history.append({"role": "user", "content": user})
        
        # Clean up history - remove any empty assistant messages that could cause API errors
        cleaned_history = []
        for msg in history:
            if msg["role"] == "assistant":
                # Handle both string and list content types
                content = msg["content"]
                if isinstance(content, str) and not content.strip():
                    continue  # Skip empty assistant messages
                elif isinstance(content, list) and not content:
                    continue  # Skip empty list content
            cleaned_history.append(msg)
        
        # Only pass tools if enabled
        tools_param = AVAILABLE_TOOLS if tools_enabled else None
        payload = provider.build_payload(cleaned_history, model=model, max_tokens=max_tokens, thinking=use_thinking, tools=tools_param)
        reply_text, tokens_used, cost_used, tool_calls_made = stream_and_render(
            url,
            payload,
            mapper=provider.map_events,
            live_window=live_window,
            use_mock=use_mock,
            timeout=timeout,
            mock_file=mock_file,
            show_rule=show_rule,
            tool_executor=tool_executor,
        )
        # Update token and cost tracking
        if tokens_used > 0:
            total_tokens_used += tokens_used
        if cost_used > 0:
            total_cost += cost_used

        # Handle tool calls if any were made
        if tool_calls_made:
            # Add tool call messages to history
            tool_messages = format_tool_messages(tool_calls_made)
            history.extend(tool_messages)
            
            # Send tool results back to Claude to get final response
            console.print("[dim]Getting Claude's response to tool results...[/dim]")
            
            # Make follow-up request with tool results
            followup_payload = provider.build_payload(history, model=model, max_tokens=max_tokens, thinking=use_thinking, tools=tools_param)
            followup_reply, followup_tokens, followup_cost, _ = stream_and_render(
                url,
                followup_payload, 
                mapper=provider.map_events,
                live_window=live_window,
                use_mock=use_mock,
                timeout=timeout,
                mock_file=mock_file,
                show_rule=False,  # Don't show rule again
                tool_executor=tool_executor,
            )
            
            # Update tracking for follow-up request
            if followup_tokens > 0:
                total_tokens_used += followup_tokens
            if followup_cost > 0:
                total_cost += followup_cost
            
            # Add Claude's final response to history
            if isinstance(followup_reply, str) and followup_reply.strip():
                history.append({"role": "assistant", "content": followup_reply})
        else:
            # Regular response without tools
            if isinstance(reply_text, str) and reply_text.strip():
                history.append({"role": "assistant", "content": reply_text})
            else:
                # This should rarely happen now
                console.print("[dim]Note: Empty response received[/dim]")


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
