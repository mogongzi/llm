"""Command handling utilities for special commands."""

from typing import Optional


def show_help_message(console) -> None:
    """Display help message with all available commands."""
    console.print("\n[bold cyan]Available Commands:[/bold cyan]")
    console.print("  [bold green]/help[/bold green]   - Show this help message")
    console.print("  [bold green]/clear[/bold green]  - Clear conversation history")
    console.print("  [bold green]/exit[/bold green]   - Quit the program")
    console.print()
    console.print("[bold cyan]Keyboard Shortcuts:[/bold cyan]")
    console.print("  [bold yellow]Ctrl+J[/bold yellow]     - Insert new line (in multi-line input)")
    console.print("  [bold yellow]Enter[/bold yellow]      - Send message")
    console.print("  [bold yellow]Esc[/bold yellow]        - Abort current stream")
    console.print("  [bold yellow]Ctrl+C[/bold yellow]     - Quit program")
    console.print()
    console.print("[bold cyan]Features:[/bold cyan]")
    console.print("  • Live Markdown rendering with syntax highlighting")
    console.print("  • Tool calling support (toggle with tools indicator)")
    console.print("  • Thinking mode support (toggle with thinking indicator)")
    console.print("  • Token usage and cost tracking")
    console.print("  • Input history navigation")
    console.print()


def handle_special_commands(user_input: Optional[str], conversation, console=None) -> bool:
    """Handle special commands like /help, /clear and /exit. Returns True if command was handled."""
    if user_input == "__CLEAR__":
        conversation.clear_history()
        return True
    if user_input and user_input.strip().lower() == "/clear":
        conversation.clear_history()
        return True
    if user_input and user_input.strip().lower() == "/help":
        if console:
            show_help_message(console)
        return True
    if user_input is None:
        return True  # Command handled or empty input
    return False