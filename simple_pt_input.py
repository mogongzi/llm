#!/usr/bin/env python3
"""
Simplified prompt-toolkit implementation focusing on working functionality
"""
from __future__ import annotations

from typing import Optional
from rich.console import Console
from prompt_toolkit import prompt
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import HTML


def get_simple_pt_input(console: Console, prompt_style: str = "bold green") -> Optional[str]:
    """Properly configured prompt-toolkit input with Enter=submit, Meta+Enter=newline."""
    
    bindings = KeyBindings()
    
    # Override the default Enter behavior in multiline mode
    @bindings.add('enter', eager=True)
    def submit_on_enter(event):
        """Enter submits the input."""
        # Exit with the current buffer content
        event.app.exit(result=event.current_buffer.text)
    
    # Add new line with Shift+Enter - use the correct prompt-toolkit syntax
    @bindings.add('c-j', eager=True)  # Use Ctrl+J as reliable alternative to Shift+Enter
    def new_line_ctrl_j(event):
        """Ctrl+J adds a new line (since Shift+Enter detection is complex)."""
        event.current_buffer.insert_text('\n')
    
    @bindings.add('c-c')  # Ctrl+C
    def cancel(event):
        """Ctrl+C cancels input."""
        event.app.exit(result=None)
    
    @bindings.add('escape', eager=True)  # Esc (but not if followed by Enter)
    def escape_cancel(event):
        """Esc cancels input."""
        # Only cancel if not part of Meta+Enter sequence
        event.app.exit(result=None)
    
    # Custom prompt with our cursor character
    cursor_char = "▌"
    
    try:
        console.print(f"[dim]Enter=submit, Ctrl+J=new line, Esc/Ctrl+C=cancel[/dim]")
        
        # Custom prompt function to show cursor on every line
        def get_prompt():
            return f'{cursor_char} '
        
        def get_continuation_prompt(width, line_number, is_soft_wrap):
            # Return the same cursor for continuation lines
            return f'{cursor_char} '
        
        result = prompt(
            get_prompt,
            key_bindings=bindings,
            multiline=True,
            wrap_lines=True,
            prompt_continuation=get_continuation_prompt,
        )
        
        return result.strip() if result else None
        
    except KeyboardInterrupt:
        console.print("\n[dim]Cancelled[/dim]")
        return None
    except EOFError:
        console.print("\n[dim]Cancelled[/dim]")  
        return None


if __name__ == "__main__":
    from rich.console import Console
    
    console = Console()
    console.print("[bold cyan]Simple Prompt Toolkit Test[/bold cyan]")
    console.print("[dim]Default prompt-toolkit multiline behavior:[/dim]")
    console.print("• Enter normally submits")
    console.print("• Shift+Enter should add new lines") 
    console.print("• Esc or Ctrl+C to cancel")
    console.print()
    
    result = get_simple_pt_input(console)
    
    if result:
        console.print(f"[green]Result:[/green] {repr(result)}")
        console.print(f"[green]Formatted:[/green]")
        console.print(result)
    else:
        console.print("[dim]No input[/dim]")