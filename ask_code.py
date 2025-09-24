#!/usr/bin/env python3
"""
Rails Code Analysis CLI using ReAct Agent

Dedicated tool for intelligent Rails codebase analysis using AI reasoning.
Features advanced input handling, RAG infrastructure, and focused Rails analysis.
"""
import argparse
import signal
from typing import List, Optional
from rich.console import Console
from rich.text import Text
from render.markdown_live import MarkdownStyled

# Import core components from llm-cli.py
from providers import get_provider
from util.simple_pt_input import get_multiline_input
from util.command_helpers import handle_special_commands
from util.input_helpers import should_exit_from_input
from chat.session import ChatSession
from rag.naive.manager import RAGManager
from streaming_client import StreamingClient
from tools.executor import ToolExecutor

# Import ReAct agent
from agents.react_rails_agent import ReactRailsAgent
from agents.agent_tool_executor import AgentToolExecutor

# Configuration
DEFAULT_URL = "http://127.0.0.1:8000/invoke"
PROMPT_STYLE = "bold green"
console = Console()
_ABORT = False


def create_streaming_client():
    """Create and return streaming client."""
    return StreamingClient()


def get_agent_input(console, prompt_style, display_string, thinking_mode, user_history, tools_enabled):
    """
    Input function for ask_code.py with simplified interface.

    Removes /tools indicator since function calling is always enabled for the agent.
    """
    # Import the internal functions we need
    from util.simple_pt_input import _create_key_bindings, _prompt_for_input, _process_user_input

    # Custom display function for Rails agent (no /tools indicator)
    def _display_rails_instructions(token_info: str = None, thinking_mode: bool = False) -> None:
        """Display usage instructions optimized for Rails analysis."""
        base_instructions = "↵ send    Ctrl+J newline"

        # Add thinking mode status
        if thinking_mode:
            thinking_part = "/think reasoning [ON]"
        else:
            thinking_part = "/think reasoning"

        instructions = f"{base_instructions}    {thinking_part}    Esc/Ctrl+C=cancel"

        if token_info:
            # Calculate spacing for right-aligned token info
            terminal_width = 120
            spaces_needed = max(0, terminal_width - len(instructions) - len(f"Tokens: {token_info}"))
            console.print(f"[dim]{instructions}{' ' * spaces_needed}Tokens: {token_info}[/dim]")
        else:
            console.print(f"[dim]{instructions}[/dim]")

    # Show our Rails-specific instructions
    _display_rails_instructions(display_string, thinking_mode)

    # Create key bindings but without tools toggle
    key_bindings = _create_key_bindings(user_history)

    try:
        user_input = _prompt_for_input(key_bindings, user_history, None)

        if not user_input:
            return None, False, thinking_mode, tools_enabled

        # Handle thinking toggle
        if user_input.strip().lower() == "/think":
            thinking_mode = not thinking_mode
            return None, True, thinking_mode, tools_enabled

        # Ignore /tools command since tools are always enabled
        if user_input.strip().lower() == "/tools":
            console.print("[dim]Tools are always enabled for Rails analysis[/dim]")
            return None, False, thinking_mode, tools_enabled

        return user_input, False, thinking_mode, tools_enabled

    except Exception as e:
        console.print(f"[red]Input error: {e}[/red]")
        return None, False, thinking_mode, tools_enabled


