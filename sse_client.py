from __future__ import annotations

from typing import Dict, Iterator, Optional

import requests


def iter_sse_lines(
    url: str,
    *,
    method: str = "POST",
    json: Optional[dict] = None,
    params: Optional[Dict[str, str]] = None,
    timeout: float = 60.0,
    session: Optional[requests.Session] = None,
) -> Iterator[str]:
    """Yield SSE data lines from an HTTP response.

    Strips the leading "data:" prefix when present and skips empty keep-alive lines.
    """
    sse_session = session or requests.Session()
    req = sse_session.get if method.upper() == "GET" else sse_session.post
    with req(url, json=json, params=params, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw:
                continue
            yield raw[5:].lstrip() if raw.startswith("data:") else raw
