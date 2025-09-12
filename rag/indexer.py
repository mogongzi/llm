"""Naive TF-IDF indexer for simple local RAG.

Builds a lightweight index of text files, chunks them, and supports
query-time retrieval with cosine similarity over TF-IDF vectors.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


TOKEN_RE = re.compile(r"\b\w+\b", re.UNICODE)


DEFAULT_EXTS = {
    ".md", ".mdx", ".txt", ".rst",
    ".py", ".js", ".ts", ".tsx", ".json", ".yml", ".yaml",
    ".css", ".scss", ".html", ".xml"
}


@dataclass
class Chunk:
    path: str
    start: int
    end: int
    text: str
    tf: Dict[str, int]


class NaiveIndexer:
    def __init__(self, *, chunk_size: int = 1000, overlap: int = 200, max_file_bytes: int = 500_000,
                 exts: Iterable[str] = DEFAULT_EXTS) -> None:
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.max_file_bytes = max_file_bytes
        self.exts = set(exts)

    # -------- tokenization and chunking --------
    def tokenize(self, text: str) -> List[str]:
        return [t.lower() for t in TOKEN_RE.findall(text)]

    def _chunk_text(self, text: str) -> List[Tuple[int, int, str]]:
        if not text:
            return []
        chunks: List[Tuple[int, int, str]] = []
        i = 0
        n = len(text)
        size = max(1, self.chunk_size)
        overlap = max(0, min(self.overlap, size - 1))
        step = size - overlap
        while i < n:
            j = min(n, i + size)
            chunks.append((i, j, text[i:j]))
            if j >= n:
                break
            i = j - overlap
        return chunks

    def _is_text_file(self, path: Path) -> bool:
        if not path.is_file():
            return False
        if path.suffix.lower() not in self.exts:
            return False
        try:
            if path.stat().st_size > self.max_file_bytes:
                return False
        except OSError:
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                f.read(256)
            return True
        except Exception:
            return False

    def _iter_files(self, root: Path) -> Iterable[Path]:
        if root.is_file():
            if self._is_text_file(root):
                yield root
            return
        if root.is_dir():
            for p in root.rglob("*"):
                if self._is_text_file(p):
                    yield p

    # -------- indexing --------
    def build_index(self, paths: List[str]) -> Dict:
        chunks: List[Chunk] = []
        df: Dict[str, int] = {}
        files_meta: List[Dict] = []

        for p in paths:
            path = Path(p).resolve()
            for file in self._iter_files(path):
                try:
                    data = file.read_text(encoding="utf-8")
                except Exception:
                    continue
                # chunk
                for start, end, text in self._chunk_text(data):
                    tokens = self.tokenize(text)
                    if not tokens:
                        continue
                    tf: Dict[str, int] = {}
                    seen: set[str] = set()
                    for tok in tokens:
                        tf[tok] = tf.get(tok, 0) + 1
                        if tok not in seen:
                            df[tok] = df.get(tok, 0) + 1
                            seen.add(tok)
                    chunks.append(Chunk(str(file), start, end, text, tf))
                # meta per file
                try:
                    stat = file.stat()
                    files_meta.append({
                        "path": str(file),
                        "mtime": int(stat.st_mtime),
                        "size": int(stat.st_size),
                    })
                except OSError:
                    pass

        index = {
            "meta": {
                "type": "naive",
                "chunk_size": self.chunk_size,
                "overlap": self.overlap,
                "files": files_meta,
                "total_chunks": len(chunks),
                "vocab_size": len(df),
            },
            "df": df,
            "chunks": [
                {
                    "path": c.path,
                    "start": c.start,
                    "end": c.end,
                    "text": c.text,
                    "tf": c.tf,
                }
                for c in chunks
            ],
        }
        return index

    # -------- search --------
    def _idf(self, df: Dict[str, int], total_docs: int, tok: str) -> float:
        # Add-one smoothing
        d = df.get(tok, 0) + 1
        return 1.0 + (total_docs / d)

    def search(self, index: Dict, query: str, *, k: int = 3) -> List[Dict]:
        if not index or not query.strip():
            return []
        chunks = index.get("chunks", [])
        df = index.get("df", {})
        total_docs = max(1, len(chunks))

        # Query vector
        q_tokens = self.tokenize(query)
        if not q_tokens:
            return []
        q_tf: Dict[str, int] = {}
        for t in q_tokens:
            q_tf[t] = q_tf.get(t, 0) + 1

        # Compute weighted vectors for query
        q_weights: Dict[str, float] = {}
        for tok, cnt in q_tf.items():
            q_weights[tok] = cnt * self._idf(df, total_docs, tok)
        q_norm = sum(v * v for v in q_weights.values()) ** 0.5 or 1.0

        # Score each chunk
        scored: List[Tuple[float, Dict]] = []
        for c in chunks:
            tf: Dict[str, int] = c.get("tf", {})
            # Compute dot product between weighted vectors
            dot = 0.0
            d_norm_sq = 0.0
            for tok, q_w in q_weights.items():
                d_tf = tf.get(tok)
                if d_tf:
                    d_w = d_tf * self._idf(df, total_docs, tok)
                    dot += q_w * d_w
            # Compute document norm
            for tok, cnt in tf.items():
                idf = self._idf(df, total_docs, tok)
                w = cnt * idf
                d_norm_sq += w * w
            d_norm = (d_norm_sq ** 0.5) or 1.0
            score = dot / (q_norm * d_norm)
            if score > 0:
                scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        results: List[Dict] = []
        for score, c in scored[:k]:
            results.append({
                "score": float(score),
                "path": c["path"] if isinstance(c, dict) else c.path,
                "start": c["start"] if isinstance(c, dict) else c.start,
                "end": c["end"] if isinstance(c, dict) else c.end,
                "text": c["text"] if isinstance(c, dict) else c.text,
            })
        return results

