"""
Simple NumPy-based Vector Store
Lightweight alternative to ChromaDB without multiprocessing issues
"""
import hashlib
import json
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import numpy as np
from loguru import logger

from app.core.config import settings


class SimpleVectorStore:
    """
    Simple in-memory vector store using NumPy

    Features:
    - Cosine similarity search
    - Metadata filtering
    - Persistence to disk
    - No multiprocessing overhead
    """

    def __init__(self, persist_dir: str = None):
        """Initialize vector store"""
        self.persist_dir = persist_dir or settings.chroma_persist_dir
        Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

        self.store_file = Path(self.persist_dir) / "simple_vector_store.pkl"

        # Storage
        self.embeddings: Optional[np.ndarray] = None  # (n_docs, embedding_dim)
        self.documents: List[str] = []
        self.metadatas: List[Dict] = []
        self.ids: List[str] = []

        # Load existing store if available
        self._load()

        logger.info(f"SimpleVectorStore initialized with {len(self.documents)} documents")

    def add(
        self,
        documents: List[str],
        embeddings: List[List[float]],
        metadatas: List[Dict],
        ids: List[str]
    ):
        """Add documents with pre-computed embeddings"""
        if not documents:
            return

        # Convert embeddings to numpy array
        new_embeddings = np.array(embeddings, dtype=np.float32)

        # Add to store
        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])

        self.documents.extend(documents)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)

        logger.info(f"Added {len(documents)} documents. Total: {len(self.documents)}")

        # Persist to disk
        self._save()

    def query(
        self,
        query_embedding: List[float],
        n_results: int = 5,
        where: Optional[Dict] = None
    ) -> Dict:
        """
        Query similar documents using cosine similarity

        Returns:
            Dict with 'documents', 'metadatas', 'distances', 'ids'
        """
        if self.embeddings is None or len(self.documents) == 0:
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

        # Convert query to numpy
        query_vec = np.array(query_embedding, dtype=np.float32).reshape(1, -1)

        # Filter by metadata if needed
        if where:
            valid_indices = self._filter_by_metadata(where)
        else:
            valid_indices = list(range(len(self.documents)))

        if not valid_indices:
            return {
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
                "ids": [[]]
            }

        # Get embeddings for valid documents
        valid_embeddings = self.embeddings[valid_indices]

        # Compute cosine similarity
        # Normalize vectors
        query_norm = query_vec / (np.linalg.norm(query_vec, axis=1, keepdims=True) + 1e-8)
        docs_norm = valid_embeddings / (np.linalg.norm(valid_embeddings, axis=1, keepdims=True) + 1e-8)

        # Cosine similarity = dot product of normalized vectors
        similarities = np.dot(query_norm, docs_norm.T)[0]

        # Convert to distances (1 - similarity for cosine distance)
        distances = 1 - similarities

        # Get top k results
        k = min(n_results, len(valid_indices))
        top_k_indices = np.argsort(distances)[:k]

        # Map back to original indices
        original_indices = [valid_indices[i] for i in top_k_indices]

        # Format results
        results = {
            "documents": [[self.documents[i] for i in original_indices]],
            "metadatas": [[self.metadatas[i] for i in original_indices]],
            "distances": [[float(distances[i]) for i in top_k_indices]],
            "ids": [[self.ids[i] for i in original_indices]]
        }

        return results

    def get(self, where: Optional[Dict] = None, include: List[str] = None) -> Dict:
        """Get documents matching filter"""
        include = include or ["documents", "metadatas", "ids"]

        if where:
            indices = self._filter_by_metadata(where)
        else:
            indices = list(range(len(self.documents)))

        result = {}

        if "documents" in include:
            result["documents"] = [self.documents[i] for i in indices]
        if "metadatas" in include:
            result["metadatas"] = [self.metadatas[i] for i in indices]
        if "ids" in include:
            result["ids"] = [self.ids[i] for i in indices]

        return result

    def delete(self, ids: Optional[List[str]] = None, where: Optional[Dict] = None):
        """Delete documents by IDs or filter"""
        if ids:
            indices_to_delete = [i for i, doc_id in enumerate(self.ids) if doc_id in ids]
        elif where:
            indices_to_delete = self._filter_by_metadata(where)
        else:
            return

        if not indices_to_delete:
            return

        # Delete in reverse order to preserve indices
        for i in sorted(indices_to_delete, reverse=True):
            del self.documents[i]
            del self.metadatas[i]
            del self.ids[i]
            if self.embeddings is not None:
                self.embeddings = np.delete(self.embeddings, i, axis=0)

        logger.info(f"Deleted {len(indices_to_delete)} documents")
        self._save()

    def count(self) -> int:
        """Count total documents"""
        return len(self.documents)

    def reset(self):
        """Clear all data"""
        self.embeddings = None
        self.documents = []
        self.metadatas = []
        self.ids = []

        if self.store_file.exists():
            self.store_file.unlink()

        logger.warning("Vector store reset")

    def _filter_by_metadata(self, where: Dict) -> List[int]:
        """Filter documents by metadata conditions"""
        valid_indices = []

        for i, metadata in enumerate(self.metadatas):
            match = True

            for key, value in where.items():
                if isinstance(value, dict) and "$in" in value:
                    # Handle $in operator
                    if metadata.get(key) not in value["$in"]:
                        match = False
                        break
                else:
                    # Exact match
                    if metadata.get(key) != value:
                        match = False
                        break

            if match:
                valid_indices.append(i)

        return valid_indices

    def _save(self):
        """Persist store to disk"""
        try:
            data = {
                "embeddings": self.embeddings,
                "documents": self.documents,
                "metadatas": self.metadatas,
                "ids": self.ids
            }

            with open(self.store_file, "wb") as f:
                pickle.dump(data, f)

            logger.debug(f"Saved {len(self.documents)} documents to disk")
        except Exception as e:
            logger.error(f"Error saving vector store: {e}")

    def _load(self):
        """Load store from disk"""
        if not self.store_file.exists():
            return

        try:
            with open(self.store_file, "rb") as f:
                data = pickle.load(f)

            # Load embeddings (backwards compatible with old format)
            self.embeddings = data.get("embeddings", data.get("embeddings_full"))

            self.documents = data.get("documents", [])
            self.metadatas = data.get("metadatas", [])
            self.ids = data.get("ids", [])

            logger.info(f"Loaded {len(self.documents)} documents from disk")
        except Exception as e:
            logger.error(f"Error loading vector store: {e}")
