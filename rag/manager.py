from __future__ import annotations

"""RAG manager: indexing, persistence, retrieval, and context formatting."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .indexer import NaiveIndexer


@dataclass
class RAGManager:
    index_path: str = "context/.rag_index.json"
    default_k: int = 3
    chunk_size: int = 1000
    overlap: int = 200
    char_cap: int = 6000
    enabled: bool = False
    index_type: str = "naive"
    _index_cache: Optional[Dict] = field(default=None, init=False, repr=False)

    # -------- internal helpers --------
    def _ensure_dir(self) -> None:
        d = Path(self.index_path).parent
        d.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Optional[Dict]:
        if self._index_cache is not None:
            return self._index_cache
        p = Path(self.index_path)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            self._index_cache = data
            return data
        except Exception:
            return None

    def _save_index(self, idx: Dict) -> None:
        self._ensure_dir()
        Path(self.index_path).write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
        self._index_cache = idx

    # -------- user-facing API --------
    def clear(self) -> None:
        self._index_cache = None
        try:
            Path(self.index_path).unlink(missing_ok=True)
        except Exception:
            pass

    def index(self, paths: List[str], *, index_type: str = "naive") -> Dict:
        self.index_type = index_type or "naive"
        if self.index_type != "naive":
            # Placeholder for future embedding-based indexers
            raise ValueError(f"Unsupported index type: {self.index_type}")

        indexer = NaiveIndexer(chunk_size=self.chunk_size, overlap=self.overlap)
        idx = indexer.build_index(paths)
        # Record type in meta
        idx.setdefault("meta", {})["type"] = self.index_type
        self._save_index(idx)
        return idx

    def search(self, query: str, *, k: Optional[int] = None) -> List[Dict]:
        idx = self._load_index()
        if not idx:
            return []
        indexer = NaiveIndexer(chunk_size=self.chunk_size, overlap=self.overlap)
        return indexer.search(idx, query, k=k or self.default_k)

    def format_context(self, results: List[Dict]) -> str:
        if not results:
            return ""
        parts: List[str] = ["<context>"]
        used = 0
        for r in results:
            text = (r.get("text") or "").strip()
            src = f"{r.get('path','')}#{r.get('start',0)}-{r.get('end',0)}"
            snippet = text
            # Truncate aggressively if needed
            if used + len(snippet) > self.char_cap:
                remaining = max(0, self.char_cap - used)
                snippet = snippet[:remaining]
            parts.append(f"<chunk src=\"{src}\">\n{snippet}\n</chunk>")
            used += len(snippet)
            if used >= self.char_cap:
                break
        parts.append("</context>")
        return "\n".join(parts)

    def search_and_format(self, query: str, *, k: Optional[int] = None) -> str:
        results = self.search(query, k=k)
        return self.format_context(results)

    def status(self) -> Dict:
        idx = self._load_index() or {}
        meta = idx.get("meta", {})
        return {
            "enabled": self.enabled,
            "type": self.index_type,
            "files": len(meta.get("files", [])),
            "chunks": meta.get("total_chunks", 0),
            "vocab": meta.get("vocab_size", 0),
            "chunk_size": self.chunk_size,
            "overlap": self.overlap,
            "k": self.default_k,
            "char_cap": self.char_cap,
            "indexed": bool(idx),
        }

