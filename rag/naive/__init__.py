"""
Naive RAG Implementation.

Simple TF-IDF based retrieval-augmented generation system for local documents.
This is the original implementation, now organized in its own module.
"""

from .manager import RAGManager
from .indexer import NaiveIndexer

__all__ = ['RAGManager', 'NaiveIndexer']