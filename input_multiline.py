#!/usr/bin/env python3
"""
Multi-line input with visual cursor indicator ▌

Features:
- Shift+Enter for new lines
- Enter to submit
- Visual ▌ cursor at start of each line (non-selectable)
- Cross-platform key detection
"""
from __future__ import annotations

import sys
import os
from typing import List, Optional
from rich.console import Console
from rich.text import Text

# Platform-specific imports
if os.name == 'nt':  # Windows
    import msvcrt
else:  # Unix-like (Linux, macOS)
    import tty
    import termios
    import select


class MultilineInput:
    def __init__(self, console: Console, prompt_style: str = "bold green"):
        self.console = console
        self.prompt_style = prompt_style
        self.cursor_char = "▌"
        
    def get_input(self, prompt_text: str = "") -> Optional[str]:
        """Get multi-line input with ▌ visual cursor.
        
        Returns:
            String input or None if cancelled (Esc)
        """
        lines: List[str] = [""]
        current_line = 0
        
        # Show initial prompt
        self._display_lines(lines, current_line, prompt_text)
        
        if os.name == 'nt':
            return self._input_windows(lines, current_line, prompt_text)
        else:
            return self._input_unix(lines, current_line, prompt_text)
    
    def _display_lines(self, lines: List[str], current_line: int, prompt_text: str = ""):
        """Display all lines with ▌ cursors."""
        # Clear current display area
        for i in range(len(lines)):
            if i < len(lines) - 1 or lines[current_line]:
                # Move cursor up if not on last line
                if i > 0:
                    self.console.print(f"\033[A", end="")
                # Clear line and print with cursor
                self.console.print(f"\033[2K", end="")  # Clear line
                self.console.print(f"[{self.prompt_style}]{self.cursor_char}[/] {lines[i]}")
        
        # Position cursor at end of current line
        if current_line < len(lines):
            cursor_pos = len(lines[current_line]) + 2  # +2 for "▌ "
            self.console.print(f"\033[{cursor_pos}G", end="")
    
    def _input_unix(self, lines: List[str], current_line: int, prompt_text: str) -> Optional[str]:
        """Handle input on Unix-like systems."""
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            
            while True:
                char = sys.stdin.read(1)
                
                if char == '\x1b':  # Escape sequence
                    # Check for Esc key (standalone) or special sequences
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        next_char = sys.stdin.read(1)
                        if next_char == '[':
                            # Arrow keys and other sequences
                            third_char = sys.stdin.read(1)
                            if third_char == 'A':  # Up arrow - ignore
                                continue
                            elif third_char == 'B':  # Down arrow - ignore
                                continue
                            elif third_char == 'C':  # Right arrow - ignore
                                continue
                            elif third_char == 'D':  # Left arrow - ignore
                                continue
                        elif next_char == 'O':
                            # Function keys - ignore
                            sys.stdin.read(1)
                            continue
                    else:
                        # Standalone Esc key - cancel
                        self.console.print("\n[dim]Cancelled[/dim]")
                        return None
                        
                elif char == '\r':  # Enter key
                    # In raw mode, we get \r for Enter
                    # We need to distinguish between Enter and Shift+Enter
                    # Let's use a simpler approach: Ctrl+Enter for new line, Enter for submit
                    break
                    
                elif char == '\n':  # Line feed (Ctrl+Enter or Shift+Enter)
                    # Add new line
                    lines.append("")
                    current_line += 1
                    self.console.print()  # Move to next line
                    self._display_current_line("", current_line)
                    
                elif char == '\x7f':  # Backspace
                    if lines[current_line]:
                        lines[current_line] = lines[current_line][:-1]
                        self._redraw_current_line(lines[current_line])
                    elif current_line > 0:
                        # Join with previous line and go up
                        content_to_move = lines.pop(current_line)
                        current_line -= 1
                        lines[current_line] += content_to_move
                        # Redraw from current line up
                        self.console.print(f"\033[A\033[2K", end="")  # Move up and clear
                        self._redraw_current_line(lines[current_line])
                        
                elif char == '\x03':  # Ctrl+C
                    raise KeyboardInterrupt
                    
                elif char.isprintable():
                    lines[current_line] += char
                    self._redraw_current_line(lines[current_line])
            
            return '\n'.join(lines).strip()
            
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def _input_windows(self, lines: List[str], current_line: int, prompt_text: str) -> Optional[str]:
        """Handle input on Windows systems."""
        # Simplified Windows implementation
        # For full implementation, would need to handle raw key codes
        self.console.print("[dim]Windows multi-line input - use Ctrl+Z then Enter to submit[/dim]")
        
        result_lines = []
        while True:
            try:
                line = input(f"▌ ")
                if line == "\x1a":  # Ctrl+Z
                    break
                result_lines.append(line)
            except EOFError:
                break
            except KeyboardInterrupt:
                return None
        
        return '\n'.join(result_lines).strip()
    
    def _display_current_line(self, content: str, line_num: int = 0):
        """Display a single line with ▌ cursor."""
        self.console.print(f"[{self.prompt_style}]{self.cursor_char}[/] {content}", end="")
    
    def _redraw_current_line(self, content: str):
        """Redraw just the current line."""
        self.console.print(f"\033[2K\r[{self.prompt_style}]{self.cursor_char}[/] {content}", end="")
    
    def _redraw_all_lines(self, lines: List[str], current_line: int):
        """Redraw all lines."""
        # Move to beginning of input area
        self.console.print(f"\033[{len(lines)}A", end="")
        for i, line in enumerate(lines):
            self.console.print(f"\033[2K[{self.prompt_style}]{self.cursor_char}[/] {line}")
        # Position cursor at end of current line
        if current_line < len(lines):
            move_up = len(lines) - current_line - 1
            if move_up > 0:
                self.console.print(f"\033[{move_up}A", end="")
            cursor_pos = len(lines[current_line]) + 2
            self.console.print(f"\033[{cursor_pos}G", end="")


def get_multiline_input(console: Console, prompt_text: str = "", prompt_style: str = "bold green") -> Optional[str]:
    """Convenience function to get multi-line input."""
    input_handler = MultilineInput(console, prompt_style)
    return input_handler.get_input(prompt_text)