#!/usr/bin/env python3
"""
Advanced multi-line input system using prompt-toolkit.

This module provides a sophisticated multi-line input interface with:
- Visual ▌ cursor indicator on every line
- Enter key for submission
- Ctrl+J for adding new lines
- Special /paste mode for large content blocks
- Consistent cross-platform behavior

Key Features:
    - Enter = Submit message
    - Ctrl+J = Add new line
    - /paste = Enter special paste mode
    - ▌ cursor appears on every line for visual consistency
"""
from __future__ import annotations

from typing import Optional

from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console

# Constants for visual consistency
CURSOR_CHARACTER = "▌"
PASTE_COMMAND = "/paste"
PASTE_END_COMMAND = "/end"


def get_multiline_input(
    console: Console,
    prompt_style: str = "bold green",
    token_info: Optional[str] = None
) -> Optional[str]:
    """
    Get multi-line input from user with enhanced prompt-toolkit interface.

    This function provides a sophisticated input experience with:
    - Visual cursor indicator (▌) on every line
    - Enter key submits the complete input
    - Ctrl+J adds new lines for multi-line messages
    - Special /paste command for handling large content blocks
    - Consistent escape/cancellation behavior

    Args:
        console: Rich console instance for displaying messages and styling
        prompt_style: Style string for prompt formatting (currently unused
                     but kept for API compatibility)
        token_info: Optional token usage string to display (e.g., "1.2k/200k (0.6%)")

    Returns:
        Optional[str]: The user's input as a string, or None if cancelled

    Raises:
        No exceptions are raised - all errors are caught and handled gracefully

    Examples:
        >>> console = Console()
        >>> user_input = get_multiline_input(console)
        >>> if user_input:
        ...     print(f"User entered: {user_input}")
    """
    key_bindings = _create_key_bindings()
    _display_usage_instructions(console, token_info)

    try:
        user_input = _prompt_for_input(key_bindings)
        return _process_user_input(user_input, console)

    except (KeyboardInterrupt, EOFError):
        _display_cancellation_message(console)
        return None


def _create_key_bindings() -> KeyBindings:
    """
    Create and configure key bindings for the input interface.

    Sets up custom key combinations to override prompt-toolkit's default
    multiline behavior, allowing us to control when input is submitted
    versus when new lines are added.

    Returns:
        KeyBindings: Configured key bindings object for prompt-toolkit
    """
    bindings = KeyBindings()

    @bindings.add('enter', eager=True)
    def handle_enter_key_submission(event):
        """Handle Enter key press - submit the current input."""
        event.app.exit(result=event.current_buffer.text)

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

    return bindings


def _display_usage_instructions(console: Console, token_info: Optional[str] = None) -> None:
    """
    Display usage instructions to help user understand key bindings.

    Args:
        console: Rich console instance for styled output
        token_info: Optional token usage string to display on the right side
    """
    instructions = "↵ send    Ctrl+J newline    Esc/Ctrl+C=cancel"

    if token_info:
        # Calculate padding to right-align token info
        terminal_width = console.size.width
        base_length = len("↵ send    Ctrl+J newline    Esc/Ctrl+C=cancel")
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
        return f'{CURSOR_CHARACTER} '

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
        return f'{CURSOR_CHARACTER} '

    return get_main_prompt, get_continuation_prompt


def _prompt_for_input(key_bindings: KeyBindings) -> str:
    """
    Execute the actual prompt-toolkit input session.

    Args:
        key_bindings: Pre-configured key bindings for the input session

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


def _process_user_input(user_input: str, console: Console) -> Optional[str]:
    """
    Process the raw user input and handle special commands.

    Args:
        user_input: Raw input string from prompt-toolkit
        console: Rich console instance for any needed output

    Returns:
        Optional[str]: Processed input or result from special command handling
    """
    if not user_input:
        return None

    cleaned_input = user_input.strip()

    # Handle special paste command
    if cleaned_input == PASTE_COMMAND:
        return _handle_paste_mode(console)

    return cleaned_input if cleaned_input else None


def _display_cancellation_message(console: Console) -> None:
    """
    Display a user-friendly cancellation message.

    Args:
        console: Rich console instance for styled output
    """
    console.print("\n[dim]Cancelled[/dim]")


def _handle_paste_mode(console: Console) -> Optional[str]:
    """
    Handle special paste mode for large content blocks.

    In paste mode, users can input large blocks of text (like JSON, code, etc.)
    line by line until they type the end command. This is useful for content
    that would be difficult to format using the normal multi-line input.

    Args:
        console: Rich console instance for displaying instructions and messages

    Returns:
        Optional[str]: Combined content from all input lines, or None if cancelled

    Usage:
        User types "/paste" in normal input, then:
        1. Enters content line by line
        2. Types "/end" on a new line to finish
        3. All content between /paste and /end is returned as single string
    """
    _display_paste_mode_instructions(console)

    content_lines = []

    while True:
        try:
            line = input()

            if line == PASTE_END_COMMAND:
                break

            content_lines.append(line)

        except EOFError:
            # Ctrl+D pressed - treat as end of paste
            break
        except KeyboardInterrupt:
            # Ctrl+C pressed - cancel paste mode
            console.print("[dim]Paste cancelled[/dim]")
            return None

    # Join all lines and clean up whitespace
    combined_content = '\n'.join(content_lines).strip()
    return combined_content if combined_content else None


def _display_paste_mode_instructions(console: Console) -> None:
    """
    Display instructions for paste mode usage.

    Args:
        console: Rich console instance for styled output
    """
    instruction_text = (
        f"Paste mode: Enter your content, then type "
        f"'{PASTE_END_COMMAND}' on a new line to finish:"
    )
    console.print(f"[yellow]{instruction_text}[/yellow]")


# Legacy function name for backward compatibility
# This ensures existing code continues to work after refactoring
handle_paste_mode = _handle_paste_mode


def _run_interactive_test() -> None:
    """
    Run an interactive test of the multi-line input system.

    This function demonstrates the input system's capabilities and allows
    manual testing of all features including normal input, multi-line input,
    and paste mode functionality.
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
    console.print("• /paste = Enter paste mode for large content")
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