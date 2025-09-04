#!/usr/bin/env python3
"""
Advanced multi-line input using prompt-toolkit
Supports proper Shift+Enter for new lines, Enter for submit
"""
from __future__ import annotations

from typing import Optional
from rich.console import Console
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.shortcuts import CompleteStyle


def get_prompt_toolkit_input(console: Console, prompt_style: str = "bold green") -> Optional[str]:
    """Get multi-line input with proper Shift+Enter/Enter handling using prompt-toolkit."""
    
    # Create custom key bindings
    bindings = KeyBindings()
    
    @bindings.add('c-j')  # Ctrl+J (alternative for new line)
    def new_line_ctrl_j(event):
        """Ctrl+J adds a new line."""
        event.current_buffer.insert_text('\n')
    
    # Handle Enter key - by default it adds new lines in multiline mode
    # We'll override the default behavior to submit instead
    @bindings.add('enter')
    def submit(event):
        """Enter submits the input."""
        event.app.exit(result=event.current_buffer.text.strip())
    
    @bindings.add('c-c')  # Ctrl+C
    def cancel(event):
        """Ctrl+C cancels input."""
        event.app.exit(result=None)
    
    @bindings.add('escape')  # Esc
    def escape_cancel(event):
        """Esc cancels input."""
        event.app.exit(result=None)
    
    # Custom prompt with our cursor character
    cursor_char = "▌"
    
    # Create the prompt with rich-like styling
    prompt_text = HTML(f'<style color="green"><b>{cursor_char}</b></style> ')
    
    try:
        # Show instructions
        console.print(f"[dim]Enter=submit, Shift+Enter=new line, /paste for large content, Esc/Ctrl+C=cancel[/dim]")
        
        result = prompt(
            prompt_text,
            key_bindings=bindings,
            multiline=True,
            complete_style=CompleteStyle.MULTI_COLUMN,
            mouse_support=True,
        )
        
        # Handle special commands
        if result and result.strip() == '/paste':
            return handle_paste_mode(console)
        
        return result if result else None
        
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled[/dim]")
        return None
    except EOFError:
        console.print("\n[dim]Cancelled[/dim]")
        return None


def handle_paste_mode(console: Console) -> Optional[str]:
    """Handle the special paste mode."""
    console.print(f"[yellow]Paste mode: Enter your content, then type '/end' on a new line to finish:[/yellow]")
    
    # Use regular input() for paste mode since it's simpler
    paste_lines = []
    while True:
        try:
            line = input()
            if line == '/end':
                break
            paste_lines.append(line)
        except EOFError:
            break
        except KeyboardInterrupt:
            console.print("[dim]Paste cancelled[/dim]")
            return None
    
    result = '\n'.join(paste_lines).strip()
    return result if result else None


def create_prompt_toolkit_multiline_input():
    """Factory function to create a prompt-toolkit based multiline input function."""
    def multiline_input_func(console: Console, prompt_style: str = "bold green") -> Optional[str]:
        return get_prompt_toolkit_input(console, prompt_style)
    return multiline_input_func


if __name__ == "__main__":
    # Test the prompt-toolkit input
    from rich.console import Console
    
    console = Console()
    console.print("[bold cyan]Prompt Toolkit Multi-line Input Test[/bold cyan]")
    console.print("[dim]Instructions:[/dim]")
    console.print("• Shift+Enter for new lines")
    console.print("• Enter to submit")
    console.print("• /paste for large content")
    console.print("• Esc or Ctrl+C to cancel")
    console.print()
    
    while True:
        console.print("[yellow]Enter your message:[/yellow]")
        result = get_prompt_toolkit_input(console)
        
        if result is None:
            console.print("[dim]Goodbye![/dim]")
            break
            
        if result.lower() in ["exit", "quit"]:
            console.print("[dim]Goodbye![/dim]")
            break
            
        console.print()
        console.print("[cyan]You entered:[/cyan]")
        console.print(f"[yellow]{repr(result)}[/yellow]")
        console.print()
        console.print("[cyan]Formatted output:[/cyan]")
        console.print(result)
        console.print()
        console.print("[dim]" + "="*50 + "[/dim]")
        console.print()