#!/usr/bin/env python3
"""
Directly fix CODEOWNERS in ChromaDB
"""
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

# Initialize embedding model
print("Loading embedding model...")
model = SentenceTransformer('all-MiniLM-L6-v2')

# Connect to ChromaDB
print("Connecting to ChromaDB...")
client = chromadb.PersistentClient(
    path="../chromadb",
    settings=Settings(anonymized_telemetry=False)
)

# Get collection
collection = client.get_collection(name="gov_docs_keras-team-keras-io")
print(f"✓ Found collection: {collection.name}")
print(f"  Total documents: {collection.count()}")

# CODEOWNERS content
codeowners_content = """# Owners for /guides directory
/guides/ @fchollet @MarkDaoust @pcoet

The maintainers of the Keras-io project are:
- @fchollet (François Chollet)
- @MarkDaoust (Mark Daoust)
- @pcoet (Paul Coet)

These GitHub users are responsible for maintaining the /guides directory."""

# Create embedding
print("\nGenerating embedding...")
embedding = model.encode(codeowners_content).tolist()

# Delete old CODEOWNERS entries
print("\nDeleting old CODEOWNERS entries...")
try:
    collection.delete(
        where={"file_path": "CODEOWNERS"}
    )
    print("✓ Deleted old entries")
except Exception as e:
    print(f"  No old entries to delete (or error: {e})")

# Add new entry
print("\nAdding new CODEOWNERS with content...")
collection.add(
    documents=[codeowners_content],
    embeddings=[embedding],
    metadatas=[{
        "file_path": "CODEOWNERS",
        "file_type": "maintainers",
        "project_id": "keras-team-keras-io",
        "chunk_index": 0
    }],
    ids=["codeowners-fixed"]
)

print("✅ CODEOWNERS re-indexed successfully!")
print(f"   Content length: {len(codeowners_content)} characters")

# Test retrieval
print("\n" + "="*60)
print("Testing retrieval...")
print("="*60)

query_embedding = model.encode("Who maintains the project?").tolist()
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=3,
    where={"project_id": "keras-team-keras-io"}
)

if results['documents']:
    for i, (doc, meta, dist) in enumerate(zip(results['documents'][0], results['metadatas'][0], results['distances'][0]), 1):
        print(f"\n--- Result {i} ---")
        print(f"File: {meta.get('file_path', 'unknown')}")
        print(f"Type: {meta.get('file_type', 'unknown')}")
        print(f"Distance: {dist:.4f}")
        print(f"Content:\n{doc[:200]}...")

print("\n✓ Fix complete! Try the query again in the frontend.")