def repl(
    url: str,
    *,
    provider,
    project_root: str,
) -> int:
    """
    Interactive Rails code analysis loop with ReAct agent.

    Args:
        url: LLM endpoint URL
        provider: Provider adapter (bedrock/azure)
        project_root: Rails project root directory

    Returns:
        Exit code (0 for success)
    """
    console.rule("Rails Code Analysis • ReAct Agent")
    console.print(Text("Type '/help' for commands or 'exit' to leave. Press Esc during stream, or Ctrl+C.", style="dim"))

    # Initialize components
    rag_manager = RAGManager()
    tool_executor = ToolExecutor()

    # Add usage tracking like llm-cli.py
    from chat.usage_tracker import UsageTracker
    usage = UsageTracker(max_tokens_limit=200000)

    # Extract provider name from module name
    provider_name = provider.__name__.split('.')[-1] if hasattr(provider, '__name__') else "bedrock"

    # Create a streaming client (tool executor will be swapped after agent init)
    streaming_client = create_streaming_client()

    # Create session
    session = ChatSession(
        url=url,
        provider=provider,
        max_tokens=4096,
        timeout=120.0,
        tool_executor=tool_executor,
        rag_manager=rag_manager,
        provider_name=provider_name
    )

    # Assign streaming client to session
    session.streaming_client = streaming_client

    # Initialize ReAct agent
    try:
        react_agent = ReactRailsAgent(project_root=project_root, session=session)
        console.print(f"[green]✓ ReAct Rails Agent initialized[/green]: {project_root}")
        # Show tool summary at startup
        try:
            st = react_agent.get_status()
            tools = st.get("tools_available", [])
            console.print(f"[dim]Tools available ({len(tools)}): {', '.join(sorted(tools))}[/dim]")
        except Exception:
            pass
    except Exception as e:
        console.print(f"[red]Error: Could not initialize ReAct agent: {e}[/red]")
        return 1

    # Wire provider-managed tool calls to the agent's tools
    try:
        agent_executor = AgentToolExecutor(react_agent.tools)
        session.streaming_client = StreamingClient(tool_executor=agent_executor)
    except Exception as e:
        console.print(f"[yellow]Warning: could not attach agent tool executor: {e}[/yellow]")

    # Track UI state
    thinking_mode = False
    tools_enabled = False
    user_history = []

    while True:
        try:
            # Build display string with usage and RAG status
            rag_status = "RAG:on" if rag_manager.enabled else "RAG:off"
            project_name = project_root.split('/')[-1] if project_root else "unknown"
            usage_display = usage.get_display_string()
            display_string = f"{usage_display} • Rails Code Analysis • {project_name} • {rag_status}"

            # Get user input synchronously
            user_input, use_thinking, thinking_mode, tools_enabled = get_agent_input(
                console,
                PROMPT_STYLE,
                display_string,
                thinking_mode,
                user_history,
                tools_enabled,
            )

            # Handle exit conditions
            if should_exit_from_input(user_input):
                console.print("[dim]Bye![/dim]")
                return 0

            # Handle special commands (including /rag)
            if handle_special_commands(user_input, None, console, None, None, rag_manager, react_agent):
                continue

        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Bye![/dim]")
            return 0

        # Add to history if it's a real query
        if user_input and isinstance(user_input, str):
            user_history.append(user_input)

        # Process through ReAct agent
        try:
            console.print("\n[dim]🤖 Agent processing...[/dim]")
            response = react_agent.process_message(user_input)
            # Content was already displayed during streaming - no need to re-render
            console.print()

            # Note: ReAct agent handles its own LLM calls internally
            # Token usage tracking happens within the agent's session
            # For now, show basic usage stats (actual tokens tracked inside ReactRailsAgent)
            console.print(f"[dim]Tokens used: Agent managed • Session: {len(user_history)} queries[/dim]")

        except Exception as e:
            console.print(f"[red]Agent processing error: {e}[/red]")


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entry point with argument parsing and signal handling."""
    parser = argparse.ArgumentParser(
        prog="ask-code",
        description="Rails Code Analysis with ReAct Agent"
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Rails project root directory"
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help=f"Endpoint URL (default {DEFAULT_URL})"
    )
    parser.add_argument(
        "--provider",
        default="bedrock",
        choices=["bedrock", "azure"],
        help="Provider adapter to use (default: bedrock)"
    )
    args = parser.parse_args(argv)

    # Setup signal handlers for graceful stream abortion
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
        pass  # Signal setup not supported on platform

    # Use endpoint URL from args
    endpoint = args.url
    provider = get_provider(args.provider)

    code = repl(
        endpoint,
        provider=provider,
        project_root=args.project,
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
