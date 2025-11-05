"""
Simple script to pre-index ResilientDB governance documents
"""
import json
import hashlib
from pathlib import Path
from sentence_transformers import SentenceTransformer
from app.rag.simple_vector_store import SimpleVectorStore
from app.core.config import settings

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50):
    """Simple text chunking"""
    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        # Try to break at sentence boundary
        if end < text_len:
            for sep in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                pos = text.rfind(sep, start, end + 50)
                if pos > start:
                    end = pos + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap if end < text_len else text_len

        # Safety check to prevent infinite loops
        if start >= text_len:
            break

    return chunks

def main():
    print("=" * 60)
    print("Pre-indexing ResilientDB Governance Documents")
    print("=" * 60)

    # Load cached governance data
    cache_id = hashlib.md5('apache/incubator-resilientdb'.encode()).hexdigest()
    cache_file = Path('../data/cache') / f'{cache_id}.json'

    if not cache_file.exists():
        print(f"ERROR: Cache file not found: {cache_file}")
        return False

    print(f"\n1. Loading cache from: {cache_file}")
    with open(cache_file) as f:
        data = json.load(f)

    files = data.get('files', {})
    print(f"   Found {len(files)} governance files")

    # Initialize embedding model
    print(f"\n2. Loading embedding model: {settings.embedding_model}")
    model = SentenceTransformer(settings.embedding_model)
    print("   Model loaded successfully")

    # Process all documents
    print("\n3. Processing and chunking documents...")
    all_documents = []
    all_metadatas = []
    all_ids = []

    for file_type, file_data in files.items():
        content = file_data.get('content', '')
        if not content:
            continue

        print(f"   - {file_type}: {len(content)} chars")
        chunks = chunk_text(content)
        print(f"     Created {len(chunks)} chunks")

        for i, chunk in enumerate(chunks):
            all_documents.append(chunk)
            all_metadatas.append({
                'project_id': 'resilientdb',
                'file_type': file_type,
                'file_path': file_data.get('path', ''),
                'chunk_index': i,
                'owner': 'apache',
                'repo': 'incubator-resilientdb'
            })
            chunk_id = hashlib.md5(f"resilientdb_{file_type}_{i}".encode()).hexdigest()
            all_ids.append(chunk_id)

    print(f"\n   Total chunks to index: {len(all_documents)}")

    # Generate embeddings
    print("\n4. Generating embeddings...")
    embeddings = model.encode(
        all_documents,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True
    )
    embeddings_list = embeddings.tolist()
    print(f"   Generated {len(embeddings_list)} embeddings")

    # Initialize vector store and add documents
    print("\n5. Saving to vector store...")
    vector_store = SimpleVectorStore(persist_dir=settings.chroma_persist_dir)

    # Clear existing data for resilientdb
    print("   Clearing old data...")
    vector_store.delete(where={'project_id': 'resilientdb'})

    # Add new data
    print("   Adding documents...")
    vector_store.add(
        documents=all_documents,
        embeddings=embeddings_list,
        metadatas=all_metadatas,
        ids=all_ids
    )

    # Verify
    stats = {
        'total_chunks': vector_store.count(),
        'indexed_files': len(files),
        'project_id': 'resilientdb'
    }

    print("\n" + "=" * 60)
    print("✅ Indexing Complete!")
    print("=" * 60)
    print(f"Total documents in store: {stats['total_chunks']}")
    print(f"Files indexed: {stats['indexed_files']}")
    print(f"Project: {stats['project_id']}")
    print("=" * 60)

    return True

if __name__ == '__main__':
    try:
        success = main()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
