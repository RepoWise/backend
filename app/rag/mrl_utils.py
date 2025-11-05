"""
Matryoshka Representation Learning (MRL) Utilities
Provides helper functions for embedding normalization, slicing, and manipulation
"""
import numpy as np
from typing import List, Tuple
from loguru import logger


def normalize_embedding(embedding: np.ndarray) -> np.ndarray:
    """
    L2-normalize an embedding vector or slice

    Critical for MRL: Prefix slices live in a smaller subspace.
    Without normalization, vectors spread out and cosine scores get jumpy.

    Args:
        embedding: NumPy array of shape (embedding_dim,) or (n, embedding_dim)

    Returns:
        L2-normalized embedding
    """
    if len(embedding.shape) == 1:
        # Single vector
        norm = np.linalg.norm(embedding)
        if norm < 1e-10:  # Avoid division by zero
            return embedding
        return embedding / norm
    else:
        # Batch of vectors
        norms = np.linalg.norm(embedding, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-10)  # Avoid division by zero
        return embedding / norms


def slice_and_normalize(
    full_embedding: np.ndarray,
    target_dim: int
) -> np.ndarray:
    """
    Slice embedding to target dimension and normalize

    Args:
        full_embedding: Full embedding vector or batch
        target_dim: Target dimension to slice to

    Returns:
        Sliced and normalized embedding
    """
    if len(full_embedding.shape) == 1:
        # Single vector
        sliced = full_embedding[:target_dim]
    else:
        # Batch of vectors
        sliced = full_embedding[:, :target_dim]

    return normalize_embedding(sliced)


def create_multi_dim_embeddings(
    full_embeddings: np.ndarray,
    dimensions: List[int]
) -> dict:
    """
    Create multiple dimensional embeddings from full embedding

    Args:
        full_embeddings: Full embeddings of shape (n_docs, full_dim)
        dimensions: List of target dimensions (e.g., [128, 256, 768])

    Returns:
        Dictionary mapping dimension -> normalized embeddings
    """
    multi_dim = {}

    for dim in dimensions:
        if dim > full_embeddings.shape[1]:
            logger.warning(f"Requested dimension {dim} exceeds full dimension {full_embeddings.shape[1]}")
            continue

        sliced = slice_and_normalize(full_embeddings, dim)
        multi_dim[dim] = sliced

    return multi_dim


def compute_cosine_similarity(
    query_emb: np.ndarray,
    doc_embs: np.ndarray
) -> np.ndarray:
    """
    Compute cosine similarity between query and documents
    Assumes inputs are already normalized

    Args:
        query_emb: Query embedding (embedding_dim,)
        doc_embs: Document embeddings (n_docs, embedding_dim)

    Returns:
        Similarity scores (n_docs,)
    """
    # Dot product of normalized vectors = cosine similarity
    similarities = np.dot(doc_embs, query_emb)
    return similarities


def quantize_embedding(
    embedding: np.ndarray,
    bits: int = 8
) -> Tuple[np.ndarray, float, float]:
    """
    Quantize embedding to reduce storage (optional optimization)

    Args:
        embedding: Embedding to quantize
        bits: Number of bits (default: 8 for uint8)

    Returns:
        (quantized_embedding, min_val, max_val)
    """
    min_val = embedding.min()
    max_val = embedding.max()

    scale = (2 ** bits - 1) / (max_val - min_val + 1e-10)
    quantized = np.round((embedding - min_val) * scale).astype(np.uint8)

    return quantized, min_val, max_val


def dequantize_embedding(
    quantized: np.ndarray,
    min_val: float,
    max_val: float
) -> np.ndarray:
    """
    Restore quantized embedding

    Args:
        quantized: Quantized embedding
        min_val: Original minimum value
        max_val: Original maximum value

    Returns:
        Dequantized embedding as float32
    """
    scale = (max_val - min_val) / (2 ** 8 - 1)
    return quantized.astype(np.float32) * scale + min_val
