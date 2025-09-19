from __future__ import annotations

import re
from typing import Dict, List


class RoutedTool:
    def __init__(self, name: str, input: Dict):
        self.name = name
        self.input = input


def detect_tools_for_query(text: str) -> List[RoutedTool]:
    """Return a list of tool invocations that likely satisfy the query.

    Simple regex-based router for common Rails tasks.
    """
    t = text.strip()
    out: List[RoutedTool] = []

    # Extract Model.verb like Order.create / Order.save
    m = re.search(r"\b([A-Z][A-Za-z0-9_:]*)\.(create|save|update|destroy)\b", t)
    model = m.group(1) if m else None
    verb = m.group(2) if m else None

    # Callbacks intent
    if re.search(r"\bcallbacks?\b|\binvoked methods\b.*after\s+save", t, re.I):
        if model:
            out.append(RoutedTool("rails_callbacks", {"model": model}))
            return out

    # Post-persist flow intent
    if re.search(r"\b(after|when)\b.*\b(create|save|update|destroy)\b.*\b(methods|invoked|called)\b", t, re.I):
        if model:
            out.append(RoutedTool("rails_flow_after_persist", {"model": model, "verb": verb or "create"}))
            return out

    return out

