from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional
from pathlib import Path

from .code_search import rg_search, read_file


def _underscore(name: str) -> str:
    s1 = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _controller_candidates(rails_root: Path, model: str) -> List[Path]:
    u = _underscore(model)
    pats = [f"app/controllers/**/*{u}*controller.rb", "app/controllers/**/*application_controller.rb"]
    out: List[Path] = []
    for pat in pats:
        out.extend(rails_root.glob(pat))
    return out


CALL_PATTERN_TOKENS = [
    r"[A-Za-z_:@][\w:@]*(?:\.[\w!?]+)*\s*\(",  # Foo.bar(
    r"redirect_to\b",
    r"render\b",
    r"flash\[[^\]]+\]",
    r"head\b",
]
CALL_RE = re.compile("|".join(f"(?:{p})" for p in CALL_PATTERN_TOKENS))


def _collect_calls_after(lines: List[str], start_idx: int) -> List[Dict[str, Any]]:
    calls: List[Dict[str, Any]] = []
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if re.match(r"^\s*end\b", line):
            break
        m = CALL_RE.search(line)
        if m:
            calls.append({"line": i + 1, "code": line.strip()})
    return calls


def analyze_after_persist(model: str, verb: str = "create", *, rails_root: str, max_results: int = 5) -> Dict[str, Any]:
    """
    Heuristic static analysis: find controller/action code invoked after a persist event on model.
    Returns structured data to be summarized by the caller.
    """
    root = Path(rails_root)
    results: List[Dict[str, Any]] = []

    # 1) Direct create usages: Model.create( / create!(
    patterns = [
        rf"{re.escape(model)}\.create!?\s*\(",
        rf"{re.escape(model)}\.new\s*\(",  # for new + save pattern
    ]
    matches = []
    for pat in patterns:
        matches.extend(rg_search(str(root), pat, globs=["*.rb"]))

    # 2) Controller focus: open methods around def create/update
    controller_files = _controller_candidates(root, model)
    for f in controller_files:
        try:
            text = Path(f).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if re.match(rf"^\s*def\s+{verb}\b", line):
                # Search within method for save/create lines
                # naive find end
                end = i + 1
                depth = 1
                while end < len(lines):
                    if re.match(r"^\s*def\b", lines[end]):
                        depth += 1
                    if re.match(r"^\s*end\b", lines[end]):
                        depth -= 1
                        if depth == 0:
                            break
                    end += 1
                body = lines[i:end+1]
                # find create/save
                save_idx = None
                for j, l in enumerate(body):
                    if re.search(r"\.save!?\b", l) or re.search(rf"{re.escape(model)}\.create!?\b", l):
                        save_idx = j
                        break
                if save_idx is not None:
                    calls = _collect_calls_after(body, save_idx)
                    if calls:
                        results.append({
                            "file": str(f),
                            "action": verb,
                            "calls": calls,
                        })

    # 3) If still empty, use direct matches to open a local window and extract calls that follow
    if not results and matches:
        for m in matches[:max_results]:
            p = Path(m['file'])
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            lines = text.splitlines()
            idx = m['line'] - 1
            calls = []
            for i in range(idx + 1, min(len(lines), idx + 40)):
                line = lines[i]
                mm = CALL_RE.search(line)
                if mm:
                    calls.append({"line": i + 1, "code": line.strip()})
            if calls:
                results.append({"file": str(p), "calls": calls})

    return {
        "model": model,
        "verb": verb,
        "results": results,
    }


def format_flow_summary(data: Dict[str, Any]) -> str:
    model = data.get("model")
    verb = data.get("verb")
    parts: List[str] = [f"Likely methods invoked after {model}.{verb}:\n"]
    n = 1
    for r in data.get("results", []):
        file = r.get("file")
        for c in r.get("calls", []):
            code = c.get("code")
            parts.append(f"  {n}. {code}  [{file}:{c.get('line')}]")
            n += 1
    if n == 1:
        parts.append("  (no obvious post-persist calls found)")
    return "\n".join(parts)

