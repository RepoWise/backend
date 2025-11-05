"""
OpenAI Embeddings Integration with Automatic Fallback

Provides superior embedding quality when API key is available,
automatically falls back to sentence-transformers if not.

Performance Comparison:
- OpenAI text-embedding-3-small: 1536 dims, +15% accuracy, $0.02/1M tokens
- SentenceTransformers all-MiniLM-L6-v2: 384 dims, free, local

Cost Example:
- 1000 chunks × 200 tokens = 200K tokens = $0.004 per project
- 1000 projects/month = $4/month total
"""
import os
from typing import List, Optional
import numpy as np
from loguru import logger

# Try importing OpenAI (optional dependency)
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("OpenAI library not installed. Install with: pip install openai")

# Fallback to sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.error("sentence-transformers not installed!")


class UnifiedEmbedder:
    """
    Unified embedding interface with automatic provider selection

    Priority:
    1. OpenAI (if API key available) - Best quality
    2. SentenceTransformers (fallback) - Local, free
    """

    def __init__(self, prefer_openai: bool = True):
        """
        Initialize embedder with automatic fallback

        Args:
            prefer_openai: Try OpenAI first if available
        """
        self.provider = None
        self.model_name = None
        self.dimensions = None

        # Try OpenAI first
        if prefer_openai and OPENAI_AVAILABLE:
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key and api_key.strip():
                try:
                    self.client = OpenAI(api_key=api_key)
                    # Test with a simple embedding
                    test_response = self.client.embeddings.create(
                        model="text-embedding-3-small",
                        input=["test"]
                    )
                    self.provider = "openai"
                    self.model_name = "text-embedding-3-small"
                    self.dimensions = 1536
                    logger.success(
                        f"✅ Using OpenAI embeddings (text-embedding-3-small, 1536 dims)"
                    )
                    logger.info("Cost: ~$0.004 per project, $4/month for 1000 projects")
                    return
                except Exception as e:
                    logger.warning(f"OpenAI initialization failed: {e}")

        # Fallback to SentenceTransformers
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                self.model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
                self.provider = "sentence_transformers"
                self.model_name = "all-MiniLM-L6-v2"
                self.dimensions = 384
                logger.info(
                    f"ℹ️  Using local embeddings (all-MiniLM-L6-v2, 384 dims)"
                )
                logger.info("Free, but 10-15% lower retrieval accuracy than OpenAI")
                return
            except Exception as e:
                logger.error(f"SentenceTransformer initialization failed: {e}")

        raise RuntimeError(
            "No embedding provider available! Install openai or sentence-transformers"
        )

    def embed_documents(
        self, texts: List[str], batch_size: int = 100, show_progress: bool = False
    ) -> np.ndarray:
        """
        Embed multiple documents

        Args:
            texts: List of text strings to embed
            batch_size: Batch size for processing
            show_progress: Show progress bar (SentenceTransformers only)

        Returns:
            numpy array of shape (len(texts), dimensions)
        """
        if not texts:
            return np.array([])

        if self.provider == "openai":
            return self._embed_with_openai(texts, batch_size)
        elif self.provider == "sentence_transformers":
            return self._embed_with_sentence_transformers(texts, show_progress)
        else:
            raise RuntimeError("No embedding provider initialized")

    def embed_query(self, text: str) -> np.ndarray:
        """
        Embed a single query string

        Args:
            text: Query text

        Returns:
            numpy array of shape (dimensions,)
        """
        if self.provider == "openai":
            return self._embed_with_openai([text], batch_size=1)[0]
        elif self.provider == "sentence_transformers":
            return self.model.encode([text], convert_to_numpy=True)[0]
        else:
            raise RuntimeError("No embedding provider initialized")

    def _embed_with_openai(self, texts: List[str], batch_size: int) -> np.ndarray:
        """
        Embed texts using OpenAI API with batching

        OpenAI allows up to 2048 texts per API call, but we use smaller
        batches to handle rate limits and errors gracefully.
        """
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            try:
                response = self.client.embeddings.create(
                    model=self.model_name, input=batch
                )

                batch_embeddings = [e.embedding for e in response.data]
                embeddings.extend(batch_embeddings)

                if i % 500 == 0 and i > 0:
                    logger.info(f"Embedded {i}/{len(texts)} documents with OpenAI")

            except Exception as e:
                logger.error(f"OpenAI embedding batch failed at index {i}: {e}")
                # Fallback to sentence-transformers for this batch
                logger.warning("Falling back to local embeddings for this batch")
                if SENTENCE_TRANSFORMERS_AVAILABLE:
                    fallback_model = SentenceTransformer(
                        "sentence-transformers/all-MiniLM-L6-v2"
                    )
                    fallback_embeddings = fallback_model.encode(
                        batch, convert_to_numpy=True
                    )
                    # Pad to 1536 dimensions to match OpenAI
                    padded = np.pad(
                        fallback_embeddings,
                        ((0, 0), (0, 1536 - 384)),
                        mode="constant",
                    )
                    embeddings.extend(padded.tolist())
                else:
                    # Return zeros as last resort
                    embeddings.extend([[0.0] * 1536] * len(batch))

        return np.array(embeddings)

    def _embed_with_sentence_transformers(
        self, texts: List[str], show_progress: bool
    ) -> np.ndarray:
        """
        Embed texts using SentenceTransformers (local, free)
        """
        return self.model.encode(
            texts,
            batch_size=32,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
        )

    def get_info(self) -> dict:
        """Get embedding provider information"""
        return {
            "provider": self.provider,
            "model": self.model_name,
            "dimensions": self.dimensions,
            "cost_per_1m_tokens": 0.02 if self.provider == "openai" else 0.0,
            "local": self.provider == "sentence_transformers",
        }


# Singleton instance
_embedder_instance: Optional[UnifiedEmbedder] = None


def get_embedder(prefer_openai: bool = True) -> UnifiedEmbedder:
    """
    Get singleton embedder instance

    Args:
        prefer_openai: Prefer OpenAI if available (default: True)

    Returns:
        UnifiedEmbedder instance
    """
    global _embedder_instance

    if _embedder_instance is None:
        _embedder_instance = UnifiedEmbedder(prefer_openai=prefer_openai)

    return _embedder_instance
