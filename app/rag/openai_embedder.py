"""
Local Embeddings using Sentence Transformers

Uses free, local embeddings for document indexing and retrieval.
No API keys, no costs, no rate limits.

Model: all-MiniLM-L6-v2
- 384 dimensions
- Fast and efficient
- Runs completely offline
- Perfect for governance document RAG
"""
from typing import List, Optional
import numpy as np
from loguru import logger

# Import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.error("sentence-transformers not installed! Install with: pip install sentence-transformers")


class UnifiedEmbedder:
    """
    Local embedding provider using Sentence Transformers

    Provides fast, free, offline embeddings for RAG applications.
    """

    def __init__(self):
        """Initialize local embedder with Sentence Transformers"""
        self.provider = "sentence_transformers"
        self.model_name = "all-MiniLM-L6-v2"
        self.dimensions = 384

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise RuntimeError(
                "sentence-transformers not installed! Install with: pip install sentence-transformers"
            )

        try:
            self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            logger.success(
                f"✅ Using local embeddings ({self.model_name}, {self.dimensions} dims, 100% free)"
            )
        except Exception as e:
            logger.error(f"SentenceTransformer initialization failed: {e}")
            raise

    def embed_documents(
        self, texts: List[str], batch_size: int = 32, show_progress: bool = False
    ) -> np.ndarray:
        """
        Embed multiple documents using local model

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for processing (default: 32)
            show_progress: Show progress bar

        Returns:
            numpy array of shape (len(texts), 384)
        """
        if not texts:
            return np.array([])

        return self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embed a single query string

        Args:
            text: Query text

        Returns:
            numpy array of shape (384,)
        """
        return self.model.encode([text], convert_to_numpy=True)[0]

    def get_info(self) -> dict:
        """Get embedding provider information"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "dimensions": self.dimensions,
            "cost_per_1m_tokens": 0.0,
            "local": True,
        }


# Singleton instance
_embedder_instance: Optional[UnifiedEmbedder] = None


def get_embedder() -> UnifiedEmbedder:
    """
    Get singleton embedder instance (local Sentence Transformers only)

    Returns:
        UnifiedEmbedder instance
    """
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = UnifiedEmbedder()

    return _embedder_instance
