#!/usr/bin/env python3
"""
Debug script to investigate project filtering issue
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.rag.rag_engine import RAGEngine
from loguru import logger

def main():
    """Debug project filtering"""

    logger.info("="*70)
    logger.info("🔍 DEBUGGING PROJECT FILTERING ISSUE")
    logger.info("="*70)

    rag = RAGEngine()

    # Get all chunks to see what's actually stored
    logger.info("\n📊 Checking database contents...")

    try:
        # Query without filters to see all data
        all_results = rag.vector_store.get()

        logger.info(f"\nTotal chunks in database: {len(all_results['ids'])}")

        # Count by project_id
        project_counts = {}
        for metadata in all_results['metadatas']:
            pid = metadata.get('project_id', 'unknown')
            project_counts[pid] = project_counts.get(pid, 0) + 1

        logger.info("\nProject distribution:")
        for pid, count in sorted(project_counts.items()):
            logger.info(f"  - {pid}: {count} chunks")

        # Check keras-team-keras chunks specifically
        logger.info("\n🔍 Examining keras-team-keras chunks:")
        keras_chunks = [
            (i, meta)
            for i, meta in enumerate(all_results['metadatas'])
            if meta.get('project_id') == 'keras-team-keras'
        ]

        logger.info(f"Found {len(keras_chunks)} keras chunks")

        if keras_chunks:
            logger.info("\nFirst 3 keras chunks metadata:")
            for i, (idx, meta) in enumerate(keras_chunks[:3]):
                logger.info(f"\n  Chunk {i+1}:")
                logger.info(f"    ID: {all_results['ids'][idx]}")
                logger.info(f"    project_id: {meta.get('project_id')}")
                logger.info(f"    file_type: {meta.get('file_type')}")
                logger.info(f"    file_path: {meta.get('file_path')}")
                logger.info(f"    Content preview: {all_results['documents'][idx][:100]}...")

        # Now test search with filter
        logger.info("\n" + "="*70)
        logger.info("🧪 TESTING SEARCH WITH PROJECT FILTER")
        logger.info("="*70)

        query = "Who are the maintainers?"

        # Test 1: Search for keras with filter
        logger.info(f"\nTest 1: Searching keras-team-keras for '{query}'")
        keras_results = rag.search(
            query=query,
            project_id="keras-team-keras",
            n_results=5,
            enable_reranking=False  # Disable to see raw scores
        )

        logger.info(f"Results: {len(keras_results)} chunks")
        for i, result in enumerate(keras_results):
            logger.info(f"\n  Result {i+1}:")
            logger.info(f"    Score: {result['score']:.3f}")
            logger.info(f"    Project: {result['metadata'].get('project_id')}")
            logger.info(f"    File: {result['metadata'].get('file_path')}")
            logger.info(f"    Content: {result['content'][:150]}...")

        # Test 2: Search without filter to see what would come up
        logger.info("\n" + "-"*70)
        logger.info(f"\nTest 2: Searching ALL projects for '{query}' (no filter)")
        all_results = rag.search(
            query=query,
            project_id=None,
            n_results=5,
            enable_reranking=False
        )

        logger.info(f"Results: {len(all_results)} chunks")
        for i, result in enumerate(all_results):
            logger.info(f"\n  Result {i+1}:")
            logger.info(f"    Score: {result['score']:.3f}")
            logger.info(f"    Project: {result['metadata'].get('project_id')}")
            logger.info(f"    File: {result['metadata'].get('file_path')}")
            logger.info(f"    Content: {result['content'][:150]}...")

        # Test 3: Direct ChromaDB query with where clause
        logger.info("\n" + "-"*70)
        logger.info("\nTest 3: Direct ChromaDB query with where clause")

        # Generate embedding for query
        query_embedding = rag.embedder.embed_query(query).tolist()

        # Query with where clause
        chroma_results = rag.vector_store.query(
            query_embedding=query_embedding,
            n_results=5,
            where={"project_id": "keras-team-keras"}
        )

        logger.info(f"ChromaDB returned {len(chroma_results['ids'][0])} results")
        for i in range(len(chroma_results['ids'][0])):
            logger.info(f"\n  Result {i+1}:")
            logger.info(f"    Distance: {chroma_results['distances'][0][i]:.3f}")
            logger.info(f"    Project: {chroma_results['metadatas'][0][i].get('project_id')}")
            logger.info(f"    File: {chroma_results['metadatas'][0][i].get('file_path')}")
            logger.info(f"    Content: {chroma_results['documents'][0][i][:150]}...")

        logger.info("\n" + "="*70)

    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
