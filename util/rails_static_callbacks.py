from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Set


# Regex patterns for callbacks and associations
CALLBACK_FN = re.compile(
    r"^\s*(before|after|around)_(validation|save|create|update|destroy|touch|commit|rollback)\s*(\(.*?\))?\s*(.*)$"
)

# after_create_commit / after_update_commit / after_destroy_commit
AFTER_X_COMMIT = re.compile(r"^\s*after_(create|update|destroy)_commit\s*(\(.*?\))?\s*(.*)$")

# set_callback :save, :before, :method, on: :create
SET_CALLBACK = re.compile(
    r"^\s*set_callback\s*:(validation|save|create|update|destroy|commit|rollback|touch)\s*,\s*:(before|after|around)\s*,\s*([^#\n]+)"
)

ASSOC = re.compile(r"^\s*(belongs_to|has_one|has_many)\s+:([a-zA-Z_][a-zA-Z0-9_]*)\s*(.*)$")
INCLUDE_MOD = re.compile(r"^\s*include\s+([A-Za-z_][A-Za-z0-9_:]*)\s*(#.*)?$")


def _extract_symbols(arg_str: str) -> List[str]:
    if not arg_str:
        return []
    # symbols like :foo, :bar or [:a, :b] or proc/block
    names = re.findall(r":([a-zA-Z_][a-zA-Z0-9_]*)", arg_str)
    return list(dict.fromkeys(names))


def _extract_options(arg_str: str) -> Dict[str, Any]:
    opts: Dict[str, Any] = {}
    if not arg_str:
        return opts
    m_on = re.search(r"on:\s*:(create|update|destroy)", arg_str)
    if m_on:
        opts["on"] = m_on.group(1)
    m_if = re.search(r"\bif:\s*([^,\)]+)", arg_str)
    if m_if:
        opts["if"] = m_if.group(1).strip()
    m_unless = re.search(r"\bunless:\s*([^,\)]+)", arg_str)
    if m_unless:
        opts["unless"] = m_unless.group(1).strip()
    return opts


def _parse_callback_line(line: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    m = CALLBACK_FN.match(line)
    if m:
        kind, event, _paren, rest = m.groups()
        names = _extract_symbols(rest)
        if not names:
            # Block/proc case
            names = ["<block>"]
        opts = _extract_options(rest)
        for name in names:
            out.append({"event": event, "kind": kind, "filter": name, "options": opts})
        return out

    mx = AFTER_X_COMMIT.match(line)
    if mx:
        which, _paren, rest = mx.groups()
        names = _extract_symbols(rest) or ["<block>"]
        opts = _extract_options(rest)
        opts = {**opts, "on": which}
        for name in names:
            out.append({"event": "commit", "kind": "after", "filter": name, "options": opts})
        return out

    ms = SET_CALLBACK.match(line)
    if ms:
        event, kind, rest = ms.groups()
        names = _extract_symbols(rest) or ["<block>"]
        opts = _extract_options(rest)
        for name in names:
            out.append({"event": event, "kind": kind, "filter": name, "options": opts})
        return out

    return out


def _parse_assoc_line(line: str) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    m = ASSOC.match(line)
    if not m:
        return None, None
    macro, name, rest = m.groups()
    # touch: true
    touch = re.search(r"\btouch:\s*true\b", rest)
    dep = re.search(r"\bdependent:\s*:(destroy|delete|delete_all|nullify|restrict_with_error|restrict_with_exception)\b", rest)
    class_name = None
    mcn = re.search(r"\bclass_name:\s*['\"]([^'\"]+)['\"]", rest)
    if mcn:
        class_name = mcn.group(1)
    touches = {"name": name, "macro": macro, "class_name": class_name, "options": {"touch": True}} if touch else None
    depend = {"name": name, "macro": macro, "class_name": class_name, "dependent": dep.group(1)} if dep else None
    return touches, depend


def _underscore(name: str) -> str:
    # Very simple underscore for CamelCase
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _module_to_path(mod: str) -> str:
    parts = mod.split("::")
    return "/".join(_underscore(p) for p in parts)


def _find_model_files(rails_root: Path, model: str) -> List[Path]:
    # Prefer app/models/**/model.rb
    candidates = list(rails_root.glob(f"app/models/**/*{_underscore(model)}.rb"))
    # Filter by containing class definition
    out: List[Path] = []
    class_re = re.compile(rf"class\s+(?:[A-Za-z0-9_:]*::)?{re.escape(model)}\s*<")
    for p in candidates:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if class_re.search(text):
            out.append(p)
    return out


def _find_concern_files(rails_root: Path, includes: List[str]) -> List[Path]:
    files: List[Path] = []
    conc_root = rails_root / "app/models/concerns"
    for mod in includes:
        rel = _module_to_path(mod) + ".rb"
        p = conc_root / rel
        if p.exists():
            files.append(p)
        else:
            # Try a loose search
            for cand in conc_root.glob("**/*.rb"):
                if cand.name == rel.split("/")[-1]:
                    files.append(cand)
    # Dedup
    seen: Set[Path] = set()
    uniq = []
    for p in files:
        if p not in seen:
            uniq.append(p)
            seen.add(p)
    return uniq


def scan_model_static(model: str, *, rails_root: str) -> Dict[str, Any]:
    root = Path(rails_root)
    callbacks: List[Dict[str, Any]] = []
    touches: List[Dict[str, Any]] = []
    dependents: List[Dict[str, Any]] = []
    includes: List[str] = []

    model_files = _find_model_files(root, model)
    searched_files: List[Path] = []

    def scan_file(path: Path):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return
        for i, line in enumerate(lines, start=1):
            # Callbacks
            for cb in _parse_callback_line(line):
                cb.update({"source_file": str(path), "source_line": i})
                callbacks.append(cb)
            # Associations
            t, d = _parse_assoc_line(line)
            if t:
                t.update({})
                touches.append(t)
            if d:
                dependents.append(d)
            # Includes
            m = INCLUDE_MOD.match(line)
            if m:
                includes.append(m.group(1))

    for p in model_files:
        searched_files.append(p)
        scan_file(p)

    # Scan included concerns
    concern_files = _find_concern_files(root, includes)
    for p in concern_files:
        searched_files.append(p)
        scan_file(p)

    return {
        "model": model,
        "callbacks": callbacks,
        "touches": touches,
        "dependents": dependents,
        "searched_files": [str(p) for p in searched_files],
    }

