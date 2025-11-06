#!/usr/bin/env python3
"""
Debug script to check what CODEOWNERS content is in the vector database
"""
import chromadb
from chromadb.config import Settings

# Connect to ChromaDB
client = chromadb.PersistentClient(
    path="../data/chromadb",
    settings=Settings(anonymized_telemetry=False)
)

# Get the keras-io collection
try:
    collection = client.get_collection(name="keras-team-keras-io")
    print(f"✓ Found collection: keras-team-keras-io")
    print(f"  Total documents: {collection.count()}")

    # Query for CODEOWNERS file
    results = collection.get(
        where={"file_path": "CODEOWNERS"},
        include=["documents", "metadatas"]
    )

    print(f"\n{'='*80}")
    print("CODEOWNERS FILE CONTENT IN VECTOR DB:")
    print(f"{'='*80}")

    if results['documents']:
        for i, (doc, meta) in enumerate(zip(results['documents'], results['metadatas'])):
            print(f"\n--- Chunk {i+1} ---")
            print(f"Metadata: {meta}")
            print(f"Content:\n{doc}")
            print(f"Content length: {len(doc)} characters")
    else:
        print("❌ No CODEOWNERS file found in vector database")

except Exception as e:
    print(f"❌ Error: {e}")
