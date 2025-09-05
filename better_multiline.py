#!/usr/bin/env python3
"""
Better multi-line input with proper key detection
Enter = submit, Ctrl+Enter = new line
"""
from __future__ import annotations

import sys
import os
from typing import List, Optional
from rich.console import Console

# Platform-specific imports for raw input
if os.name == 'nt':  # Windows
    import msvcrt
else:  # Unix-like (Linux, macOS)
    import tty
    import termios
    import select


class BetterMultilineInput:
    def __init__(self, console: Console, prompt_style: str = "bold green"):
        self.console = console
        self.prompt_style = prompt_style
        self.cursor_char = "▌"
        
    def get_input(self) -> Optional[str]:
        """Get multi-line input with Enter=submit, Ctrl+Enter=newline."""
        lines = [""]
        current_line = 0
        cursor_pos = 0
        
        self.console.print(f"[dim]Enter=submit, Ctrl+Enter=newline, Esc=cancel:[/dim]")
        self._display_lines(lines, current_line, cursor_pos)
        
        if os.name == 'nt':
            return self._input_windows(lines, current_line)
        else:
            return self._input_unix(lines, current_line)
    
    def _display_lines(self, lines: List[str], current_line: int, cursor_pos: int):
        """Display all lines with ▌ cursor."""
        # Move to start of our input area
        for i in range(current_line + 1):
            if i > 0:
                self.console.print(f"\033[A", end="")  # Move up
        
        # Display all lines
        for i, line in enumerate(lines):
            self.console.print(f"\033[2K", end="")  # Clear line
            self.console.print(f"[{self.prompt_style}]{self.cursor_char}[/] {line}")
        
        # Position cursor at the current editing position
        if current_line < len(lines):
            # Move up to current line
            moves_up = len(lines) - current_line - 1
            if moves_up > 0:
                self.console.print(f"\033[{moves_up}A", end="")
            # Position horizontally (▌ + space + text position)
            col_pos = len(f"{self.cursor_char} ") + cursor_pos + 1
            self.console.print(f"\033[{col_pos}G", end="")
    
    def _input_unix(self, lines: List[str], current_line: int) -> Optional[str]:
        """Handle input on Unix systems with proper key detection."""
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            cursor_pos = len(lines[current_line])
            
            while True:
                char = sys.stdin.read(1)
                
                if char == '\x1b':  # Escape sequence
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        # Read escape sequence
                        next_chars = sys.stdin.read(2)
                        # Ignore arrow keys for now
                        continue
                    else:
                        # Standalone Esc - cancel
                        self.console.print("\n[dim]Cancelled[/dim]")
                        return None
                
                elif char == '\r':  # Enter key
                    # Regular Enter - submit
                    result = '\n'.join(lines).strip()
                    self.console.print()  # Move to next line
                    return result if result else None
                
                elif char == '\n':  # Ctrl+Enter (Line Feed)
                    # Add new line
                    lines.append("")
                    current_line += 1
                    cursor_pos = 0
                    self.console.print()  # Move to next line  
                    self._display_lines(lines, current_line, cursor_pos)
                
                elif char == '\x7f':  # Backspace
                    if cursor_pos > 0:
                        # Remove character
                        line = lines[current_line]
                        lines[current_line] = line[:cursor_pos-1] + line[cursor_pos:]
                        cursor_pos -= 1
                        self._redraw_current_line(lines[current_line], cursor_pos)
                    elif current_line > 0:
                        # Join with previous line
                        prev_line = lines.pop(current_line)
                        current_line -= 1
                        cursor_pos = len(lines[current_line])
                        lines[current_line] += prev_line
                        self._display_lines(lines, current_line, cursor_pos)
                
                elif char == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                
                elif char.isprintable():
                    # Add character at cursor position
                    line = lines[current_line]
                    lines[current_line] = line[:cursor_pos] + char + line[cursor_pos:]
                    cursor_pos += 1
                    self._redraw_current_line(lines[current_line], cursor_pos)
            
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def _input_windows(self, lines: List[str], current_line: int) -> Optional[str]:
        """Simplified Windows implementation."""
        self.console.print("[yellow]Windows: Use regular input for now[/yellow]")
        
        while True:
            try:
                line = input(f"{self.cursor_char} ")
                if line.lower() == 'submit':
                    break
                lines[current_line] = line
                lines.append("")
                current_line += 1
            except KeyboardInterrupt:
                return None
            except EOFError:
                break
        
        return '\n'.join(lines).strip()
    
    def _redraw_current_line(self, content: str, cursor_pos: int):
        """Redraw current line and position cursor."""
        self.console.print(f"\033[2K\r[{self.prompt_style}]{self.cursor_char}[/] {content}", end="")
        # Position cursor
        col_pos = len(f"{self.cursor_char} ") + cursor_pos + 1
        self.console.print(f"\033[{col_pos}G", end="")


def get_better_multiline_input(console: Console, prompt_style: str = "bold green") -> Optional[str]:
    """Get multi-line input with proper Enter=submit, Ctrl+Enter=newline behavior."""
    handler = BetterMultilineInput(console, prompt_style)
    return handler.get_input()


if __name__ == "__main__":
    console = Console()
    console.print("[bold]Testing Better Multi-line Input[/bold]")
    result = get_better_multiline_input(console)
    if result:
        console.print(f"[green]Result:[/green] {repr(result)}")
        console.print("[green]Formatted:[/green]")
        console.print(result)
    else:
        console.print("[dim]No input[/dim]")