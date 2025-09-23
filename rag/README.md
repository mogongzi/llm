# RAG (Retrieval-Augmented Generation) Systems

This directory contains different RAG implementations for various use cases:

## Directory Structure

```
rag/
├── __init__.py              # Main RAG imports (currently naive RAG)
├── README.md               # This file
├── naive/                  # Simple TF-IDF based RAG
│   ├── __init__.py
│   ├── manager.py          # Original RAG manager
│   └── indexer.py          # TF-IDF indexer
└── rails_rag/              # Rails-specific code analysis RAG
    ├── __init__.py
    ├── manager.py          # Rails RAG manager
    ├── indexer.py          # Multi-modal code indexer
    ├── searcher.py         # Multi-tier search engine
    └── embeddings.py       # Code embeddings
```

## RAG Systems

### Naive RAG (`naive/`)

Simple TF-IDF based document retrieval system:
- **Use case**: General document search and retrieval
- **Indexing**: TF-IDF with chunking
- **Search**: Cosine similarity over TF-IDF vectors
- **Performance**: Fast, lightweight, no external dependencies

```python
from rag import RAGManager  # Uses naive implementation

rag = RAGManager()
rag.index(["path/to/documents"])
results = rag.search("query text")
```

### Rails RAG (`rails_rag/`)

Specialized code analysis system for Ruby on Rails:
- **Use case**: Rails code analysis and SQL-to-code mapping
- **Indexing**: Multi-modal (structural, symbol, semantic, convention)
- **Search**: Multi-tier search with Rails convention understanding
- **Performance**: Optimized for large codebases, supports external tools

```python
from rag.rails_rag.manager import RailsRAGManager

rails_rag = RailsRAGManager(project_root="path/to/rails/app")
rails_rag.index_project()
results = rails_rag.search_sql("SELECT * FROM users")
```

## Usage Patterns

### CLI Integration

Both RAG systems integrate with the main CLI:

```bash
# Naive RAG commands
/rag index naive path/to/docs
/rag search "query text"
/rag on|off

# Rails RAG commands (via Rails agent)
/agent on
/agent index
/agent analyze "SELECT * FROM shopping_cart"
```

### Programmatic Usage

```python
# Import the default (naive) RAG
from rag import RAGManager

# Import specific RAG systems
from rag.naive.manager import RAGManager as NaiveRAG
from rag.rails_rag.manager import RailsRAGManager

# Use appropriate system for your needs
doc_rag = NaiveRAG()           # For documents
code_rag = RailsRAGManager()   # For Rails code
```

## Migration from Old Structure

The RAG components have been reorganized:

**Before:**
- `rag/manager.py` → `rag/naive/manager.py`
- `rag/indexer.py` → `rag/naive/indexer.py`

**After:**
- Main import still works: `from rag import RAGManager`
- Direct imports updated: `from rag.naive.manager import RAGManager`

## Adding New RAG Systems

To add a new RAG implementation:

1. Create a new directory: `rag/your_rag/`
2. Implement manager with common interface:
   - `index()` - Build search index
   - `search()` - Query the index
   - `status()` - Get index status
3. Add to main `__init__.py` if desired
4. Update CLI integration if needed

## Performance Comparison

| Feature | Naive RAG | Rails RAG |
|---------|-----------|-----------|
| Index Speed | Fast (seconds) | Moderate (minutes) |
| Search Speed | Very Fast (<100ms) | Fast (<2s) |
| Memory Usage | Low (10-50MB) | Moderate (100-500MB) |
| Dependencies | None | Optional (numpy, transformers) |
| Use Case | Documents | Rails Code |
| Precision | Good | Excellent (for Rails) |

Choose the appropriate RAG system based on your specific needs.