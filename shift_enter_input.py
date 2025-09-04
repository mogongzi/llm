#!/usr/bin/env python3
"""
Multi-line input with Shift+Enter for new lines, Enter for submit
Uses raw terminal input to detect key combinations properly
"""
from __future__ import annotations

import sys
import os
from typing import List, Optional
from rich.console import Console

# Unix-specific imports
if os.name != 'nt':
    import tty
    import termios
    import select


class ShiftEnterInput:
    def __init__(self, console: Console, prompt_style: str = "bold green"):
        self.console = console
        self.prompt_style = prompt_style
        self.cursor_char = "▌"
        
    def get_input(self) -> Optional[str]:
        """Get multi-line input with Shift+Enter=newline, Enter=submit."""
        if os.name == 'nt':
            return self._windows_fallback()
        else:
            return self._unix_input()
    
    def _unix_input(self) -> Optional[str]:
        """Unix implementation with proper Shift+Enter detection."""
        lines = [""]
        current_line = 0
        
        self.console.print(f"[dim]Enter=submit, Shift+Enter=new line, /paste for large content:[/dim]")
        
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            # Set terminal to raw mode for key detection
            tty.setcbreak(sys.stdin.fileno())  # Use cbreak instead of raw for better compatibility
            
            self._display_prompt()
            
            while True:
                # Read input character by character
                char = sys.stdin.read(1)
                
                if char == '\x1b':  # Escape sequence
                    # Read the rest of the escape sequence
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        seq = char + sys.stdin.read(2)
                        if seq == '\x1b\x0d':  # Shift+Enter (some terminals)
                            self._handle_new_line(lines, current_line)
                            current_line += 1
                            continue
                    # Standalone Esc - cancel
                    self.console.print("\n[dim]Cancelled[/dim]")
                    return None
                
                elif char == '\r':  # Enter key
                    # Check if Shift is held (this is terminal-dependent)
                    # For now, treat regular Enter as submit
                    result = '\n'.join(lines).strip()
                    self.console.print()  # New line after input
                    return result if result else None
                
                elif char == '\n':  # Some terminals send \n for Shift+Enter
                    self._handle_new_line(lines, current_line)
                    current_line += 1
                    continue
                
                elif char == '\x7f':  # Backspace
                    if lines[current_line]:
                        lines[current_line] = lines[current_line][:-1]
                        self._redraw_line(lines[current_line])
                    elif current_line > 0:
                        # Move to previous line
                        content = lines.pop(current_line)
                        current_line -= 1
                        lines[current_line] += content
                        self._redraw_all(lines, current_line)
                
                elif char == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                
                elif char.isprintable():
                    lines[current_line] += char
                    self._redraw_line(lines[current_line])
        
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def _windows_fallback(self) -> Optional[str]:
        """Fallback for Windows - use the current approach."""
        from multiline_input import simple_multiline_input
        return simple_multiline_input(self.console, self.prompt_style)
    
    def _display_prompt(self):
        """Display the initial prompt."""
        self.console.print(f"[{self.prompt_style}]{self.cursor_char}[/] ", end="")
    
    def _handle_new_line(self, lines: List[str], current_line: int):
        """Handle adding a new line."""
        lines.append("")
        self.console.print()  # Move to next line
        self.console.print(f"[{self.prompt_style}]{self.cursor_char}[/] ", end="")
    
    def _redraw_line(self, content: str):
        """Redraw the current line."""
        # Clear line and redraw with content
        self.console.print(f"\r\033[K[{self.prompt_style}]{self.cursor_char}[/] {content}", end="")
    
    def _redraw_all(self, lines: List[str], current_line: int):
        """Redraw all lines (used after backspace joins lines)."""
        # Move up to first line
        for _ in range(current_line + 1):
            self.console.print("\033[A", end="")
        
        # Redraw all lines
        for i, line in enumerate(lines):
            self.console.print(f"\r\033[K[{self.prompt_style}]{self.cursor_char}[/] {line}")
        
        # Move back to current line
        moves_up = len(lines) - current_line - 1
        for _ in range(moves_up):
            self.console.print("\033[A", end="")
        
        # Position cursor at end of line
        self.console.print(f"\r\033[{len(f'{self.cursor_char} {lines[current_line]}')+1}C", end="")


def get_shift_enter_input(console: Console, prompt_style: str = "bold green") -> Optional[str]:
    """Get multi-line input with Shift+Enter for new lines."""
    handler = ShiftEnterInput(console, prompt_style)
    return handler.get_input()


if __name__ == "__main__":
    console = Console()
    console.print("[bold]Testing Shift+Enter Input[/bold]")
    console.print("[dim]Enter=submit, Shift+Enter=new line[/dim]")
    
    result = get_shift_enter_input(console)
    if result:
        console.print(f"[green]You entered:[/green]")
        console.print(repr(result))
        console.print(f"[green]Formatted:[/green]")
        console.print(result)
    else:
        console.print("[dim]No input[/dim]")