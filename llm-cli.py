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
from typing import List, Optional, Tuple
from requests.exceptions import RequestException, ReadTimeout, ConnectTimeout
from rich.console import Console
from rich.text import Text
from util.sse_client import iter_sse_lines
from providers import get_provider
from render.markdown_live import MarkdownStream
from util.simple_pt_input import get_multiline_input
from tools.definitions import AVAILABLE_TOOLS
from tools.executor import ToolExecutor

# Import from new modular structure
from util.url_helpers import to_mock_url
from util.input_helpers import _raw_mode, _esc_pressed, should_exit_from_input
from util.command_helpers import handle_special_commands
from chat.conversation import ConversationManager
from chat.usage_tracker import UsageTracker
from chat.session import ChatSession
from chat.tool_workflow import process_tool_execution
from context.context_manager import ContextManager
from util.path_browser import PathBrowser
from rag.manager import RAGManager

# ---------------- Configuration ----------------
DEFAULT_URL = "http://127.0.0.1:8000/invoke"
COLOR_MODEL = "cyan"
PROMPT_STYLE = "bold green"

console = Console(soft_wrap=True)
_ABORT = False



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
    use_thinking: bool = False,
    provider_name: str = "bedrock",
) -> Tuple[str, int, float, List[dict]]:
    """Stream SSE and render incrementally with live Markdown rendering.

    Handles streaming response from LLM provider, processes tool calls, and renders
    content in real-time with ESC abort support.

    Returns: (response_text, token_count, cost, tool_calls_made)
    """
    ms = MarkdownStream(live_window=live_window)
    buf: List[str] = []  # Accumulate response text
    model_name: Optional[str] = None

    # Tool call state tracking
    current_tool = None  # Currently streaming tool info
    tool_input_buffer = ""  # Accumulate tool input parameters
    tool_calls_made = []  # Collect all tool calls in this turn

    global _ABORT
    _ABORT = False
    try:
        # Setup request parameters for mock vs real provider
        params = {}
        if use_mock and mock_file:
            params["file"] = mock_file
        # Pass through optional mock delay from env var set by argparse
        mock_delay = os.getenv("LLM_MOCK_DELAY_MS")
        if use_mock and mock_delay:
            params["delay_ms"] = mock_delay
        method = "GET" if use_mock else "POST"
        # Enable raw terminal mode for ESC detection
        try:
            with _raw_mode(sys.stdin):
                # Show waiting indicator until first content arrives
                if use_thinking and provider_name == "azure":
                    ms.start_waiting("Thinking…")
                else:
                    ms.start_waiting("Waiting for response…")
                # Stream SSE events and map to structured data
                for kind, value in mapper(
                    iter_sse_lines(
                        url,
                        method=method,
                        json=(None if use_mock else payload),
                        params=(params or None),
                        timeout=timeout,
                    )
                ):
                    # Check for abort conditions (ESC key or signal)
                    if _ABORT or _esc_pressed(0.0):
                        _ABORT = True
                        break
                    if kind == "model":
                        # Model name received - stop waiting and show header
                        ms.stop_waiting()
                        model_name = value or model_name
                        if show_rule and model_name:
                            console.rule(f"[bold {COLOR_MODEL}]{model_name}")
                    elif kind == "thinking":
                        # Thinking content received - render in special thinking mode
                        ms.stop_waiting()
                        ms.add_thinking(value or "")
                    elif kind == "text":
                        # Regular response text - accumulate and render
                        ms.stop_waiting()
                        buf.append(value or "")
                        ms.add_response(value or "")
                    elif kind == "tool_start":
                        # Tool call initiated - parse and store tool metadata
                        ms.stop_waiting()
                        if tool_executor and value:
                            import json
                            try:
                                # Parse tool info (name, id) and reset input buffer
                                current_tool = json.loads(value)
                                tool_input_buffer = ""
                                console.print(f"[yellow]⚙ Using {current_tool.get('name')} tool...[/yellow]")
                            except json.JSONDecodeError:
                                console.print(f"[red]Error: Invalid tool start format[/red]")
                    elif kind == "tool_input_delta":
                        # Streaming tool parameters - accumulate JSON input
                        if value:
                            tool_input_buffer += value
                    elif kind == "tool_ready":
                        # Tool input complete - execute and capture result
                        if tool_executor and current_tool:
                            import json
                            try:
                                # Parse complete tool parameters (fallback to empty dict)
                                tool_input = json.loads(tool_input_buffer) if tool_input_buffer else {}
                                tool_name = current_tool.get("name")
                                tool_id = current_tool.get("id")

                                # Execute the tool with parsed parameters
                                result = tool_executor.execute_tool(tool_name, tool_input)

                                # Display tool result and capture for conversation
                                if "error" in result:
                                    console.print(f"[red]Tool error: {result['error']}[/red]")
                                    tool_result_content = result['content']
                                else:
                                    console.print(f"[green]✓ {result['content']}[/green]")
                                    tool_result_content = result['content']

                                # Store complete tool call data for follow-up request
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
                                # Reset state for next potential tool call
                                current_tool = None
                                tool_input_buffer = ""
                    elif kind == "tokens":
                        # Parse usage statistics: "tokens|input_tokens|output_tokens|cost"
                        if value and "|" in value:
                            parts = value.split("|")
                            if len(parts) >= 4:
                                total_tokens = int(parts[0]) if parts[0].isdigit() else 0
                                cost = float(parts[3]) if parts[3] else 0.0
                                return "".join(buf), total_tokens, cost, tool_calls_made
                        # Fallback for legacy simple token format
                        tokens = int(value) if value and value.isdigit() else 0
                        return "".join(buf), tokens, 0.0, tool_calls_made
                    elif kind == "done":
                        # Stream completed successfully
                        break
        except (ReadTimeout, ConnectTimeout) as e:
            ms.stop_waiting()
            console.print(f"[red]Request timed out[/red]: {e}")
            console.print(f"[dim]Try increasing timeout with --timeout parameter[/dim]")
        except RequestException as e:
            ms.stop_waiting()
            console.print(f"[red]Network error[/red]: {e}")
            # Extract additional error details from HTTP response
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_text = e.response.text
                    console.print(f"[red]Response body[/red]: {error_text}")
                except:
                    console.print(f"[red]Status code[/red]: {e.response.status_code}")
        except Exception as e:
            ms.stop_waiting()
            console.print(f"[red]Unexpected error[/red]: {e}")
            import traceback
            console.print(f"[red]Details[/red]: {traceback.format_exc()}")
    finally:
        # Finalize markdown rendering with accumulated content
        ms.update("".join(buf), final=True)
        if _ABORT:
            console.print("[dim]Aborted[/dim]")
    # Return accumulated text, no usage stats on error
    return "".join(buf), 0, 0.0, tool_calls_made


