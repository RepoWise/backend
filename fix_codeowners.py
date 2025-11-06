#!/usr/bin/env python3
"""
Fix CODEOWNERS content in vector database
"""
import asyncio
from app.rag.rag_engine import RAGEngine

async def fix_codeowners():
    rag = RAGEngine()

    # The actual CODEOWNERS content from GitHub
    codeowners_content = """# Owners for /guides directory
/guides/ @fchollet @MarkDaoust @pcoet"""

    print("Indexing CODEOWNERS file with actual content...")

    # Index the CODEOWNERS file
    await rag.index_governance_documents(
        project_id="keras-team-keras-io",
        documents=[{
            "file_path": "CODEOWNERS",
            "content": codeowners_content,
            "file_type": "maintainers"
        }]
    )

    print("✅ CODEOWNERS file re-indexed successfully!")

    # Test retrieval
    print("\nTesting retrieval...")
    results = rag.search(
        query="Who maintains the project?",
        project_id="keras-team-keras-io",
        n_results=3
    )

    print(f"\nRetrieved {len(results)} results:")
    for i, result in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"File: {result['file_path']}")
        print(f"Type: {result['file_type']}")
        print(f"Score: {result['score']:.4f}")
        print(f"Content:\n{result['content']}")

if __name__ == "__main__":
    asyncio.run(fix_codeowners())
