from __future__ import annotations

from typing import Any, Dict, List

import os
from .rails_runner import run_script_json


def list_callbacks_for_model(model: str, *, rails_root: str, timeout: float = 20.0) -> Dict[str, Any]:
    """Invoke the Ruby inspector to list callbacks, touches, and dependents for a model."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "rails", "callbacks_inspector.rb")
    return run_script_json(script_path, [model], rails_root=rails_root, timeout=timeout)


def format_callbacks_summary(data: Dict[str, Any]) -> str:
    """Produce a human-friendly summary resembling the requested numbered list."""
    model = data.get("model") or "Model"
    callbacks = data.get("callbacks") or []
    touches = data.get("touches") or []
    dependents = data.get("dependents") or []

    def filt(ev: str, kind: str):
        return [c for c in callbacks if c.get("event") == ev and (c.get("kind") or "") == kind]

    lines: List[str] = []
    n = 1

    # Validation lifecycle
    for ev in ("validation",):
        for kind in ("before", "around", "after"):
            for cb in filt(ev, kind):
                name = cb.get("filter") or "<proc>"
                lines.append(f"  {n}. {kind}_{ev} :{name}")
                n += 1

    # Save lifecycle
    for ev in ("save",):
        for kind in ("before", "around", "after"):
            for cb in filt(ev, kind):
                name = cb.get("filter") or "<proc>"
                lines.append(f"  {n}. {kind}_{ev} :{name}")
                n += 1

    # After commit callbacks (on: [:create, :update, :destroy])
    for cb in filt("commit", "after"):
        name = cb.get("filter") or "<proc>"
        on_opt = cb.get("options", {}).get("on")
        on_suffix = f" [on: {on_opt}]" if on_opt else ""
        lines.append(f"  {n}. after_commit :{name}{on_suffix}")
        n += 1

    # Touches (associations with touch: true)
    for t in touches:
        macro = t.get("macro")
        name = t.get("name")
        klass = t.get("class_name") or ""
        lines.append(f"  {n}. → touches: {klass or name} ({macro} :{name}, touch: true)")
        n += 1

    # Dependents (cascade behaviors)
    for d in dependents:
        macro = d.get("macro")
        name = d.get("name")
        klass = d.get("class_name") or ""
        dep = d.get("dependent")
        lines.append(f"  {n}. → cascades: {klass or name} ({macro} :{name}, dependent: :{dep})")
        n += 1

    header = f"{model}.save! will execute:\n"
    return header + "\n".join(lines) if lines else header + "  (no callbacks found)"

