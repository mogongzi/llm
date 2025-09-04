#!/usr/bin/env python3
"""Test script for multiline input functionality."""

from rich.console import Console
from multiline_input import get_multiline_input

def main():
    console = Console()
    
    console.print("[bold cyan]Multi-line Input Test[/bold cyan]")
    console.print("[dim]Instructions:[/dim]")
    console.print("• Type your message")
    console.print("• Enter for new lines")
    console.print("• Empty line to submit")  
    console.print("• '/paste' for large content")
    console.print("• Ctrl+C cancels")
    console.print()
    
    while True:
        console.print("[yellow]Enter some text:[/yellow]")
        
        result = get_multiline_input(console, "bold green")
        
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

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nGoodbye!")