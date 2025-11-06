#!/usr/bin/env python3
"""
Test what content is actually retrieved for CODEOWNERS
"""
import asyncio
from app.rag.rag_engine import RAGEngine

async def test_codeowners_retrieval():
    rag = RAGEngine()

    query = "Who maintains Keras-io?"
    project_id = "keras-team-keras-io"

    print(f"Query: {query}")
    print(f"Project: {project_id}")
    print(f"\n{'='*80}")

    # Retrieve governance docs
    results = await rag.retrieve_governance_docs(
        project_id=project_id,
        query=query,
        top_k=5
    )

    print(f"Retrieved {len(results)} documents\n")

    for i, (content, metadata, score) in enumerate(results, 1):
        print(f"\n--- Document {i} ---")
        print(f"File: {metadata.get('file_path', 'unknown')}")
        print(f"Type: {metadata.get('file_type', 'unknown')}")
        print(f"Score: {score:.4f}")
        print(f"Content length: {len(content)} characters")
        print(f"\nContent:\n{content[:500]}")  # First 500 chars
        print(f"\n{'='*80}")

if __name__ == "__main__":
    asyncio.run(test_codeowners_retrieval())
