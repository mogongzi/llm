from __future__ import annotations

import io
import time
from dataclasses import dataclass, field
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.live import Live
from rich.markdown import CodeBlock, Heading, Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from rich.spinner import Spinner


class _CodeBlockTight(CodeBlock):
    def __rich_console__(self, console, options):
        code = str(self.text).rstrip()
        syntax = Syntax(code, self.lexer_name, theme=self.theme, word_wrap=True, padding=(1, 0))
        yield syntax


class _HeadingLeft(Heading):
    def __rich_console__(self, console, options):
        text = self.text
        text.justify = "left"
        if self.tag == "h1":
            yield Panel(text, box=box.HEAVY, style="markdown.h1.border")
        else:
            if self.tag == "h2":
                yield Text("")
            yield text


class MarkdownStyled(Markdown):
    elements = {
        **Markdown.elements,
        "fence": _CodeBlockTight,
        "code_block": _CodeBlockTight,
        "heading_open": _HeadingLeft,
    }


@dataclass
class MarkdownStream:
    live: Optional[Live] = None
    when: float = 0.0
    min_delay: float = 1.0 / 20
    live_window: int = 6
    printed: List[str] = field(default_factory=list)
    last_rendered: List[str] = field(default_factory=list)
    console_ref: Optional[Console] = None
    waiting_active: bool = False
    waiting_message: str = ""
    thinking_buffer: List[str] = field(default_factory=list)
    response_buffer: List[str] = field(default_factory=list)
    in_thinking_phase: bool = False
    thinking_printed: bool = False

    def _render_md_lines(self, text: str) -> List[str]:
        buf = io.StringIO()
        # Use the live console's width (or provided console) so wrapping matches
        # the actual viewport. This greatly reduces reflow surprises.
        width = None
        try:
            if self.live and getattr(self.live, "console", None):
                width = self.live.console.size.width
            elif self.console_ref is not None:
                width = self.console_ref.size.width
        except Exception:
            width = None

        # Fallback to terminal size detection if available
        if width is None or width <= 80:
            try:
                import shutil
                term_size = shutil.get_terminal_size()
                if term_size.columns > 80:
                    width = term_size.columns
            except Exception:
                pass

        # Force a much more conservative width to prevent markdown truncation
        if width and width > 100:
            width = min(width, 100)  # Cap at 100 characters to force earlier wrapping

        if width is not None and width > 0:
            tmp = Console(file=buf, force_terminal=True, soft_wrap=True, width=width)
        else:
            tmp = Console(file=buf, force_terminal=True, soft_wrap=True)

        # Debug: Check what's being rendered for bullet points
        if "• Many dramatic" in text and "probabilities" in text:
            print(f"\n[RENDER] Input text length: {len(text)}")
            print(f"[RENDER] Width: {width}")
            print(f"[RENDER] Text around bullet: {repr(text[text.find('• Many'):text.find('• Many')+150])}")

        tmp.print(MarkdownStyled(text))
        rendered_output = buf.getvalue()

        # Debug: Check what comes out of markdown rendering
        if "• Many dramatic" in text and "probabilities" in text:
            lines = rendered_output.splitlines(keepends=True)
            print(f"[RENDER] Output lines: {len(lines)}")
            for i, line in enumerate(lines):
                if "Many dramatic" in line or "measu" in line:
                    print(f"[RENDER] Line {i}: {repr(line[:100])}")

        return buf.getvalue().splitlines(keepends=True)

    def _ensure_live(self):
        if not self.live:
            # Use provided console for Live so widths and styling align.
            self.live = Live(Text(""), refresh_per_second=1.0 / self.min_delay, console=self.console_ref)
            self.live.start()

    def stop(self):
        if self.live:
            try:
                self.live.update(Text(""))
                self.live.stop()
            except Exception:
                pass
            self.live = None

    def start_waiting(self, message: str = "Waiting for response…") -> None:
        """Show a distinct animated waiting indicator inside the live area.

        Uses a spinner + dim italic message, clearly different from model output.
        """
        if self.waiting_active:
            return
        self._ensure_live()
        self.waiting_active = True
        self.waiting_message = message
        spinner = Spinner("dots", text=Text(message, style="dim italic"), style="yellow")
        if self.live:
            self.live.update(spinner)
            self.live.refresh()

    def stop_waiting(self) -> None:
        if not self.waiting_active:
            return
        self.waiting_active = False
        self.waiting_message = ""
        if self.live:
            try:
                # Clear Live region fully and refresh so previous spinner text is removed
                self.live.update(Text(""))
                self.live.refresh()
            except Exception:
                pass
        # Reset pacing so the next content update isn't throttled
        self.when = 0.0

    def update(self, cumulative_text: str, final: bool = False) -> None:
        self._ensure_live()

        now = time.time()
        if not final and (now - self.when) < self.min_delay:
            return
        self.when = now

        t0 = time.time()
        lines = self._render_md_lines(cumulative_text)
        render_time = time.time() - t0
        self.min_delay = min(max(render_time * 10, 1.0 / 20), 2)

        total = len(lines)
        # Target number of lines we consider stable this frame (older than live_window)
        # Be much more aggressive about printing stable content to prevent Live widget truncation
        if total > 3:  # Once we have more than 3 lines
            target_stable = total if final else max(0, total - 2)  # Keep only last 2 lines in Live
        else:
            target_stable = total if final else 0  # Keep everything in Live for small content

        # Two-frame confirmation: Only freeze lines up to the longest common
        # prefix between the previous render and the current one. This prevents
        # freezing lines that still reflow as more tokens arrive.
        lcp_prev = 0
        if self.last_rendered:
            lim = min(len(self.last_rendered), len(lines))
            while lcp_prev < lim and self.last_rendered[lcp_prev] == lines[lcp_prev]:
                lcp_prev += 1
        else:
            # On first render, don't freeze anything unless final
            lcp_prev = 0

        # Compute longest common prefix between what we've already printed and new lines.
        # If previously printed lines are NOT a prefix of the new rendering, it means
        # upstream reflow affected earlier lines (e.g., due to different word breaks).
        # In that case, do not extend the printed region this frame; keep more in Live.
        already = len(self.printed)
        prefix_limit = min(already, total)
        common = 0
        while common < prefix_limit and self.printed[common] == lines[common]:
            common += 1

        # Effective stable region this frame must not invalidate the prefix guarantee.
        # - If we had divergence (common < already), we freeze the printed area at
        #   the common prefix and push the rest into the Live tail so nothing appears
        #   cut off.
        # - Otherwise, we can safely extend printed output up to target_stable.
        # Additionally, cap by lcp_prev so only lines confirmed stable across
        # consecutive renders are frozen. On final render, show everything.
        effective_stable = total if final else min(target_stable, lcp_prev)
        if common < already:
            # Reflow changed previously printed content; avoid extending.
            effective_stable = common

        # If waiting indicator is active and we now have any content, stop it
        if self.waiting_active and total > 0:
            self.stop_waiting()

        # While waiting and no content yet, keep the spinner visible
        if self.waiting_active and total == 0 and not final:
            return

        if final or effective_stable > 0:
            # Only print additional stable lines if what we've printed so far
            # is still a prefix of the new rendering.
            need = max(0, effective_stable - already)
            if need > 0:
                chunk = "".join(lines[already:effective_stable])
                if self.live:
                    self.live.console.print(Text.from_ansi(chunk))
                    self.printed = lines[:effective_stable]


        # Remember current render for the next frame's stability check
        self.last_rendered = lines

        if final:
            # Debug: Check final content before stopping
            final_content = "".join(self.response_buffer)
            if "emergent abilities" in final_content:
                print(f"\n[FINAL] Total response buffer chars: {len(final_content)}")
                print(f"[FINAL] Content around 'When': {repr(final_content[final_content.find('When'):final_content.find('When')+100])}")
            self.stop()
            return

        tail = "".join(lines[effective_stable:])
        if self.live:
            # Create a Text object that preserves the original rendering width
            tail_text = Text.from_ansi(tail)
            # Ensure the Live widget uses the same width as our console
            self.live.update(tail_text)




    def add_thinking(self, text: str) -> None:
        """Add thinking text and render it streamingly with Claude Code style."""
        if not self.in_thinking_phase:
            self.in_thinking_phase = True
            self.thinking_buffer = ["*Thinking...*\n\n"]
            # Print header immediately
            self._ensure_live()
            header = self._render_md_lines("*Thinking...*\n")
            if self.live:
                self.live.console.print(Text.from_ansi("".join(header), style="dim italic"))

        self.thinking_buffer.append(text)
        self._stream_thinking()

    def add_response(self, text: str) -> None:
        """Add response text and render it normally."""
        if self.in_thinking_phase:
            self._finalize_thinking()
            self.in_thinking_phase = False

        self.response_buffer.append(text)
        cumulative = "".join(self.response_buffer)


        # Use existing update logic for streaming response
        self.update(cumulative, final=False)

    def _stream_thinking(self) -> None:
        """Stream thinking content in real-time with dim italic style."""
        self._ensure_live()

        # Get current thinking content (skip header)
        current_thinking = "".join(self.thinking_buffer[1:])  # Skip "*Thinking...*\n\n"

        if current_thinking:
            # Apply same streaming logic as normal content
            now = time.time()
            if (now - self.when) < self.min_delay:
                return
            self.when = now

            # Render and display thinking content
            lines = self._render_md_lines(current_thinking)
            tail_content = "".join(lines[-self.live_window:])  # Show live window

            # Display with dim italic style
            styled_text = Text.from_ansi(tail_content, style="dim italic")
            if self.live:
                self.live.update(styled_text)

    def _finalize_thinking(self) -> None:
        """Finalize thinking section and prepare for response."""
        if self.in_thinking_phase and self.live:
            # Print final thinking content
            current_thinking = "".join(self.thinking_buffer[1:])
            if current_thinking:
                lines = self._render_md_lines(current_thinking)
                final_content = "".join(lines)
                self.live.console.print(Text.from_ansi(final_content, style="dim italic"))

            # Add separator line
            self.live.console.print(Text(""))

            # Reset live area for response
            self.live.update(Text(""))