# ---------------- Tool Result Handling ----------------

def format_tool_messages(tool_calls_made: List[dict]) -> List[dict]:
    """Format tool calls and results into Anthropic API message format.

    Converts executed tool calls into proper conversation messages that Claude
    can understand in follow-up requests.

    Args:
        tool_calls_made: List of tool calls with results

    Returns:
        List of assistant+user message pairs for tool use conversation
    """
    if not tool_calls_made:
        return []

    messages = []

    # Create assistant message containing tool_use blocks
    tool_use_blocks = []
    for tool_data in tool_calls_made:
        tool_call = tool_data["tool_call"]
        # Each tool use needs id, name, and input parameters
        tool_use_blocks.append({
            "type": "tool_use",
            "id": tool_call["id"],
            "name": tool_call["name"],
            "input": tool_call["input"]
        })

    # Assistant message: Claude's tool use requests
    messages.append({
        "role": "assistant",
        "content": tool_use_blocks
    })

    # User message: Results from executing the requested tools
    tool_result_blocks = []
    for tool_data in tool_calls_made:
        tool_call = tool_data["tool_call"]
        result = tool_data["result"]
        # Each result references the original tool_use by ID
        tool_result_blocks.append({
            "type": "tool_result",
            "tool_use_id": tool_call["id"],
            "content": result
        })

    # User message: Tool results for Claude to process
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
    """Interactive chat loop with conversation history and tool support.

    Simplified main loop that delegates responsibilities to specialized classes.

    Returns: Exit code (0 for success)
    """
    console.rule("Talk 2 LLM • AI Core")
    console.print(Text("Type '/help' for commands or '/exit' to leave. Press Esc during stream, or Ctrl+C.", style="dim"))

    # Initialize components with clear separation of concerns
    conversation = ConversationManager()
    usage = UsageTracker(max_tokens_limit=200000)
    tool_executor = ToolExecutor()
    context_manager = ContextManager()
    rag_manager = RAGManager()
    path_browser = PathBrowser()
    # Extract provider name from module name (e.g., "providers.azure" -> "azure")
    provider_name = provider.__name__.split('.')[-1] if hasattr(provider, '__name__') else "bedrock"
    
    session = ChatSession(
        url=url,
        provider=provider,
        model=model,
        max_tokens=max_tokens,
        live_window=live_window,
        use_mock=use_mock,
        timeout=timeout,
        mock_file=mock_file,
        show_rule=show_rule,
        tool_executor=tool_executor,
        context_manager=context_manager,
        rag_manager=rag_manager,
        provider_name=provider_name
    )

    # Track UI state that persists across interactions
    thinking_mode = False
    tools_enabled = False

    while True:
        try:
            # Get user input with usage display and history navigation
            context_status = context_manager.get_status_summary()
            display_string = f"{usage.get_display_string()} • {context_status}"
            user_input, use_thinking, thinking_mode, tools_enabled = get_multiline_input(
                console, PROMPT_STYLE, display_string, thinking_mode,
                conversation.get_user_history(), tools_enabled, context_manager
            )

            # Handle exit conditions
            if should_exit_from_input(user_input):
                console.print("[dim]Bye![/dim]")
                return 0

            # Handle special commands
            if handle_special_commands(user_input, conversation, console, context_manager, path_browser, rag_manager):
                continue

        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            return 0

        # Add user message to conversation
        conversation.add_user_message(user_input)

        # Send message and get response
        reply_text, tokens_used, cost_used, tool_calls_made = session.send_message(
            conversation.get_sanitized_history(), use_thinking, tools_enabled,
            AVAILABLE_TOOLS, stream_and_render
        )

        # Update usage tracking
        usage.update(tokens_used, cost_used)

        # Handle tool execution workflow if tools were called
        if tool_calls_made:
            process_tool_execution(
                tool_calls_made, conversation, session, use_thinking, tools_enabled,
                usage, AVAILABLE_TOOLS, stream_and_render, format_tool_messages
            )
        else:
            # Store regular response (no tools involved)
            conversation.add_assistant_message(reply_text)
            if not reply_text or not reply_text.strip():
                console.print("[dim]Note: Empty response received[/dim]")


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point with argument parsing and signal handling."""
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

    # Setup signal handlers for graceful stream abortion
    def _sigint(_sig, _frm):
        global _ABORT
        _ABORT = True  # Abort current stream but stay in REPL
    def _sigterm(_sig, _frm):
        global _ABORT
        _ABORT = True  # Abort current stream but stay in REPL
    def _sigquit(_sig, _frm):
        raise KeyboardInterrupt  # Exit entire program
    try:
        signal.signal(signal.SIGINT, _sigint)
        signal.signal(signal.SIGTERM, _sigterm)
        signal.signal(signal.SIGQUIT, _sigquit)
    except Exception:
        pass  # Signal setup not supported on platform

    # Resolve endpoint URL from args or environment
    endpoint = args.url or os.getenv("LLM_URL", DEFAULT_URL)
    provider = get_provider(args.provider)
    # Configure mock mode with optional delay
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
