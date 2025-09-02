from __future__ import annotations

import io
import time
from dataclasses import dataclass
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.live import Live
from rich.markdown import CodeBlock, Heading, Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text


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
    printed: List[str] = None

    def __post_init__(self):
        self.printed = []

    def _render_md_lines(self, text: str) -> List[str]:
        buf = io.StringIO()
        tmp = Console(file=buf, force_terminal=True, soft_wrap=True)
        tmp.print(MarkdownStyled(text))
        return buf.getvalue().splitlines(keepends=True)

    def _ensure_live(self):
        if not self.live:
            self.live = Live(Text(""), refresh_per_second=1.0 / self.min_delay)
            self.live.start()

    def stop(self):
        if self.live:
            try:
                self.live.update(Text(""))
                self.live.stop()
            except Exception:
                pass
            self.live = None

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
        stable = total if final else max(0, total - self.live_window)

        if final or stable > 0:
            already = len(self.printed)
            need = stable - already
            if need > 0:
                chunk = "".join(lines[already:stable])
                self.live.console.print(Text.from_ansi(chunk))
                self.printed = lines[:stable]

        if final:
            self.stop()
            return

        tail = "".join(lines[stable:])
        self.live.update(Text.from_ansi(tail))

