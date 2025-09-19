from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, Optional


class SearchError(RuntimeError):
    pass


def rg_available() -> bool:
    from shutil import which
    return which("rg") is not None


def rg_search(
    root: str,
    query: str,
    *,
    globs: Optional[List[str]] = None,
    max_results: int = 200,
    context_lines: int = 0,
) -> List[Dict[str, Any]]:
    """
    Run ripgrep in the given root and return structured matches.
    """
    if not os.path.isdir(root):
        raise SearchError(f"Search root not found: {root}")

    if not rg_available():
        # Fallback: very naive grep via Python; slow for big repos but better than nothing
        results: List[Dict[str, Any]] = []
        for base, _dirs, files in os.walk(root):
            for fn in files:
                if not fn.endswith(('.rb', '.erb', '.haml', '.slim', '.rake', '.yml', '.yaml', '.js', '.ts', '.vue', '.coffee', '.scss', '.css', '.html')):
                    continue
                path = os.path.join(base, fn)
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, start=1):
                    if query in line:
                        before = ''.join(lines[max(1, i - context_lines) - 1:i - 1]) if context_lines else ''
                        after = ''.join(lines[i:min(len(lines), i + context_lines)]) if context_lines else ''
                        results.append({
                            'file': path,
                            'line': i,
                            'column': max(1, line.find(query) + 1),
                            'match': line.rstrip('\n'),
                            'before': before,
                            'after': after,
                        })
                        if len(results) >= max_results:
                            return results
        return results

    cmd = [
        "rg",
        "--line-number",
        "--column",
        "--no-heading",
        "--json",
        f"--max-count={max_results}",
    ]
    if context_lines:
        cmd.append(f"-C{context_lines}")
    if globs:
        for g in globs:
            cmd.extend(["-g", g])
    cmd.append(query)
    cmd.append(root)

    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode not in (0, 1):  # 1 means no matches
        raise SearchError(proc.stderr.strip())

    results: List[Dict[str, Any]] = []
    import json
    for line in proc.stdout.splitlines():
        try:
            evt = json.loads(line)
        except Exception:
            continue
        if evt.get('type') == 'match':
            data = evt['data']
            m = data['lines']['text'].rstrip('\n')
            path = data['path']['text']
            line_no = data['line_number']
            col = data['absolute_offset']  # not ideal; next prefer submatch
            subs = data.get('submatches') or []
            col = (subs[0]['start'] + 1) if subs else 1
            before = ''
            after = ''
            if context_lines:
                # context events are separate; easier: skip for now in rg path
                pass
            results.append({'file': path, 'line': line_no, 'column': col, 'match': m, 'before': before, 'after': after})
    return results


def read_file(path: str, *, start: int = 1, end: Optional[int] = None, max_bytes: int = 200_000) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read(max_bytes)
    lines = content.splitlines()
    if end is None:
        end = len(lines)
    start = max(1, start)
    end = min(len(lines), end)
    snippet = "\n".join(lines[start - 1:end])
    return {
        'file': path,
        'start': start,
        'end': end,
        'text': snippet,
    }

