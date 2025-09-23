"""
Code Embeddings for Rails RAG System.

Provides code embedding capabilities using various models:
- CodeBERT: Microsoft's pre-trained model for code understanding
- StarCoder: Hugging Face's code generation model
- Local embeddings: Sentence transformers for code similarity

This module will be enhanced to provide semantic code search capabilities.
"""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
try:
    import numpy as np
except ImportError:
    # Fallback for environments without numpy
    print("Warning: numpy not available. Code embeddings will use basic similarity.")
    np = None


class CodeEmbedder:
    """
    Base class for code embedding models.

    Provides interface for different embedding backends
    with caching and similarity search capabilities.
    """

    def __init__(self, cache_dir: str = "cache/embeddings"):
        """
        Initialize code embedder.

        Args:
            cache_dir: Directory for caching embeddings
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = "base"

    def encode(self, code_snippets: List[str]):
        """
        Encode code snippets into embeddings.

        Args:
            code_snippets: List of code strings to encode

        Returns:
            Array of embeddings with shape (n_snippets, embedding_dim)
        """
        raise NotImplementedError("Subclasses must implement encode method")

    def similarity(self, embedding1, embedding2) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Cosine similarity score between 0 and 1
        """
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)

    def _get_cache_path(self, content: str) -> Path:
        """Get cache file path for content."""
        content_hash = hashlib.md5(content.encode()).hexdigest()
        return self.cache_dir / f"{self.model_name}_{content_hash}.pkl"

    def _load_from_cache(self, content: str):
        """Load embedding from cache if available."""
        cache_path = self._get_cache_path(content)
        if cache_path.exists():
            try:
                with open(cache_path, 'rb') as f:
                    return pickle.load(f)
            except Exception:
                pass
        return None

    def _save_to_cache(self, content: str, embedding) -> None:
        """Save embedding to cache."""
        cache_path = self._get_cache_path(content)
        try:
            with open(cache_path, 'wb') as f:
                pickle.dump(embedding, f)
        except Exception:
            pass  # Silent failure for caching


class SimpleEmbedder(CodeEmbedder):
    """
    Simple embedding model using basic text features.

    Fallback embedder that doesn't require external dependencies.
    Uses basic text statistics and keyword presence for similarity.
    """

    def __init__(self, cache_dir: str = "cache/embeddings"):
        super().__init__(cache_dir)
        self.model_name = "simple"

    def encode(self, code_snippets: List[str]):
        """Encode using simple text features."""
        embeddings = []

        for snippet in code_snippets:
            # Check cache first
            cached = self._load_from_cache(snippet)
            if cached is not None:
                embeddings.append(cached)
                continue

            # Compute simple features
            features = self._extract_features(snippet)
            embedding = np.array(features, dtype=np.float32)

            # Cache the result
            self._save_to_cache(snippet, embedding)
            embeddings.append(embedding)

        return np.array(embeddings)

    def _extract_features(self, code: str) -> List[float]:
        """Extract simple features from code."""
        features = []

        # Basic statistics
        features.append(len(code))  # Length
        features.append(len(code.split('\n')))  # Line count
        features.append(len(code.split()))  # Word count

        # Ruby/Rails keywords
        ruby_keywords = [
            'class', 'def', 'end', 'if', 'else', 'elsif', 'unless', 'case', 'when',
            'while', 'for', 'do', 'break', 'next', 'return', 'yield', 'super',
            'self', 'true', 'false', 'nil', 'and', 'or', 'not', 'begin', 'rescue',
            'ensure', 'module', 'include', 'extend', 'require', 'load'
        ]

        rails_keywords = [
            'has_many', 'belongs_to', 'has_one', 'validates', 'before_action',
            'after_action', 'before_save', 'after_save', 'scope', 'find', 'where',
            'create', 'update', 'destroy', 'params', 'render', 'redirect_to',
            'respond_to', 'format', 'json', 'html', 'xml'
        ]

        # Count keyword occurrences (normalized)
        code_lower = code.lower()
        for keyword in ruby_keywords:
            count = code_lower.count(keyword)
            features.append(count / max(1, len(code.split())))

        for keyword in rails_keywords:
            count = code_lower.count(keyword)
            features.append(count / max(1, len(code.split())))

        # Code structure indicators
        features.append(code.count('{'))  # Blocks
        features.append(code.count('('))  # Method calls
        features.append(code.count('['))  # Arrays
        features.append(code.count('.'))  # Method chaining
        features.append(code.count(':'))  # Symbols
        features.append(code.count('@'))  # Instance variables
        features.append(code.count('$'))  # Global variables

        return features


