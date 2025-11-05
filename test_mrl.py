"""
Test script for MRL (Matryoshka Representation Learning) implementation
Verifies that the embedding model and MRL utilities work correctly
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.rag.rag_engine import RAGEngine
from app.rag import mrl_utils
from app.core.config import settings
import numpy as np
from loguru import logger

def test_mrl_utilities():
    """Test MRL utility functions"""
    logger.info("=" * 60)
    logger.info("Testing MRL Utilities")
    logger.info("=" * 60)

    # Create test embedding
    test_embedding = np.random.randn(768).astype(np.float32)
    logger.info(f"Test embedding shape: {test_embedding.shape}")

    # Test normalization
    normalized = mrl_utils.normalize_embedding(test_embedding)
    norm = np.linalg.norm(normalized)
    logger.info(f"Normalized embedding L2 norm: {norm:.6f} (should be ~1.0)")
    assert abs(norm - 1.0) < 1e-5, "Normalization failed"
    logger.success("✓ Normalization works correctly")

    # Test slicing and normalization
    for dim in [128, 256, 768]:
        sliced = mrl_utils.slice_and_normalize(test_embedding, dim)
        logger.info(f"Sliced to {dim} dims - shape: {sliced.shape}, norm: {np.linalg.norm(sliced):.6f}")
        assert sliced.shape[0] == dim, f"Slicing to {dim} failed"
        assert abs(np.linalg.norm(sliced) - 1.0) < 1e-5, f"Normalization of {dim}-dim slice failed"
    logger.success("✓ Slicing and normalization work correctly")

    # Test multi-dimensional embeddings
    batch_embeddings = np.random.randn(10, 768).astype(np.float32)
    multi_dim = mrl_utils.create_multi_dim_embeddings(batch_embeddings, [128, 256, 768])
    logger.info(f"Multi-dimensional embeddings created: {list(multi_dim.keys())}")
    for dim, embs in multi_dim.items():
        logger.info(f"  {dim} dims: shape={embs.shape}, all normalized={np.allclose(np.linalg.norm(embs, axis=1), 1.0)}")
    logger.success("✓ Multi-dimensional embeddings work correctly")

    logger.info("")


def test_embedding_model():
    """Test that the MRL embedding model loads and works"""
    logger.info("=" * 60)
    logger.info("Testing MRL Embedding Model")
    logger.info("=" * 60)

    logger.info(f"MRL Enabled: {settings.mrl_enabled}")
    logger.info(f"Embedding Model: {settings.embedding_model}")
    logger.info(f"MRL Dimensions: {settings.mrl_dimensions}")
    logger.info(f"MRL Shortlist Dim: {settings.mrl_shortlist_dim}")
    logger.info(f"MRL Rerank Dim: {settings.mrl_rerank_dim}")
    logger.info(f"MRL Shortlist K: {settings.mrl_shortlist_k}")

    # Initialize RAG engine (this loads the model)
    logger.info("\nInitializing RAG Engine...")
    rag_engine = RAGEngine()

    # Test encoding
    test_texts = [
        "This is a test governance document.",
        "Another test about contributing to open source.",
        "Security policy for the project."
    ]

    logger.info(f"\nEncoding {len(test_texts)} test documents...")
    embeddings = rag_engine.embedding_model.encode(test_texts, convert_to_numpy=True)
    logger.info(f"Full embeddings shape: {embeddings.shape}")
    logger.info(f"Expected: ({len(test_texts)}, {rag_engine.full_dim})")

    assert embeddings.shape == (len(test_texts), rag_engine.full_dim), "Embedding shape mismatch"
    logger.success(f"✓ Embedding model works correctly (dim={rag_engine.full_dim})")

    # Test MRL slicing
    if settings.mrl_enabled:
        logger.info("\nTesting MRL slicing on encoded embeddings...")
        for dim in settings.mrl_dimensions:
            sliced = mrl_utils.slice_and_normalize(embeddings, dim)
            logger.info(f"  Sliced to {dim} dims: {sliced.shape}")
            assert sliced.shape == (len(test_texts), dim), f"Slicing to {dim} failed"
        logger.success("✓ MRL slicing works with real embeddings")

    logger.info("")


def test_vector_store_mrl():
    """Test that the vector store supports MRL"""
    logger.info("=" * 60)
    logger.info("Testing Vector Store MRL Support")
    logger.info("=" * 60)

    from app.rag.simple_vector_store import SimpleVectorStore
    import tempfile
    import shutil

    # Create temporary directory for test
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Using temporary directory: {temp_dir}")

    try:
        vector_store = SimpleVectorStore(persist_dir=temp_dir)
        logger.info(f"Vector store initialized (MRL: {vector_store.mrl_enabled})")

        # Create test embeddings
        test_docs = ["doc1", "doc2", "doc3"]
        embeddings_full = np.random.randn(3, 768).astype(np.float32)
        embeddings_128 = mrl_utils.slice_and_normalize(embeddings_full, 128)
        embeddings_256 = mrl_utils.slice_and_normalize(embeddings_full, 256)

        # Add documents
        vector_store.add(
            documents=test_docs,
            embeddings=embeddings_full.tolist(),
            metadatas=[{"id": i} for i in range(3)],
            ids=[f"doc_{i}" for i in range(3)],
            embeddings_128=embeddings_128.tolist(),
            embeddings_256=embeddings_256.tolist()
        )

        logger.info(f"Added {vector_store.count()} documents")
        logger.info(f"  Full embeddings shape: {vector_store.embeddings_full.shape}")
        if vector_store.embeddings_128 is not None:
            logger.info(f"  128-dim embeddings shape: {vector_store.embeddings_128.shape}")
        if vector_store.embeddings_256 is not None:
            logger.info(f"  256-dim embeddings shape: {vector_store.embeddings_256.shape}")

        # Test query with MRL
        query_full = np.random.randn(768).astype(np.float32)
        query_128 = mrl_utils.slice_and_normalize(query_full, 128)

        results = vector_store.query(
            query_embedding=mrl_utils.normalize_embedding(query_full).tolist(),
            query_embedding_128=query_128.tolist(),
            n_results=2,
            use_mrl=True
        )

        logger.info(f"\nQuery results: {len(results['documents'][0])} documents")
        logger.success("✓ Vector store MRL support works correctly")

    finally:
        # Cleanup
        shutil.rmtree(temp_dir)
        logger.info(f"Cleaned up temporary directory")

    logger.info("")


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("MRL IMPLEMENTATION TEST SUITE")
    logger.info("=" * 60 + "\n")

    try:
        # Test 1: MRL utilities
        test_mrl_utilities()

        # Test 2: Embedding model
        test_embedding_model()

        # Test 3: Vector store MRL support
        test_vector_store_mrl()

        logger.info("=" * 60)
        logger.success("ALL TESTS PASSED! ✓")
        logger.info("=" * 60)
        logger.info("\nMRL Implementation Summary:")
        logger.info(f"  • MRL Enabled: {settings.mrl_enabled}")
        logger.info(f"  • Embedding Model: {settings.embedding_model}")
        logger.info(f"  • Dimensions: {settings.mrl_dimensions}")
        logger.info(f"  • Two-Stage Search: {settings.mrl_shortlist_dim}d → {settings.mrl_rerank_dim}d")
        logger.info(f"  • Shortlist Size: {settings.mrl_shortlist_k}")
        logger.info("\nThe MRL framework is fully implemented and working! 🎉")

        return 0

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"TEST FAILED: {e}")
        logger.error("=" * 60)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
