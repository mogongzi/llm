import sys
import json
import requests
import re
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text
from rich.panel import Panel

console = Console()
URL = "http://127.0.0.1:8000/invoke"

class SimpleStreamingMarkdownParser:
    def __init__(self):
        self.buffer = ""
        self.last_output_pos = 0
        self.in_code_block = False
        self.current_code_lang = ""
        self.current_code_content = ""
        
    def feed(self, text: str):
        """Add text to buffer and output what we can safely render"""
        self.buffer += text
        self._process_buffer()
    
    def _process_buffer(self):
        """Process buffer and output complete elements"""
        while self.last_output_pos < len(self.buffer):
            remaining = self.buffer[self.last_output_pos:]
            
            if not self.in_code_block:
                # Look for start of code block
                fence_match = re.search(r'^```(\w*)\s*$', remaining, re.MULTILINE)
                if fence_match:
                    # Output text before code block
                    pre_text = remaining[:fence_match.start()]
                    if pre_text.strip():
                        self._output_plain_text(pre_text)
                    
                    # Start code block
                    self.in_code_block = True
                    self.current_code_lang = fence_match.group(1) or "text"
                    self.current_code_content = ""
                    self.last_output_pos += fence_match.end()
                else:
                    # No code block start found, check if we have a partial fence at the end
                    partial_fence = re.search(r'```\w*$', remaining)
                    if partial_fence:
                        # Output text before partial fence, wait for more
                        safe_text = remaining[:partial_fence.start()]
                        if safe_text.strip():
                            self._output_plain_text(safe_text)
                            self.last_output_pos += partial_fence.start()
                        break
                    else:
                        # Safe to output all remaining text
                        if remaining.strip():
                            self._output_plain_text(remaining)
                            self.last_output_pos = len(self.buffer)
                        break
            else:
                # We're in a code block, look for closing fence
                end_fence_match = re.search(r'^```\s*$', remaining, re.MULTILINE)
                if end_fence_match:
                    # Found closing fence
                    code_content = remaining[:end_fence_match.start()]
                    self.current_code_content += code_content
                    
                    # Output the complete code block
                    self._output_code_block(self.current_code_content, self.current_code_lang)
                    
                    # Reset state
                    self.in_code_block = False
                    self.current_code_content = ""
                    self.current_code_lang = ""
                    self.last_output_pos += end_fence_match.end()
                else:
                    # No closing fence yet, add to current code content
                    self.current_code_content += remaining
                    self.last_output_pos = len(self.buffer)
                    break
    
    def _output_plain_text(self, text: str):
        """Output plain text without markdown processing"""
        if text.strip():
            # Clean up text and output
            clean_text = text.rstrip('\n')
            if clean_text:
                # Process basic markdown elements
                clean_text = self._process_inline_markdown(clean_text)
                console.print(clean_text, end="", markup=True)
    
    def _process_inline_markdown(self, text: str):
        """Process basic inline markdown elements"""
        # Convert **bold** to rich markup
        text = re.sub(r'\*\*(.+?)\*\*', r'[bold]\1[/bold]', text)
        # Convert *italic* to rich markup  
        text = re.sub(r'\*(.+?)\*', r'[italic]\1[/italic]', text)
        # Convert `code` to rich markup
        text = re.sub(r'`([^`]+)`', r'[cyan]\1[/cyan]', text)
        return text
    
    def _output_code_block(self, code_content: str, language: str):
        """Output a syntax-highlighted code block"""
        try:
            # Clean up code content
            code_content = code_content.rstrip('\n')
            
            if language and language.lower() not in ['', 'text', 'plain']:
                syntax = Syntax(
                    code_content,
                    language,
                    theme="monokai",
                    line_numbers=True,
                    word_wrap=True,
                    background_color="default"
                )
            else:
                syntax = Text(code_content, style="white")
            
            # Create panel with better formatting
            panel = Panel(
                syntax,
                title=f"[bold cyan]{language or 'text'}[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(0, 1),
                expand=False
            )
            
            console.print()  # Add spacing before code block
            console.print(panel)
            console.print()  # Add spacing after code block
            
        except Exception as e:
            # Fallback rendering
            console.print(f"[dim red]Syntax highlight error for {language}: {str(e)}[/dim red]")
            fallback_panel = Panel(
                Text(code_content, style="white"),
                title=f"[bold white]{language or 'text'}[/bold white]",
                border_style="white",
                padding=(0, 1),
                expand=False
            )
            console.print()
            console.print(fallback_panel)
            console.print()
    
    def finalize(self):
        """Output any remaining content at end of stream"""
        if self.last_output_pos < len(self.buffer):
            remaining = self.buffer[self.last_output_pos:]
            
            if self.in_code_block:
                # We have an incomplete code block
                self.current_code_content += remaining
                if self.current_code_content.strip():
                    try:
                        syntax = Syntax(
                            self.current_code_content.rstrip(),
                            self.current_code_lang,
                            theme="monokai",
                            line_numbers=True,
                            background_color="default"
                        )
                        panel = Panel(
                            syntax,
                            title=f"[bold yellow]{self.current_code_lang} (incomplete)[/bold yellow]",
                            border_style="yellow",
                            padding=(0, 1),
                            expand=False
                        )
                        console.print()
                        console.print(panel)
                    except:
                        console.print(f"\n[dim yellow]Incomplete code block:\n{self.current_code_content}[/dim yellow]")
            else:
                # Just plain text remaining
                if remaining.strip():
                    self._output_plain_text(remaining)
        
        # Reset for next use
        self.buffer = ""
        self.last_output_pos = 0
        self.in_code_block = False
        self.current_code_content = ""
        self.current_code_lang = ""