class CodeBERTEmbedder(CodeEmbedder):
    """
    CodeBERT-based embedder for code understanding.

    Uses Microsoft's CodeBERT model for generating code embeddings.
    Requires transformers library and model download.
    """

    def __init__(self, cache_dir: str = "cache/embeddings"):
        super().__init__(cache_dir)
        self.model_name = "codebert"
        self.model = None
        self.tokenizer = None
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize CodeBERT model if available."""
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch

            model_name = "microsoft/codebert-base"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.eval()

            print(f"Initialized CodeBERT model: {model_name}")

        except ImportError:
            print("CodeBERT requires transformers library. Install with: pip install transformers torch")
            self.model = None
        except Exception as e:
            print(f"Error initializing CodeBERT: {e}")
            self.model = None

    def encode(self, code_snippets: List[str]):
        """Encode using CodeBERT model."""
        if self.model is None:
            # Fallback to simple embedder
            fallback = SimpleEmbedder(str(self.cache_dir))
            return fallback.encode(code_snippets)

        embeddings = []

        for snippet in code_snippets:
            # Check cache first
            cached = self._load_from_cache(snippet)
            if cached is not None:
                embeddings.append(cached)
                continue

            # Encode with CodeBERT
            embedding = self._encode_single(snippet)
            self._save_to_cache(snippet, embedding)
            embeddings.append(embedding)

        return np.array(embeddings)

    def _encode_single(self, code: str) -> np.ndarray:
        """Encode single code snippet with CodeBERT."""
        try:
            import torch

            # Tokenize and encode
            inputs = self.tokenizer(
                code,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True
            )

            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use [CLS] token embedding
                embedding = outputs.last_hidden_state[:, 0, :].squeeze().numpy()

            return embedding

        except Exception as e:
            print(f"Error encoding with CodeBERT: {e}")
            # Fallback to simple features
            fallback = SimpleEmbedder(str(self.cache_dir))
            return fallback.encode([code])[0]


class EmbeddingIndex:
    """
    Index for storing and searching code embeddings.

    Provides efficient storage and similarity search for code embeddings
    with metadata and file information.
    """

    def __init__(self, embedder: CodeEmbedder):
        """
        Initialize embedding index.

        Args:
            embedder: Code embedder instance
        """
        self.embedder = embedder
        self.embeddings: List[np.ndarray] = []
        self.metadata: List[Dict[str, Any]] = []

    def add_code(self, code_snippet: str, metadata: Dict[str, Any]) -> None:
        """
        Add code snippet to index.

        Args:
            code_snippet: Code string to index
            metadata: Associated metadata (file, line, etc.)
        """
        embedding = self.embedder.encode([code_snippet])[0]
        self.embeddings.append(embedding)
        self.metadata.append(metadata)

    def search(self, query_code: str, top_k: int = 10, threshold: float = 0.5) -> List[Tuple[Dict[str, Any], float]]:
        """
        Search for similar code snippets.

        Args:
            query_code: Code to search for
            top_k: Number of top results to return
            threshold: Minimum similarity threshold

        Returns:
            List of (metadata, similarity_score) tuples
        """
        if not self.embeddings:
            return []

        query_embedding = self.embedder.encode([query_code])[0]
        similarities = []

        for i, embedding in enumerate(self.embeddings):
            similarity = self.embedder.similarity(query_embedding, embedding)
            if similarity >= threshold:
                similarities.append((self.metadata[i], similarity))

        # Sort by similarity and return top_k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def save(self, file_path: str) -> None:
        """Save index to file."""
        data = {
            "embeddings": [emb.tolist() for emb in self.embeddings],
            "metadata": self.metadata,
            "embedder_type": self.embedder.model_name,
        }

        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self, file_path: str) -> None:
        """Load index from file."""
        with open(file_path, 'r') as f:
            data = json.load(f)

        self.embeddings = [np.array(emb) for emb in data["embeddings"]]
        self.metadata = data["metadata"]

    def size(self) -> int:
        """Get number of indexed items."""
        return len(self.embeddings)


def create_embedder(model_type: str = "auto", cache_dir: str = "cache/embeddings") -> CodeEmbedder:
    """
    Create appropriate code embedder based on availability.

    Args:
        model_type: Type of embedder ("auto", "codebert", "simple")
        cache_dir: Cache directory for embeddings

    Returns:
        Initialized code embedder
    """
    if model_type == "auto":
        # Try CodeBERT first, fallback to simple
        codebert_embedder = CodeBERTEmbedder(cache_dir)
        if codebert_embedder.model is not None:
            return codebert_embedder
        else:
            return SimpleEmbedder(cache_dir)

    elif model_type == "codebert":
        return CodeBERTEmbedder(cache_dir)

    elif model_type == "simple":
        return SimpleEmbedder(cache_dir)

    else:
        raise ValueError(f"Unknown embedder type: {model_type}")


# Example usage and testing
if __name__ == "__main__":
    # Test embedders
    code_snippets = [
        "class User < ApplicationRecord\n  has_many :posts\nend",
        "def create\n  @user = User.new(user_params)\n  @user.save\nend",
        "SELECT * FROM users WHERE active = true",
    ]

    # Test simple embedder
    simple_embedder = SimpleEmbedder()
    simple_embeddings = simple_embedder.encode(code_snippets)
    print(f"Simple embeddings shape: {simple_embeddings.shape}")

    # Test similarity
    similarity = simple_embedder.similarity(simple_embeddings[0], simple_embeddings[1])
    print(f"Similarity between snippets 0 and 1: {similarity:.3f}")

    # Test index
    index = EmbeddingIndex(simple_embedder)
    for i, snippet in enumerate(code_snippets):
        index.add_code(snippet, {"id": i, "type": "test"})

    results = index.search("class Post < ApplicationRecord", top_k=2)
    print(f"Search results: {len(results)}")
    for metadata, score in results:
        print(f"  ID {metadata['id']}: {score:.3f}")