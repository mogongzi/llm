#!/usr/bin/env python3
"""
Simplified multi-line input with ▌ visual cursor

Uses a more straightforward approach:
- Enter = Submit
- Ctrl+J = New line (common alternative to Shift+Enter)
- Esc = Cancel
"""
from __future__ import annotations

import sys
import os
from typing import List, Optional
from rich.console import Console


class MultilineInput:
    def __init__(self, console: Console, prompt_style: str = "bold green"):
        self.console = console
        self.prompt_style = prompt_style
        self.cursor_char = "▌"
    
    def get_input(self) -> Optional[str]:
        """Get multi-line input using readline with custom display."""
        try:
            # Try to import readline for better input handling
            import readline
        except ImportError:
            pass
        
        lines = []
        self.console.print(f"[dim]Enter your message. Use Ctrl+J for new lines, Enter to submit, Esc+Enter to cancel:[/dim]")
        
        while True:
            try:
                # Show prompt with cursor
                line_prompt = f"[{self.prompt_style}]{self.cursor_char}[/] "
                
                # Use console.input which handles Rich markup
                # Always show the cursor prompt for consistency
                line = self.console.input(line_prompt)
                
                # Check for special commands
                if line == "\x1b":  # Esc (if somehow received)
                    self.console.print("[dim]Cancelled[/dim]")
                    return None
                
                # Check for Ctrl+J (new line signal)
                if line.endswith('\n') or line == '':
                    if line.endswith('\n'):
                        lines.append(line[:-1])  # Remove the \n
                    lines.append('')  # Add new empty line
                    continue
                
                # Regular line
                lines.append(line)
                
                # Check if user wants to submit (empty line after content)
                if line == '' and lines:
                    # Remove the last empty line and submit
                    lines.pop()
                    break
                    
            except EOFError:
                # Ctrl+D - submit what we have
                break
            except KeyboardInterrupt:
                # Ctrl+C - cancel
                self.console.print("\n[dim]Cancelled[/dim]")
                return None
        
        result = '\n'.join(lines).strip()
        return result if result else None


def simple_multiline_input(console: Console, prompt_style: str = "bold green") -> Optional[str]:
    """Multi-line input with paste support and Enter=submit, \\ for continuation."""
    import sys
    import os
    import select
    
    lines = []
    cursor_char = "▌"
    
    console.print(f"[dim]Type your message. Empty line submits when you have content.[/dim]")
    console.print(f"[dim]For multi-line paste: type '/paste', then paste content, then type '/end' on a new line.[/dim]")
    
    while True:
        try:
            # Normal single-line input
            line = console.input(f"[{prompt_style}]{cursor_char}[/] ")
            
            # Handle empty input - don't create new prompts for empty lines
            if line == "" and not lines:
                # Empty input with no content yet - stay on same "line" conceptually
                # Don't continue the loop which would create a new prompt
                # Instead, we let it fall through and the loop will naturally re-prompt
                pass  # This will hit the continue at the end anyway
            
            # Special paste mode
            elif line == '/paste':
                console.print(f"[yellow]Paste mode: Enter your content, then type '/end' on a new line to finish:[/yellow]")
                paste_lines = []
                while True:
                    try:
                        paste_line = input()  # Use regular input() for paste mode
                        # Check for end command
                        if paste_line == '/end':
                            break
                        paste_lines.append(paste_line)
                    except EOFError:
                        # Ctrl+D still works as backup
                        break
                    except KeyboardInterrupt:
                        # Ctrl+C in paste mode - return to normal input
                        console.print("[dim]Paste cancelled, continuing...[/dim]")
                        break
                
                if paste_lines:
                    return '\n'.join(paste_lines).strip()
                else:
                    console.print("[dim]No content pasted, continuing...[/dim]")
                    continue
            
            # Handle empty lines - submit when we have content
            if line == "":
                if lines:  # We have content, submit it
                    break
                else:  # No content yet, don't create new line, just continue
                    continue
            
            # Regular line - add it and continue (Enter = new line when typing)
            lines.append(line)
            continue
            
        except EOFError:
            # Ctrl+D - submit what we have
            break
        except KeyboardInterrupt:
            console.print("\n[dim]Cancelled[/dim]")
            return None
    
    result = '\n'.join(lines).strip()
    return result if result else None


def get_multiline_input(console: Console, prompt_style: str = "bold green") -> Optional[str]:
    """Get multi-line input with ▌ cursor indicator."""
    return simple_multiline_input(console, prompt_style)