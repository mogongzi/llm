"""Command handling utilities for special commands."""

from typing import Optional
from context.context_manager import ContextManager
from util.path_browser import PathBrowser


def show_help_message(console) -> None:
    """Display help message with all available commands."""
    console.print("\n[bold cyan]Available Commands:[/bold cyan]")
    console.print("  [bold green]/help[/bold green]         - Show this help message")
    console.print("  [bold green]/clear[/bold green]        - Clear conversation history")
    console.print("  [bold green]/context[/bold green] <file> - Add file context to conversation")
    console.print("  [bold green]/context clear[/bold green] - Remove all file context")
    console.print("  [bold green]/context list[/bold green]  - Show active context files")
    console.print("  [bold green]/exit[/bold green]         - Quit the program")
    console.print()
    console.print("[bold cyan]@ File Browser Commands:[/bold cyan]")
    console.print("  [bold yellow]@[/bold yellow]            - Start file path and use dropdown")
    console.print("  [bold yellow]@/path/[/bold yellow]      - Navigate into folder (dropdown)")
    console.print("  [bold yellow]@~/[/bold yellow]          - Browse home (dropdown)")
    console.print("  [bold yellow]@file.txt[/bold yellow]    - Add file to context")
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
    console.print("  • File context injection for enhanced conversations")
    console.print("  • Interactive file browser with @ commands")
    console.print("  • Token usage and cost tracking")
    console.print("  • Input history navigation")
    console.print()


def handle_special_commands(user_input: Optional[str], conversation, console=None, context_manager: Optional[ContextManager] = None, path_browser: Optional[PathBrowser] = None) -> bool:
    """Handle special commands like /help, /clear, /context, @ and /exit. Returns True if command was handled."""
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
    
    # Handle @ commands for file browsing
    if user_input and user_input.startswith("__AT_COMMAND__"):
        at_command = user_input[14:]  # Remove "__AT_COMMAND__" prefix
        return handle_at_command(at_command, context_manager, path_browser, console)
    
    # Handle context commands
    if user_input and user_input.strip().lower().startswith("/context"):
        return handle_context_command(user_input.strip(), context_manager, console)
    
    if user_input is None:
        return True  # Command handled or empty input
    return False


def handle_context_command(user_input: str, context_manager: Optional[ContextManager], console) -> bool:
    """Handle /context commands for file context management.
    
    Args:
        user_input: The full command input
        context_manager: Context manager instance
        console: Rich console for output
        
    Returns:
        True if command was handled
    """
    if not context_manager:
        if console:
            console.print("[red]Context manager not available[/red]")
        return True
    
    # Parse command parts
    parts = user_input.split(None, 2)  # Split into max 3 parts: /context, subcommand, argument
    
    if len(parts) == 1:
        # Just "/context" - show status
        contexts = context_manager.list_contexts()
        if not contexts:
            console.print("[dim]No active context files[/dim]")
        else:
            console.print(f"[green]Active context: {context_manager.get_status_summary()}[/green]")
            for ctx in contexts:
                console.print(f"  [cyan]{ctx['path']}[/cyan] ({ctx['size']}, added {ctx['timestamp']})")
        return True
    
    subcommand = parts[1].lower()
    
    if subcommand == "clear":
        # Clear all context
        context_manager.clear_all_context()
        console.print("[green]All context files cleared[/green]")
        return True
    
    elif subcommand == "list":
        # List active contexts
        contexts = context_manager.list_contexts()
        if not contexts:
            console.print("[dim]No active context files[/dim]")
        else:
            console.print(f"[green]Active context ({context_manager.get_status_summary()}):[/green]")
            for ctx in contexts:
                console.print(f"  [cyan]{ctx['path']}[/cyan] ({ctx['size']}, added {ctx['timestamp']})")
        return True
    
    else:
        # Treat as file path (including cases where subcommand is actually a file path)
        file_path = " ".join(parts[1:])  # Rejoin everything after "/context"
        
        try:
            context_manager.add_file_context(file_path)
            console.print(f"[green]Added context file: {file_path}[/green]")
            console.print(f"[dim]Context status: {context_manager.get_status_summary()}[/dim]")
        except FileNotFoundError:
            console.print(f"[red]File not found: {file_path}[/red]")
        except ValueError as e:
            console.print(f"[red]Error adding context: {e}[/red]")
        except Exception as e:
            console.print(f"[red]Unexpected error: {e}[/red]")
        
        return True


def handle_at_command(at_command: str, context_manager: Optional[ContextManager], path_browser: Optional[PathBrowser], console) -> bool:
    """Handle @ commands for file browsing and context addition.
    
    Args:
        at_command: The @ command (e.g., "@", "@/path/", "@file.txt")
        context_manager: Context manager instance
        path_browser: Path browser instance
        console: Rich console for output
        
    Returns:
        True if command was handled
    """
    if not path_browser:
        if console:
            console.print("[red]Path browser not available[/red]")
        return True
    
    try:
        # Parse the @ command
        path, is_directory_listing = path_browser.parse_at_command(at_command)
        
        if is_directory_listing:
            # Suppress printing listings; rely on @ dropdown navigation
            # No output here keeps the input session active and uncluttered.
            return True
        else:
            # File addition to context
            if not context_manager:
                console.print("[red]Context manager not available[/red]")
                return True
            
            # Validate file first
            is_valid, error_msg = path_browser.validate_file_for_context(path)
            if not is_valid:
                console.print(f"[red]{error_msg}[/red]")
                return True
            
            # Try to add to context
            try:
                context_manager.add_file_context(path)
                display_path = path_browser.get_relative_path(path)
                console.print(f"[green]Added context file: {display_path}[/green]")
                console.print(f"[dim]Context status: {context_manager.get_status_summary()}[/dim]")
            except ValueError as e:
                console.print(f"[red]Error adding context: {e}[/red]")
            except Exception as e:
                console.print(f"[red]Unexpected error: {e}[/red]")
    
    except Exception as e:
        console.print(f"[red]Error processing @ command: {e}[/red]")
    
    return True