def build_payload(user_input: str):
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 2048,
        "messages": [
            {"role": "user", "content": user_input}
        ]
    }

def stream_response(payload):
    """Stream response with improved markdown parsing"""
    try:
        r = requests.post(URL, json=payload, stream=True, timeout=30)
    except requests.exceptions.RequestException as e:
        console.print(f"[bold red]Connection Error:[/bold red] {e}")
        return

    if not r.ok:
        console.print(f"[bold red]HTTP {r.status_code}:[/bold red] {r.text}")
        return

    parser = SimpleStreamingMarkdownParser()
    response_started = False

    try:
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
                
            if not line.startswith("data:"):
                continue

            data = line[5:].strip()
            if data == "[DONE]":
                parser.finalize()
                console.print()  # Final newline
                break

            try:
                evt = json.loads(data)
            except json.JSONDecodeError as e:
                console.print(f"[dim red]JSON decode error: {e}[/dim red]")
                continue

            # Print model name once at start
            if evt.get("type") == "message_start" and not response_started:
                message = evt.get("message", {})
                model_name = message.get("model", "Unknown Model")
                console.print(f"\n[bold blue]{model_name}:[/bold blue]")
                response_started = True
                continue

            # Handle content streaming
            if evt.get("type") == "content_block_delta":
                delta = evt.get("delta", {})
                if delta.get("type") == "text_delta":
                    text = delta.get("text", "")
                    if text:
                        parser.feed(text)

            # Handle message completion
            if evt.get("type") == "message_stop":
                parser.finalize()
                console.print()
                break
                
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user[/bold red]")
    except Exception as e:
        console.print(f"\n[bold red]Stream processing error:[/bold red] {e}")
        parser.finalize()

if __name__ == "__main__":
    # Welcome message with better formatting
    welcome_panel = Panel(
        "[bold cyan]Talk To LLMs[/bold cyan]\n\n" +
        "Features:\n" +
        "• [green]Author: Ryan Ren[/green]\n\n" +
        "Commands:\n" +
        "• Type your message and press Enter\n" +
        "• Type [bold]'exit'[/bold], [bold]'quit'[/bold], or [bold]Ctrl+C[/bold] to exit",
        title="[bold green]Welcome[/bold green]",
        border_style="green",
        padding=(1, 2)
    )
    console.print(welcome_panel)
    console.print()
    
    try:
        while True:
            try:
                console.print("[bold green]❯[/bold green] ", end="")
                user_input = input().strip()
                
                if not user_input:
                    continue
                if user_input.lower() in {"exit", "quit", "q"}:
                    console.print("[bold cyan]Goodbye! 👋[/bold cyan]")
                    break
                    
                payload = build_payload(user_input)
                stream_response(payload)
                
            except EOFError:
                console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]")
                break
                
    except KeyboardInterrupt:
        console.print("\n[bold cyan]Goodbye! 👋[/bold cyan]")
        sys.exit(0)