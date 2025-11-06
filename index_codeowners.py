#!/usr/bin/env python3
"""
Index CODEOWNERS content for keras-io using the RAG engine
"""
import asyncio
from app.rag.rag_engine import RAGEngine

async def main():
    # Initialize RAG engine
    rag = RAGEngine()

    # CODEOWNERS content from GitHub
    codeowners_content = """# Owners for /guides directory
/guides/ @fchollet @MarkDaoust @pcoet

The maintainers of the Keras-io project are:
- @fchollet (François Chollet)
- @MarkDaoust (Mark Daoust)
- @pcoet (Paul Coet)

These GitHub users are responsible for maintaining the /guides directory."""

    print("📝 Indexing CODEOWNERS file...")

    # Create governance documents structure
    gov_data = {
        "files": {
            "CODEOWNERS": {
                "content": codeowners_content,
                "file_type": "maintainers",
                "file_path": "CODEOWNERS",
                "size": len(codeowners_content)
            }
        },
        "metadata": {
            "owner": "keras-team",
            "repo": "keras-io",
            "extraction_time_seconds": 0
        }
    }

    # Index using RAG engine (not async)
    result = rag.index_governance_documents("keras-team-keras-io", gov_data)

    print(f"✅ Indexing complete!")
    print(f"   Project: keras-team-keras-io")
    print(f"   Chunks indexed: {result.get('total_chunks', 0)}")
    print(f"   Collection: {result.get('collection', 'unknown')}")

    # Test retrieval
    print("\n🔍 Testing retrieval...")
    results = rag.retrieve_governance_docs(
        project_id="keras-team-keras-io",
        query="Who maintains the project?",
        top_k=3
    )

    print(f"\nRetrieved {len(results)} documents:")
    for i, (content, metadata, score) in enumerate(results, 1):
        print(f"\n--- Result {i} ---")
        print(f"File: {metadata.get('file_path', 'unknown')}")
        print(f"Type: {metadata.get('file_type', 'unknown')}")
        print(f"Score: {score:.4f}")
        print(f"Content:\n{content[:200]}...")

if __name__ == "__main__":
    asyncio.run(main())
