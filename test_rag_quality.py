"""
Test RAG retrieval quality for governance queries
"""
import asyncio
from app.rag.rag_engine import RAGEngine
from app.agents.intent_router import IntentRouter
from loguru import logger

async def test_governance_query():
    """Test what documents are retrieved for governance query"""

    query = "What is the governance model?"
    project_id = "resilientdb"

    print("=" * 80)
    print(f"Testing Query: '{query}'")
    print(f"Project: {project_id}")
    print("=" * 80)

    # Test intent routing
    router = IntentRouter()
    intent, metadata = router.route_query(query, project_id)
    print(f"\n1. INTENT ROUTING:")
    print(f"   Intent: {intent.value}")
    print(f"   Method: {metadata['method']}")
    print(f"   Confidence: {metadata['confidence']}")
    print(f"   Latency: {metadata['latency_ms']:.2f}ms")

    # Test RAG retrieval
    rag_engine = RAGEngine()

    print(f"\n2. RAG RETRIEVAL (Hybrid Search):")
    context, sources = rag_engine.get_context_for_query(query, project_id, max_chunks=5)

    print(f"   Retrieved {len(sources)} document chunks")
    print(f"   Total context length: {len(context)} characters")

    print(f"\n3. RETRIEVED SOURCES:")
    for i, source in enumerate(sources, 1):
        print(f"\n   Source {i}:")
        print(f"   - File: {source.get('file_path', 'N/A')}")
        print(f"   - Type: {source.get('file_type', 'N/A')}")
        print(f"   - Score: {source.get('score', 0):.4f}")
        print(f"   - Text Preview: {source.get('text', '')[:200]}...")

    print(f"\n4. FULL CONTEXT SENT TO LLM:")
    print("-" * 80)
    print(context)
    print("-" * 80)

    # Test with different query
    print("\n\n" + "=" * 80)
    query2 = "How do I contribute to the project?"
    print(f"Testing Query 2: '{query2}'")
    print("=" * 80)

    intent2, metadata2 = router.route_query(query2, project_id)
    print(f"\n1. INTENT ROUTING:")
    print(f"   Intent: {intent2.value}")
    print(f"   Method: {metadata2['method']}")

    context2, sources2 = rag_engine.get_context_for_query(query2, project_id, max_chunks=5)
    print(f"\n2. RAG RETRIEVAL:")
    print(f"   Retrieved {len(sources2)} document chunks")

    print(f"\n3. RETRIEVED SOURCES:")
    for i, source in enumerate(sources2, 1):
        print(f"   {i}. {source.get('file_type', 'N/A')}: {source.get('file_path', 'N/A')} (score: {source.get('score', 0):.4f})")

if __name__ == "__main__":
    asyncio.run(test_governance_query())
