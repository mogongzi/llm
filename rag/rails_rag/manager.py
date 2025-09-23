"""
Rails RAG Manager - Multi-modal code indexing and retrieval.

Manages Rails-specific code analysis with multiple indexing strategies:
- Structural indexing (AST-based)
- Symbol indexing (definitions, references)
- Semantic indexing (code embeddings)
- Convention-based indexing (Rails patterns)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any

from .indexer import RailsCodeIndexer
from .searcher import RailsCodeSearcher


@dataclass
class RailsRAGManager:
    """
    Manages Rails-specific code indexing and retrieval.

    Separate from the naive RAG system, this provides intelligent
    code analysis with understanding of Rails conventions and
    multi-modal search capabilities.
    """

    project_root: str = "."
    index_path: str = "cache/rails_rag_index.json"
    enabled: bool = False

    # Index configuration
    use_structural_index: bool = True
    use_symbol_index: bool = True
    use_semantic_index: bool = True
    use_convention_index: bool = True

    # Performance settings
    max_file_size: int = 1024 * 1024  # 1MB per file
    max_results: int = 50
    semantic_similarity_threshold: float = 0.7

    # Internal components
    _indexer: Optional[RailsCodeIndexer] = field(default=None, init=False, repr=False)
    _searcher: Optional[RailsCodeSearcher] = field(default=None, init=False, repr=False)
    _index_cache: Optional[Dict] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        """Initialize components after dataclass creation."""
        self.project_root = Path(self.project_root).resolve()
        self._indexer = RailsCodeIndexer(
            project_root=str(self.project_root),
            max_file_size=self.max_file_size
        )
        self._searcher = RailsCodeSearcher(
            project_root=str(self.project_root),
            max_results=self.max_results,
            similarity_threshold=self.semantic_similarity_threshold
        )

    def _ensure_cache_dir(self) -> None:
        """Ensure cache directory exists."""
        cache_dir = Path(self.index_path).parent
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Optional[Dict]:
        """Load existing index from disk."""
        if self._index_cache is not None:
            return self._index_cache

        index_file = Path(self.index_path)
        if not index_file.exists():
            return None

        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._index_cache = data
            return data
        except Exception:
            return None

    def _save_index(self, index_data: Dict) -> None:
        """Save index to disk."""
        self._ensure_cache_dir()
        try:
            with open(self.index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            self._index_cache = index_data
        except Exception as e:
            print(f"Error saving Rails RAG index: {e}")

    def index_project(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """
        Build comprehensive index of Rails project.

        Args:
            force_rebuild: Force complete rebuild even if index exists

        Returns:
            Index statistics and metadata
        """
        if not self._indexer:
            raise RuntimeError("Rails RAG Manager not properly initialized")

        # Check if we need to rebuild
        existing_index = self._load_index()
        if existing_index and not force_rebuild:
            # Check if index is still valid (simple timestamp check)
            index_time = existing_index.get("metadata", {}).get("created_at", 0)
            if time.time() - index_time < 3600:  # 1 hour freshness
                return existing_index.get("metadata", {})

        print("Building Rails code index...")
        start_time = time.time()

        # Build multi-modal index
        index_components = {}

        if self.use_structural_index:
            print("  - Building structural index...")
            index_components["structural"] = self._indexer.build_structural_index()

        if self.use_symbol_index:
            print("  - Building symbol index...")
            index_components["symbols"] = self._indexer.build_symbol_index()

        if self.use_convention_index:
            print("  - Building Rails convention index...")
            index_components["conventions"] = self._indexer.build_convention_index()

        if self.use_semantic_index:
            print("  - Building semantic index...")
            index_components["semantic"] = self._indexer.build_semantic_index()

        # Combine into final index
        final_index = {
            "components": index_components,
            "metadata": {
                "created_at": time.time(),
                "build_time": time.time() - start_time,
                "project_root": str(self.project_root),
                "version": "1.0.0",
                "enabled_features": {
                    "structural": self.use_structural_index,
                    "symbols": self.use_symbol_index,
                    "conventions": self.use_convention_index,
                    "semantic": self.use_semantic_index,
                }
            }
        }

        # Save to disk
        self._save_index(final_index)

        build_time = time.time() - start_time
        print(f"Rails index built in {build_time:.2f}s")

        return final_index["metadata"]

    def search(self, query: str, query_type: str = "auto") -> List[Dict[str, Any]]:
        """
        Search Rails codebase with multi-modal retrieval.

        Args:
            query: Search query (SQL, natural language, or code pattern)
            query_type: Type of search ("sql", "semantic", "symbol", "auto")

        Returns:
            List of ranked search results
        """
        if not self.enabled:
            return []

        if not self._searcher:
            raise RuntimeError("Rails RAG Manager not properly initialized")

        # Load index
        index_data = self._load_index()
        if not index_data:
            print("No Rails index found. Run index_project() first.")
            return []

        # Delegate to searcher
        return self._searcher.search(
            query=query,
            index_data=index_data,
            query_type=query_type
        )

    def search_sql(self, sql_query: str) -> List[Dict[str, Any]]:
        """Search for code related to a specific SQL query."""
        return self.search(sql_query, query_type="sql")

    def search_semantic(self, description: str) -> List[Dict[str, Any]]:
        """Search for code using semantic similarity."""
        return self.search(description, query_type="semantic")

    def search_symbol(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Search for symbol definitions and references."""
        return self.search(symbol_name, query_type="symbol")

    def clear_index(self) -> None:
        """Clear the Rails RAG index."""
        self._index_cache = None
        index_file = Path(self.index_path)
        if index_file.exists():
            index_file.unlink()
        print("Rails RAG index cleared")

    def status(self) -> Dict[str, Any]:
        """Get current Rails RAG status."""
        index_data = self._load_index()

        status = {
            "enabled": self.enabled,
            "project_root": str(self.project_root),
            "index_exists": index_data is not None,
            "features": {
                "structural": self.use_structural_index,
                "symbols": self.use_symbol_index,
                "conventions": self.use_convention_index,
                "semantic": self.use_semantic_index,
            }
        }

        if index_data:
            metadata = index_data.get("metadata", {})
            status["index_info"] = {
                "created_at": metadata.get("created_at"),
                "build_time": metadata.get("build_time"),
                "version": metadata.get("version"),
            }

            # Add component statistics
            components = index_data.get("components", {})
            status["statistics"] = {}
            for component_name, component_data in components.items():
                if isinstance(component_data, dict):
                    status["statistics"][component_name] = {
                        "files": len(component_data.get("files", [])),
                        "entries": len(component_data.get("entries", [])),
                    }

        return status

    def enable(self) -> None:
        """Enable Rails RAG system."""
        self.enabled = True
        print("Rails RAG enabled")

    def disable(self) -> None:
        """Disable Rails RAG system."""
        self.enabled = False
        print("Rails RAG disabled")