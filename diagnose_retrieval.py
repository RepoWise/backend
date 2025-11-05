"""
Deep dive diagnostic for RAG retrieval issues
Tests each component separately to identify root cause
"""
import asyncio
from app.rag.rag_engine import RAGEngine
from loguru import logger

def test_document_inventory():
    """Check what documents are actually indexed"""
    print("=" * 80)
    print("STEP 1: DOCUMENT INVENTORY")
    print("=" * 80)

    rag_engine = RAGEngine()

    # Get all documents for the project
    all_docs = rag_engine.vector_store.get(
        where={"project_id": "resilientdb"},
        include=["metadatas", "documents"]
    )

    if not all_docs or not all_docs.get("metadatas"):
        print("❌ No documents found for project 'resilientdb'!")
        return

    # Count documents by file type
    file_type_counts = {}
    unique_file_paths = set()

    for metadata in all_docs["metadatas"]:
        file_type = metadata.get("file_type", "unknown")
        file_path = metadata.get("file_path", "unknown")

        file_type_counts[file_type] = file_type_counts.get(file_type, 0) + 1
        unique_file_paths.add(file_path)

    print(f"\n📊 Total document chunks: {len(all_docs['metadatas'])}")
    print(f"📁 Unique files: {len(unique_file_paths)}")

    print(f"\n📋 Document Distribution by Type:")
    for file_type, count in sorted(file_type_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {file_type}: {count} chunks")

    print(f"\n📄 Unique File Paths:")
    for path in sorted(unique_file_paths):
        print(f"   - {path}")

    return all_docs

def test_vector_search_only(query: str, project_id: str):
    """Test vector search in isolation"""
    print("\n" + "=" * 80)
    print("STEP 2: VECTOR-ONLY SEARCH")
    print("=" * 80)
    print(f"Query: '{query}'")

    rag_engine = RAGEngine()

    # Perform vector search
    results = rag_engine.search(
        query=query,
        project_id=project_id,
        n_results=10
    )

    print(f"\n✅ Found {len(results)} results\n")

    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  File: {result['file_path']}")
        print(f"  Type: {result['file_type']}")
        print(f"  Score: {result['score']:.4f}")
        print(f"  Preview: {result['content'][:150]}...")
        print()

    return results

def test_bm25_search_only(query: str, project_id: str):
    """Test BM25 search in isolation"""
    print("\n" + "=" * 80)
    print("STEP 3: BM25-ONLY SEARCH")
    print("=" * 80)
    print(f"Query: '{query}'")

    rag_engine = RAGEngine()

    # Check if BM25 index exists
    if project_id not in rag_engine.bm25_indices:
        print(f"❌ No BM25 index for project: {project_id}")
        return []

    # Perform BM25 search
    results = rag_engine.bm25_search(
        query=query,
        project_id=project_id,
        n_results=10
    )

    print(f"\n✅ Found {len(results)} results\n")

    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  File: {result['file_path']}")
        print(f"  Type: {result['file_type']}")
        print(f"  Score: {result['score']:.4f}")
        print(f"  Preview: {result['content'][:150]}...")
        print()

    return results

def test_hybrid_search(query: str, project_id: str):
    """Test hybrid search (RRF fusion)"""
    print("\n" + "=" * 80)
    print("STEP 4: HYBRID SEARCH (RRF FUSION)")
    print("=" * 80)
    print(f"Query: '{query}'")

    rag_engine = RAGEngine()

    # Perform hybrid search
    results = rag_engine.hybrid_search(
        query=query,
        project_id=project_id,
        n_results=10
    )

    print(f"\n✅ Found {len(results)} results\n")

    for i, result in enumerate(results, 1):
        print(f"Result {i}:")
        print(f"  File: {result['file_path']}")
        print(f"  Type: {result['file_type']}")
        print(f"  Score: {result.get('score', 0):.4f}")
        print(f"  RRF Score: {result.get('rrf_score', 0):.4f}")
        print(f"  Method: {result.get('search_method', 'unknown')}")
        print(f"  Fusion: {result.get('fusion_method', 'none')}")
        print(f"  Preview: {result['content'][:150]}...")
        print()

    return results

def compare_search_methods():
    """Run all three searches and compare results"""
    print("\n" + "=" * 80)
    print("STEP 5: COMPARISON ANALYSIS")
    print("=" * 80)

    query = "What is the governance model?"
    project_id = "resilientdb"

    rag_engine = RAGEngine()

    # Get results from all three methods
    vector_results = rag_engine.search(query, project_id, n_results=5)
    bm25_results = rag_engine.bm25_search(query, project_id, n_results=5)
    hybrid_results = rag_engine.hybrid_search(query, project_id, n_results=5)

    print("\n📊 Top Result from Each Method:\n")

    print("Vector Search:")
    if vector_results:
        top = vector_results[0]
        print(f"  {top['file_type']} - {top['file_path']} (score: {top['score']:.4f})")
    else:
        print("  No results")

    print("\nBM25 Search:")
    if bm25_results:
        top = bm25_results[0]
        print(f"  {top['file_type']} - {top['file_path']} (score: {top['score']:.4f})")
    else:
        print("  No results")

    print("\nHybrid Search:")
    if hybrid_results:
        top = hybrid_results[0]
        print(f"  {top['file_type']} - {top['file_path']} (rrf: {top.get('rrf_score', 0):.4f})")
    else:
        print("  No results")

    # Check if governance docs appear in any results
    print("\n" + "=" * 80)
    print("GOVERNANCE DOCUMENT CHECK")
    print("=" * 80)

    gov_keywords = ["CONTRIBUTING", "GOVERNANCE", "CODE_OF_CONDUCT", "README"]

    for method_name, results in [
        ("Vector", vector_results),
        ("BM25", bm25_results),
        ("Hybrid", hybrid_results)
    ]:
        print(f"\n{method_name} Search:")
        found_gov = False
        for result in results:
            file_path = result.get('file_path', '').upper()
            if any(kw in file_path for kw in gov_keywords):
                print(f"  ✅ Found governance doc: {result['file_path']}")
                found_gov = True

        if not found_gov:
            print(f"  ❌ No governance documents in top 5 results")

def main():
    """Run all diagnostic tests"""
    logger.remove()  # Disable logger output for cleaner diagnostics

    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "RAG RETRIEVAL DIAGNOSTICS" + " " * 33 + "║")
    print("╚" + "=" * 78 + "╝")
    print("\n")

    # Step 1: Check what's indexed
    all_docs = test_document_inventory()

    if not all_docs:
        print("\n❌ CRITICAL: No documents found. RAG is empty!")
        return

    # Step 2: Test vector search
    query = "What is the governance model?"
    project_id = "resilientdb"

    vector_results = test_vector_search_only(query, project_id)

    # Step 3: Test BM25 search
    bm25_results = test_bm25_search_only(query, project_id)

    # Step 4: Test hybrid search
    hybrid_results = test_hybrid_search(query, project_id)

    # Step 5: Compare
    compare_search_methods()

    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()
