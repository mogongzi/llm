#!/usr/bin/env python3
"""
Advanced multi-line input system using prompt-toolkit.

This module provides a sophisticated multi-line input interface with:
- Visual ▌ cursor indicator on every line
- Enter key for submission
- Ctrl+J for adding new lines
- Ctrl+J for adding new lines
- Consistent cross-platform behavior

Key Features:
    - Enter = Submit message
    - Ctrl+J = Add new line
    - Ctrl+J = Add new line for multi-line input
    - ▌ cursor appears on every line for visual consistency
"""
from __future__ import annotations

from typing import Optional

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from rich.console import Console

# Constants for visual consistency
CURSOR_CHARACTER = "▌"


def get_multiline_input(
    console: Console,
    prompt_style: str = "bold green",
    token_info: Optional[str] = None,
    thinking_mode: bool = False,
    history: Optional[list[str]] = None,
    tools_enabled: bool = False
) -> tuple[Optional[str], bool, bool, bool]:
    """
    Get multi-line input from user with enhanced prompt-toolkit interface.

    This function provides a sophisticated input experience with:
    - Visual cursor indicator (▌) on every line
    - Enter key submits the complete input
    - Ctrl+J adds new lines for multi-line messages
    - Ctrl+J for multi-line input support
    - Consistent escape/cancellation behavior

    Args:
        console: Rich console instance for displaying messages and styling
        prompt_style: Style string for prompt formatting (currently unused
                     but kept for API compatibility)
        token_info: Optional token usage string to display (e.g., "1.2k/200k (0.6%)")
        thinking_mode: Current thinking mode state (ON/OFF)
        history: Optional list of previous user inputs for up/down navigation
        tools_enabled: Current tools mode state (ON/OFF)

    Returns:
        tuple[Optional[str], bool, bool, bool]: (user_input, use_thinking, new_thinking_mode, new_tools_enabled)

    Raises:
        No exceptions are raised - all errors are caught and handled gracefully

    Examples:
        >>> console = Console()
        >>> user_input = get_multiline_input(console)
        >>> if user_input:
        ...     print(f"User entered: {user_input}")
    """
    key_bindings = _create_key_bindings(history or [])
    
    # Show instructions with token info before prompting
    _display_usage_instructions(console, token_info, thinking_mode, tools_enabled)

    try:
        user_input = _prompt_for_input(key_bindings, history)
        
        # Check for empty input immediately to avoid any visual artifacts
        if not user_input or not user_input.strip():
            return None, False, thinking_mode, tools_enabled
            
        return _process_user_input(user_input, console, thinking_mode, tools_enabled)

    except (KeyboardInterrupt, EOFError):
        _display_cancellation_message(console)
        return "__EXIT__", False, thinking_mode, tools_enabled  # Special exit signal


def _create_key_bindings(history: list[str] = None) -> KeyBindings:
    """
    Create and configure key bindings for the input interface.

    Sets up custom key combinations to override prompt-toolkit's default
    multiline behavior, allowing us to control when input is submitted
    versus when new lines are added. Also includes history navigation.

    Args:
        history: List of previous user inputs for up/down arrow navigation

    Returns:
        KeyBindings: Configured key bindings object for prompt-toolkit
    """
    bindings = KeyBindings()
    
    # History navigation state
    if history is None:
        history = []
    
    history_position = len(history)  # Start at end (no selection)
    original_text = ""  # Store original text when navigating

    @bindings.add('enter', eager=True)
    def handle_enter_key_submission(event):
        """Handle Enter key press - submit the current input only if non-empty."""
        current_text = event.current_buffer.text
        # Only submit if there's actual content (not just whitespace)
        if current_text and current_text.strip():
            event.app.exit(result=current_text)
        # If empty or whitespace only, do nothing (don't exit, don't add newline)

    @bindings.add('c-j', eager=True)
    def handle_ctrl_j_new_line(event):
        """Handle Ctrl+J key press - add a new line to current input."""
        event.current_buffer.insert_text('\n')

    @bindings.add('c-c')
    def handle_ctrl_c_cancellation(event):
        """Handle Ctrl+C key press - cancel input and return None."""
        event.app.exit(result=None)

    @bindings.add('escape', eager=True)
    def handle_escape_cancellation(event):
        """Handle Escape key press - cancel input and return None."""
        event.app.exit(result=None)

    @bindings.add('up', eager=True)
    def handle_up_arrow_history(event):
        """Handle Up arrow key press - navigate to previous history item."""
        nonlocal history_position, original_text
        
        if not history:
            return  # No history to navigate
            
        # Save original text when first navigating
        if history_position == len(history):
            original_text = event.current_buffer.text
            
        # Move up in history (towards older entries)
        if history_position > 0:
            history_position -= 1
            event.current_buffer.text = history[history_position]
            event.current_buffer.cursor_position = len(history[history_position])

    @bindings.add('down', eager=True)
    def handle_down_arrow_history(event):
        """Handle Down arrow key press - navigate to next history item."""
        nonlocal history_position, original_text
        
        if not history:
            return  # No history to navigate
            
        # Move down in history (towards newer entries)
        if history_position < len(history):
            history_position += 1
            
            if history_position == len(history):
                # Back to original/empty text
                event.current_buffer.text = original_text
                event.current_buffer.cursor_position = len(original_text)
            else:
                event.current_buffer.text = history[history_position]
                event.current_buffer.cursor_position = len(history[history_position])


    return bindings


