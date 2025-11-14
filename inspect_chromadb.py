#!/usr/bin/env python3
"""Inspect ChromaDB collections to debug project context issue"""
import chromadb
from chromadb.config import Settings

# Initialize ChromaDB client
client = chromadb.PersistentClient(
    path="../chromadb",
    settings=Settings(
        anonymized_telemetry=False,
        allow_reset=False,
        is_persistent=True,
    )
)

# List all collections
collections = client.list_collections()
print(f"\n📦 Total Collections: {len(collections)}\n")

for collection in collections:
    print(f"  Collection: {collection.name}")
    print(f"  Documents: {collection.count()}")
    print(f"  Metadata: {collection.metadata}")

    # Extract project_id from collection name
    if collection.name.startswith("project_docs_"):
        project_id = collection.name.replace("project_docs_", "")
        print(f"  Project ID: {project_id}")

        # Sample a few documents to see what's in there
        if collection.count() > 0:
            sample = collection.get(limit=2, include=["metadatas"])
            if sample and sample.get("metadatas"):
                print(f"  Sample metadata: {sample['metadatas'][0]}")

    print()
