"""
Rails-specific RAG (Retrieval-Augmented Generation) system.

This package provides specialized code analysis and retrieval capabilities
for Ruby on Rails applications, separate from the general-purpose naive RAG
implementation.

Components:
- manager.py: Rails RAG manager with multi-modal indexing
- indexer.py: Code-specific indexing with AST and symbol analysis
- searcher.py: Multi-tier search engine (Symbol → Structural → Semantic)
- embeddings.py: Code embeddings using CodeBERT or local models
"""

from .manager import RailsRAGManager
from .indexer import RailsCodeIndexer
from .searcher import RailsCodeSearcher

__all__ = ['RailsRAGManager', 'RailsCodeIndexer', 'RailsCodeSearcher']