def _display_usage_instructions(console: Console, token_info: Optional[str] = None, thinking_mode: bool = False, tools_enabled: bool = False, show_instructions: bool = True) -> None:
    """
    Display usage instructions to help user understand key bindings.

    Args:
        console: Rich console instance for styled output
        token_info: Optional token usage string to display on the right side
        thinking_mode: Whether thinking mode is currently enabled
        tools_enabled: Whether tools mode is currently enabled
        show_instructions: Whether to show the usage instructions
    """
    # Build instructions with status indicators
    base_instructions = "↵ send    Ctrl+J newline"
    
    # Add thinking mode status
    if thinking_mode:
        thinking_part = "/think reasoning [ON]"
    else:
        thinking_part = "/think reasoning"
    
    # Add tools mode status  
    if tools_enabled:
        tools_part = "/tools functions [ON]"
    else:
        tools_part = "/tools functions"
    
    instructions = f"{base_instructions}    {thinking_part}    {tools_part}    Esc/Ctrl+C=cancel"

    # Only show instructions if requested
    if not show_instructions:
        # Show only token info if available
        if token_info:
            console.print(f"[dim]Tokens: {token_info}[/dim]")
        return

    if token_info:
        # Calculate padding to right-align token info
        terminal_width = console.size.width
        base_length = len(instructions)  # Use actual instruction text length
        token_length = len(f"Tokens: {token_info}")
        padding_needed = terminal_width - base_length - token_length - 4  # 4 for spacing buffer

        if padding_needed > 0:
            padding = " " * padding_needed
            full_line = f"{instructions}{padding}Tokens: {token_info}"
        else:
            # Fallback if terminal too narrow
            full_line = f"{instructions}  Tokens: {token_info}"
    else:
        full_line = instructions

    console.print(f"[dim]{full_line}[/dim]")


def _create_prompt_functions():
    """
    Create prompt functions for consistent cursor display.

    Returns:
        tuple: (main_prompt_function, continuation_prompt_function)
    """
    def get_main_prompt():
        """Return the main prompt string with cursor character."""
        return HTML(f'<lemonchiffon>{CURSOR_CHARACTER}</lemonchiffon> ')

    def get_continuation_prompt(width, line_number, is_soft_wrap):
        """
        Return the continuation prompt for multi-line input.

        Args:
            width: Terminal width (unused but required by prompt-toolkit)
            line_number: Current line number (unused but required)
            is_soft_wrap: Whether this is a soft wrap (unused but required)

        Returns:
            str: Same cursor character for visual consistency
        """
        return HTML(f'<lemonchiffon>{CURSOR_CHARACTER}</lemonchiffon> ')

    return get_main_prompt, get_continuation_prompt


def _prompt_for_input(key_bindings: KeyBindings, history: list[str] = None) -> str:
    """
    Execute the actual prompt-toolkit input session.

    Args:
        key_bindings: Pre-configured key bindings for the input session
        history: List of previous inputs for history navigation

    Returns:
        str: Raw user input from prompt-toolkit
    """
    main_prompt, continuation_prompt = _create_prompt_functions()

    return prompt(
        main_prompt,
        key_bindings=key_bindings,
        multiline=True,
        wrap_lines=True,
        prompt_continuation=continuation_prompt,
    )


