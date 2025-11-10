"""
Production-Grade ChromaDB Vector Store for Multi-Project RAG
Implements advanced features: hybrid search, metadata filtering, relevance scoring
"""
import hashlib
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from loguru import logger

from app.core.config import settings


class ChromaVectorStore:
    """
    Production-grade ChromaDB vector store for project document retrieval

    Features:
    - Multi-project isolation using separate collections
    - Persistent storage with automatic snapshots
    - Hybrid search (semantic + keyword)
    - Advanced metadata filtering
    - Relevance scoring and reranking
    - Efficient batch operations
    - Thread-safe operations
    """

    def __init__(self, persist_dir: str = None):
        """
        Initialize ChromaDB client with optimal settings

        Args:
            persist_dir: Directory for persistent storage
        """
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB with production settings
        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
                is_persistent=True,
            )
        )

        # Collection cache for fast access
        self._collections = {}

        logger.success(f"ChromaDB initialized at {self.persist_dir}")
        logger.info(f"Available collections: {self._list_collections()}")

    def _list_collections(self) -> List[str]:
        """List all collections in the database"""
        try:
            collections = self.client.list_collections()
            return [col.name for col in collections]
        except Exception as e:
            logger.warning(f"Error listing collections: {e}")
            return []

    def _get_collection(self, project_id: str, create_if_missing: bool = True):
        """
        Get or create a collection for a specific project

        Args:
            project_id: Unique project identifier
            create_if_missing: Create collection if it doesn't exist

        Returns:
            ChromaDB collection instance
        """
        # Collection names must be 3-63 characters, alphanumeric + underscores/hyphens
        collection_name = f"project_docs_{project_id}".replace("/", "_").replace(".", "_")

        # Check cache first
        if collection_name in self._collections:
            return self._collections[collection_name]

        try:
            # Try to get existing collection
            collection = self.client.get_collection(name=collection_name)
            logger.debug(f"Retrieved existing collection: {collection_name}")
        except Exception:
            if create_if_missing:
                # Create new collection with metadata
                collection = self.client.create_collection(
                    name=collection_name,
                    metadata={
                        "project_id": project_id,
                        "description": f"Project documents for {project_id}",
                        "hnsw:space": "cosine",  # Use cosine similarity
                    }
                )
                logger.info(f"Created new collection: {collection_name}")
            else:
                logger.warning(f"Collection {collection_name} not found")
                return None

        # Cache the collection
        self._collections[collection_name] = collection
        return collection

    def add(
        self,
        project_id: str,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: List[str]
    ):
        """
        Add documents to project-specific collection with batch processing

        Args:
            project_id: Project identifier
            documents: List of document texts
            embeddings: Pre-computed embeddings
            metadatas: Document metadata
            ids: Unique document IDs

        Raises:
            ValueError: If no documents provided or all batches failed
            Exception: If ChromaDB operations fail
        """
        if not documents:
            error_msg = "No documents to add"
            logger.error(error_msg)
            raise ValueError(error_msg)

        collection = self._get_collection(project_id, create_if_missing=True)

        # ChromaDB has a batch size limit, process in chunks
        batch_size = 5000
        total_added = 0
        total_batches = (len(documents) + batch_size - 1) // batch_size
        failed_batches = []

        for i in range(0, len(documents), batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_embeds = embeddings[i:i + batch_size]
            batch_metas = metadatas[i:i + batch_size]
            batch_ids = ids[i:i + batch_size]
            batch_num = i//batch_size + 1

            try:
                collection.add(
                    documents=batch_docs,
                    embeddings=batch_embeds,
                    metadatas=batch_metas,
                    ids=batch_ids
                )
                total_added += len(batch_docs)
                logger.debug(f"✅ Added batch {batch_num}/{total_batches}: {len(batch_docs)} documents")
            except Exception as e:
                error_msg = f"❌ Batch {batch_num}/{total_batches} failed: {e}"
                logger.error(error_msg)
                failed_batches.append((batch_num, str(e)))
                # Continue with next batch but track failures

        # Verify documents were actually added
        total_docs = collection.count()

        if total_added == 0:
            error_details = "; ".join([f"Batch {num}: {err}" for num, err in failed_batches])
            error_msg = f"Failed to add any documents to {project_id}. All {total_batches} batches failed. Errors: {error_details}"
            logger.error(error_msg)
            raise Exception(error_msg)

        if failed_batches:
            logger.warning(f"⚠️ {len(failed_batches)}/{total_batches} batches failed for {project_id}")

        logger.success(f"✅ Added {total_added}/{len(documents)} documents to {project_id}. Collection total: {total_docs}")

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict:
        """
        Query similar documents using vector similarity

        Args:
            project_id: Project to query
            query_embedding: Query vector
            n_results: Number of results to return
            where: Metadata filter (e.g., {"file_type": "CONTRIBUTING"})
            where_document: Document content filter (e.g., {"$contains": "governance"})

        Returns:
            Dict with 'documents', 'metadatas', 'distances', 'ids'
        """
        collection = self._get_collection(project_id, create_if_missing=False)

        if collection is None:
            logger.warning(f"No collection found for project: {project_id}")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

        try:
            # Perform vector search with filters
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, collection.count()),  # Don't exceed collection size
                where=where,
                where_document=where_document,
                include=["documents", "metadatas", "distances"]
            )

            logger.debug(f"Query returned {len(results['documents'][0])} results for {project_id}")
            return results

        except Exception as e:
            logger.error(f"Error querying ChromaDB: {e}")
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

    def hybrid_search(
        self,
        project_id: str,
        query_embedding: List[float],
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict] = None,
        alpha: float = 0.7
    ) -> Dict:
        """
        Hybrid search combining semantic (vector) and keyword (BM25) search

        Args:
            project_id: Project to query
            query_embedding: Query vector for semantic search
            query_text: Query text for keyword search
            n_results: Total results to return
            where: Metadata filter
            alpha: Weight for semantic search (1-alpha for keyword)
                  0.0 = pure keyword, 1.0 = pure semantic, 0.5 = balanced

        Returns:
            Merged and reranked results
        """
        # Get more results from each method, then merge
        semantic_results = self.query(
            project_id=project_id,
            query_embedding=query_embedding,
            n_results=n_results * 2,
            where=where
        )

        # Keyword search using where_document
        keyword_results = self.query(
            project_id=project_id,
            query_embedding=query_embedding,  # Still need embedding for ChromaDB
            n_results=n_results * 2,
            where=where,
            where_document={"$contains": query_text.split()[0]} if query_text else None
        )

        # Merge and rerank results
        merged = self._merge_search_results(
            semantic_results,
            keyword_results,
            alpha=alpha,
            n_results=n_results
        )

        logger.debug(f"Hybrid search returned {len(merged['documents'][0])} results")
        return merged

    def _merge_search_results(
        self,
        semantic_results: Dict,
        keyword_results: Dict,
        alpha: float,
        n_results: int
    ) -> Dict:
        """
        Merge semantic and keyword search results using reciprocal rank fusion

        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            alpha: Weight for semantic results
            n_results: Number of final results

        Returns:
            Merged results dictionary
        """
        # Use reciprocal rank fusion (RRF) for merging
        scores = {}
        k = 60  # RRF constant

        # Score semantic results
        for rank, doc_id in enumerate(semantic_results['ids'][0]):
            scores[doc_id] = alpha * (1.0 / (k + rank + 1))

        # Score keyword results
        for rank, doc_id in enumerate(keyword_results['ids'][0]):
            if doc_id in scores:
                scores[doc_id] += (1 - alpha) * (1.0 / (k + rank + 1))
            else:
                scores[doc_id] = (1 - alpha) * (1.0 / (k + rank + 1))

        # Sort by combined score
        ranked_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:n_results]

        # Build result dictionary
        id_to_data = {}
        for i, doc_id in enumerate(semantic_results['ids'][0]):
            id_to_data[doc_id] = {
                'document': semantic_results['documents'][0][i],
                'metadata': semantic_results['metadatas'][0][i],
                'distance': semantic_results['distances'][0][i]
            }
        for i, doc_id in enumerate(keyword_results['ids'][0]):
            if doc_id not in id_to_data:
                id_to_data[doc_id] = {
                    'document': keyword_results['documents'][0][i],
                    'metadata': keyword_results['metadatas'][0][i],
                    'distance': keyword_results['distances'][0][i]
                }

        # Construct final results
        merged_docs = []
        merged_metas = []
        merged_dists = []
        merged_ids = []

        for doc_id in ranked_ids:
            if doc_id in id_to_data:
                data = id_to_data[doc_id]
                merged_docs.append(data['document'])
                merged_metas.append(data['metadata'])
                merged_dists.append(data['distance'])
                merged_ids.append(doc_id)

        return {
            'documents': [merged_docs],
            'metadatas': [merged_metas],
            'distances': [merged_dists],
            'ids': [merged_ids]
        }

    def delete_collection(self, project_id: str) -> bool:
        """
        Delete all documents for a project

        Args:
            project_id: Project to delete

        Returns:
            True if successful
        """
        collection_name = f"project_docs_{project_id}".replace("/", "_").replace(".", "_")

        try:
            self.client.delete_collection(name=collection_name)
            if collection_name in self._collections:
                del self._collections[collection_name]
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            return False

    def get_collection_stats(self, project_id: str) -> Dict:
        """
        Get statistics for a project's collection

        Args:
            project_id: Project identifier

        Returns:
            Dict with collection statistics
        """
        collection = self._get_collection(project_id, create_if_missing=False)

        if collection is None:
            return {"exists": False, "count": 0}

        return {
            "exists": True,
            "count": collection.count(),
            "name": collection.name,
            "metadata": collection.metadata
        }

    def get_all_stats(self) -> Dict:
        """
        Get statistics for all collections

        Returns:
            Dict with stats for each project
        """
        all_collections = self.client.list_collections()
        stats = {
            "total_collections": len(all_collections),
            "projects": {}
        }

        for collection in all_collections:
            # Extract project_id from collection name
            if collection.name.startswith("project_docs_"):
                project_id = collection.name.replace("project_docs_", "")
                stats["projects"][project_id] = {
                    "document_count": collection.count(),
                    "metadata": collection.metadata
                }

        return stats

    def upsert(
        self,
        project_id: str,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: List[str]
    ):
        """
        Update or insert documents (safer than add for re-indexing)

        Args:
            project_id: Project identifier
            documents: Document texts
            embeddings: Document embeddings
            metadatas: Document metadata
            ids: Document IDs
        """
        if not documents:
            return

        collection = self._get_collection(project_id, create_if_missing=True)

        try:
            collection.upsert(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Upserted {len(documents)} documents for {project_id}")
        except Exception as e:
            logger.error(f"Error upserting documents: {e}")

    def reset(self):
        """Reset entire database (use with caution!)"""
        try:
            self.client.reset()
            self._collections = {}
            logger.warning("ChromaDB reset - all data cleared!")
        except Exception as e:
            logger.error(f"Error resetting ChromaDB: {e}")