def _process_user_input(user_input: str, console: Console, thinking_mode: bool, tools_enabled: bool) -> tuple[Optional[str], bool, bool, bool]:
    """
    Process the raw user input and handle special commands.

    Args:
        user_input: Raw input string from prompt-toolkit
        console: Rich console instance for any needed output
        thinking_mode: Current thinking mode state
        tools_enabled: Current tools mode state

    Returns:
        tuple[Optional[str], bool, bool, bool]: (processed_input, use_thinking, new_thinking_mode, new_tools_enabled)
    """
    # Input is guaranteed to be non-empty by caller
    cleaned_input = user_input.strip()

    # Handle thinking mode toggle command
    if cleaned_input == '/think':
        if thinking_mode:
            console.print("[dim]Thinking mode disabled.[/dim]")
        else:
            console.print("[green]Thinking mode enabled. All messages will now show reasoning.[/green]")
        return None, False, not thinking_mode, tools_enabled  # Toggle thinking mode
    
    # Handle tools mode toggle command
    elif cleaned_input == '/tools':
        if tools_enabled:
            console.print("[dim]Tools disabled. Claude will not use function calls.[/dim]")
        else:
            console.print("[green]Tools enabled. Claude can now use calculator, weather, and time functions.[/green]")
        return None, False, thinking_mode, not tools_enabled  # Toggle tools mode

    # Handle legacy /think <message> format for backward compatibility
    elif cleaned_input.startswith('/think '):
        actual_message = cleaned_input[7:].strip()  # Remove "/think " prefix
        if actual_message:
            console.print("[dim]Tip: Use /think to toggle thinking mode on/off, then just type your message.[/dim]")
            return actual_message, True, thinking_mode, tools_enabled
        else:
            console.print("[yellow]Use /think to toggle thinking mode on/off, or /think <message> for one-time thinking.[/yellow]")
            return None, False, thinking_mode, tools_enabled

    # Regular message - use current thinking mode
    if cleaned_input:
        return cleaned_input, thinking_mode, thinking_mode, tools_enabled
    else:
        return None, False, thinking_mode, tools_enabled


def _display_cancellation_message(console: Console) -> None:
    """
    Display a user-friendly cancellation message.

    Args:
        console: Rich console instance for styled output
    """
    console.print("\n[dim]Cancelled[/dim]")




def _run_interactive_test() -> None:
    """
    Run an interactive test of the multi-line input system.

    This function demonstrates the input system's capabilities and allows
    manual testing of all features including normal input and multi-line input.
    """
    console = Console()

    _display_test_header(console)
    _display_test_instructions(console)

    while True:
        console.print("[yellow]Enter your message (or 'exit' to quit):[/yellow]")

        result = get_multiline_input(console)

        if result is None:
            console.print("[dim]Goodbye![/dim]")
            break

        if result.lower() in ["exit", "quit"]:
            console.print("[dim]Goodbye![/dim]")
            break

        _display_test_results(console, result)


def _display_test_header(console: Console) -> None:
    """Display the test application header."""
    console.print("[bold cyan]Multi-line Input System Test[/bold cyan]")


def _display_test_instructions(console: Console) -> None:
    """Display comprehensive usage instructions for testing."""
    console.print("[dim]Available features:[/dim]")
    console.print("• Enter = Submit message")
    console.print("• Ctrl+J = Add new line")
    console.print("• Esc or Ctrl+C = Cancel current input")
    console.print("• Type 'exit' or 'quit' to end test")
    console.print()


def _display_test_results(console: Console, user_input: str) -> None:
    """
    Display the results of user input in a formatted way.

    Args:
        console: Rich console instance for styled output
        user_input: The input string to display
    """
    console.print()
    console.print("[cyan]Raw input (Python representation):[/cyan]")
    console.print(f"[yellow]{repr(user_input)}[/yellow]")
    console.print()
    console.print("[cyan]Formatted output:[/cyan]")
    console.print(user_input)
    console.print()
    console.print("[dim]" + "="*50 + "[/dim]")
    console.print()


if __name__ == "__main__":
    _run_interactive_test()