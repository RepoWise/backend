"""
RAG Engine with Simple Vector Store for Governance Document Search
Implements semantic search, document chunking, and context retrieval
ENHANCED: Hybrid search with BM25 + vector fusion using Reciprocal Rank Fusion (RRF)
UPGRADED: OpenAI embeddings with automatic fallback to local models
"""
import hashlib
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from loguru import logger

from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.rag.simple_vector_store import SimpleVectorStore
from app.rag.openai_embedder import get_embedder


class RAGEngine:
    """
    Retrieval-Augmented Generation engine for governance documents

    Features:
    - Semantic document chunking with overlap
    - Vector similarity search using ChromaDB
    - BM25 keyword search for exact term matching
    - Hybrid search (semantic + keyword) with Reciprocal Rank Fusion (RRF)
    - Context-aware retrieval with metadata filtering
    """

    def __init__(self):
        """Initialize RAG engine with SimpleVectorStore, embedding model, and BM25 index"""

        # Initialize unified embedder (OpenAI or SentenceTransformers)
        self.embedder = get_embedder(prefer_openai=True)
        embedder_info = self.embedder.get_info()
        logger.info(
            f"Embedding provider: {embedder_info['provider']} "
            f"({embedder_info['model']}, {embedder_info['dimensions']} dims)"
        )
        if embedder_info['provider'] == 'openai':
            logger.info(f"💰 Cost: ${embedder_info['cost_per_1m_tokens']:.3f}/1M tokens")
        else:
            logger.info("🆓 Using free local embeddings")

        # Initialize simple vector store
        self.vector_store = SimpleVectorStore(persist_dir=settings.chroma_persist_dir)

        # BM25 index storage (project_id -> BM25 index + document mapping)
        self.bm25_indices: Dict[str, Dict] = {}
        self.bm25_persist_dir = Path(settings.chroma_persist_dir) / "bm25_indices"
        self.bm25_persist_dir.mkdir(exist_ok=True)

        # Load existing BM25 indices
        self._load_bm25_indices()

        logger.success("RAG Engine initialized with hybrid search support")

    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization for BM25"""
        return text.lower().split()

    def _load_bm25_indices(self):
        """Load BM25 indices from disk"""
        try:
            for index_file in self.bm25_persist_dir.glob("*.pkl"):
                project_id = index_file.stem
                with open(index_file, "rb") as f:
                    self.bm25_indices[project_id] = pickle.load(f)
                logger.info(f"Loaded BM25 index for project: {project_id}")
        except Exception as e:
            logger.warning(f"Could not load BM25 indices: {e}")

    def _save_bm25_index(self, project_id: str):
        """Save BM25 index for a project to disk"""
        try:
            index_file = self.bm25_persist_dir / f"{project_id}.pkl"
            with open(index_file, "wb") as f:
                pickle.dump(self.bm25_indices[project_id], f)
            logger.info(f"Saved BM25 index for project: {project_id}")
        except Exception as e:
            logger.error(f"Error saving BM25 index: {e}")

    def _reciprocal_rank_fusion(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        k: int = 60
    ) -> List[Dict]:
        """
        Reciprocal Rank Fusion (RRF) algorithm to combine vector and BM25 results

        RRF Formula: score(d) = Σ 1/(k + rank(d))
        where k=60 is a constant (standard in literature)

        Args:
            vector_results: Results from vector search (with 'id' and 'score')
            bm25_results: Results from BM25 search (with 'id' and 'score')
            k: RRF constant (default=60)

        Returns:
            Fused results sorted by RRF score
        """
        rrf_scores = {}

        # Process vector results
        for rank, result in enumerate(vector_results, start=1):
            doc_id = result.get("id", result.get("content", "")[:50])  # Use content snippet as fallback
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        # Process BM25 results
        for rank, result in enumerate(bm25_results, start=1):
            doc_id = result.get("id", result.get("content", "")[:50])
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank)

        # Create mapping of doc_id to full result
        all_results = {
            result.get("id", result.get("content", "")[:50]): result
            for result in vector_results + bm25_results
        }

        # Sort by RRF score
        fused = []
        for doc_id, rrf_score in sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True):
            if doc_id in all_results:
                result = all_results[doc_id].copy()
                result["rrf_score"] = rrf_score
                result["fusion_method"] = "rrf"
                fused.append(result)

        return fused

    def chunk_document(
        self,
        content: str,
        chunk_size: int = 512,
        overlap: int = 50,
        metadata: Dict = None,
    ) -> List[Tuple[str, Dict]]:
        """
        Split document into semantically meaningful chunks with overlap

        Args:
            content: Document text
            chunk_size: Target chunk size in tokens (approximate)
            overlap: Number of characters to overlap between chunks
            metadata: Metadata to attach to each chunk

        Returns:
            List of (chunk_text, chunk_metadata) tuples
        """
        if not content or not content.strip():
            return []

        # Simple character-based chunking (can be enhanced with sentence splitting)
        chunks = []
        start = 0
        content_length = len(content)

        while start < content_length:
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < content_length:
                # Look for sentence endings
                for sep in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                    sep_pos = content.rfind(sep, start, end + 100)
                    if sep_pos > start:
                        end = sep_pos + len(sep)
                        break

            chunk_text = content[start:end].strip()

            if chunk_text:
                chunk_metadata = {
                    **(metadata or {}),
                    "chunk_index": len(chunks),
                    "chunk_start": start,
                    "chunk_end": end,
                }
                chunks.append((chunk_text, chunk_metadata))

            # Update start position - ensure we always make progress
            new_start = end - overlap if overlap > 0 else end
            # Safety check: if we're not making progress, force advance by at least 1 char
            if new_start <= start:
                new_start = start + 1
            start = new_start

        logger.debug(f"Created {len(chunks)} chunks from document")
        return chunks

    def index_governance_documents(
        self, project_id: str, governance_data: Dict
    ) -> Dict:
        """
        Index governance documents for a project

        Args:
            project_id: Unique project identifier
            governance_data: Governance extraction result

        Returns:
            Indexing statistics
        """
        logger.info(f"Indexing governance documents for project: {project_id}")

        files = governance_data.get("files", {})
        if not files:
            logger.warning(f"No files to index for {project_id}")
            return {"indexed": 0, "error": "No files found"}

        # Delete existing documents for this project
        self.delete_project_documents(project_id)

        total_chunks = 0
        documents = []
        metadatas = []
        ids = []

        logger.info(f"Processing {len(files)} files for indexing...")

        # Process each governance file
        for file_type, file_data in files.items():
            logger.info(f"Processing file: {file_type}")
            content = file_data.get("content", "")
            if not content:
                logger.info(f"Skipping {file_type} - no content")
                continue

            # Prepare base metadata
            base_metadata = {
                "project_id": project_id,
                "file_type": file_type,
                "file_path": file_data.get("path", ""),
                "owner": governance_data.get("owner", ""),
                "repo": governance_data.get("repo", ""),
            }

            # Chunk document
            logger.info(f"Chunking {file_type}...")
            chunks = self.chunk_document(content, metadata=base_metadata)
            logger.info(f"Created {len(chunks)} chunks for {file_type}")

            for chunk_text, chunk_metadata in chunks:
                # Generate unique ID
                chunk_id = hashlib.md5(
                    f"{project_id}_{file_type}_{chunk_metadata['chunk_index']}".encode()
                ).hexdigest()

                documents.append(chunk_text)
                metadatas.append(chunk_metadata)
                ids.append(chunk_id)
                total_chunks += 1

        logger.info(f"Finished processing files. Total chunks: {total_chunks}")

        # Batch add to ChromaDB + BM25
        if documents:
            logger.info(f"Starting embedding generation for {total_chunks} chunks...")
            try:
                # Pre-generate embeddings using unified embedder
                logger.info(f"Generating embeddings for {total_chunks} chunks...")
                embeddings = self.embedder.embed_documents(
                    documents,
                    batch_size=100,  # OpenAI supports larger batches
                    show_progress=False
                )

                # Convert to list for ChromaDB
                embeddings_list = embeddings.tolist()

                logger.info(f"Adding {total_chunks} chunks to vector store...")
                self.vector_store.add(
                    documents=documents,
                    embeddings=embeddings_list,
                    metadatas=metadatas,
                    ids=ids
                )

                # Build BM25 index
                logger.info(f"Building BM25 index for {project_id}...")
                tokenized_docs = [self._tokenize(doc) for doc in documents]
                bm25 = BM25Okapi(tokenized_docs)

                # Store BM25 index with document mapping
                self.bm25_indices[project_id] = {
                    "bm25": bm25,
                    "documents": documents,
                    "ids": ids,
                    "metadatas": metadatas,
                }

                # Persist BM25 index to disk
                self._save_bm25_index(project_id)

                logger.success(
                    f"Indexed {total_chunks} chunks from {len(files)} files for {project_id} (Vector + BM25)"
                )

                return {
                    "indexed": total_chunks,
                    "files": len(files),
                    "project_id": project_id,
                    "bm25_indexed": True,
                }

            except Exception as e:
                logger.error(f"Error indexing documents: {e}")
                return {"indexed": 0, "error": str(e)}

        return {"indexed": 0, "files": 0}

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        n_results: int = 5,
        file_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Semantic search in governance documents

        Args:
            query: Search query
            project_id: Filter by project (optional)
            n_results: Number of results to return
            file_types: Filter by file types (optional)

        Returns:
            List of search results with content and metadata
        """
        logger.info(f"Searching for: '{query}' in project: {project_id}")

        try:
            # Build where clause for filtering
            where_clause = {}
            if project_id:
                where_clause["project_id"] = project_id

            if file_types:
                where_clause["file_type"] = {"$in": file_types}

            # Generate query embedding
            query_embedding = self.embedder.embed_query(query).tolist()

            # Perform search
            results = self.vector_store.query(
                query_embedding=query_embedding,
                n_results=n_results,
                where=where_clause if where_clause else None
            )

            # Format results
            formatted_results = []
            if results and results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i]

                    formatted_results.append(
                        {
                            "content": doc,
                            "metadata": metadata,
                            "score": 1 - distance,  # Convert distance to similarity score
                            "file_type": metadata.get("file_type", ""),
                            "file_path": metadata.get("file_path", ""),
                        }
                    )

            logger.info(f"Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def bm25_search(
        self,
        query: str,
        project_id: str,
        n_results: int = 5,
    ) -> List[Dict]:
        """
        BM25 keyword search in governance documents

        Args:
            query: Search query
            project_id: Project to search
            n_results: Number of results to return

        Returns:
            List of search results with content and metadata
        """
        if project_id not in self.bm25_indices:
            logger.warning(f"No BM25 index found for project: {project_id}")
            return []

        try:
            index_data = self.bm25_indices[project_id]
            bm25 = index_data["bm25"]
            documents = index_data["documents"]
            ids = index_data["ids"]
            metadatas = index_data["metadatas"]

            # Tokenize query
            tokenized_query = self._tokenize(query)

            # Get BM25 scores
            scores = bm25.get_scores(tokenized_query)

            # Get top N results
            top_indices = scores.argsort()[-n_results:][::-1]

            results = []
            for idx in top_indices:
                if scores[idx] > 0:  # Only include documents with positive scores
                    results.append({
                        "id": ids[idx],
                        "content": documents[idx],
                        "metadata": metadatas[idx],
                        "score": float(scores[idx]),
                        "file_type": metadatas[idx].get("file_type", ""),
                        "file_path": metadatas[idx].get("file_path", ""),
                        "search_method": "bm25",
                    })

            logger.info(f"BM25 search found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"BM25 search error: {e}")
            return []

    def hybrid_search(
        self,
        query: str,
        project_id: Optional[str] = None,
        n_results: int = 5,
        file_types: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Hybrid search combining vector similarity and BM25 using Reciprocal Rank Fusion

        This provides the best of both worlds:
        - Vector search: Semantic similarity (finds "license" when you ask about "copyright")
        - BM25 search: Exact keyword matching (finds "Apache-2.0" when you search for it)

        Args:
            query: Search query
            project_id: Filter by project (optional for vector, required for BM25)
            n_results: Number of final results to return
            file_types: Filter by file types (optional)

        Returns:
            List of fused search results ranked by RRF score
        """
        logger.info(f"Hybrid search for: '{query}' in project: {project_id}")

        # Vector search (always available)
        vector_results = self.search(
            query=query,
            project_id=project_id,
            n_results=n_results * 2,  # Get more for better fusion
            file_types=file_types
        )

        # Add IDs to vector results (use content hash if no id)
        for result in vector_results:
            if "id" not in result:
                result["id"] = hashlib.md5(result["content"][:100].encode()).hexdigest()
            result["search_method"] = "vector"

        # BM25 search (if project has BM25 index)
        bm25_results = []
        if project_id and project_id in self.bm25_indices:
            bm25_results = self.bm25_search(
                query=query,
                project_id=project_id,
                n_results=n_results * 2
            )
        else:
            logger.info(f"No BM25 index for {project_id}, using vector-only search")

        # If we have both, fuse them
        if vector_results and bm25_results:
            logger.info(f"Fusing {len(vector_results)} vector + {len(bm25_results)} BM25 results")
            fused_results = self._reciprocal_rank_fusion(vector_results, bm25_results)
            final_results = fused_results[:n_results]
            logger.info(f"Hybrid search returned {len(final_results)} fused results")
            return final_results

        # Fallback to vector-only if no BM25 index
        logger.info(f"Returning {len(vector_results[:n_results])} vector-only results")
        return vector_results[:n_results]

    def get_context_for_query(
        self,
        query: str,
        project_id: str,
        max_chunks: int = 5,
        max_chars: int = 4000,
    ) -> Tuple[str, List[Dict]]:
        """
        Retrieve relevant context for LLM query using HYBRID SEARCH

        Uses both vector similarity and BM25 keyword matching for best results.

        Args:
            query: User query
            project_id: Project to search
            max_chunks: Maximum chunks to retrieve
            max_chars: Maximum total characters for context

        Returns:
            (context_string, source_chunks)
        """
        # Use hybrid search for best results
        results = self.hybrid_search(query, project_id=project_id, n_results=max_chunks)

        context_parts = []
        total_chars = 0
        sources = []

        for result in results:
            content = result["content"]
            if total_chars + len(content) > max_chars:
                # Truncate if needed
                remaining = max_chars - total_chars
                if remaining > 100:  # Only add if meaningful content remains
                    content = content[:remaining] + "..."
                else:
                    break

            context_parts.append(
                f"[{result['file_type'].upper()}] {result['file_path']}\n{content}"
            )
            total_chars += len(content)

            sources.append(
                {
                    "file_type": result["file_type"],
                    "file_path": result["file_path"],
                    "score": result["score"],
                    # Preserve hybrid search metadata
                    "search_method": result.get("search_method", "unknown"),
                    "fusion_method": result.get("fusion_method", "none"),
                    "rrf_score": result.get("rrf_score", 0),
                }
            )

            if total_chars >= max_chars:
                break

        context = "\n\n---\n\n".join(context_parts)
        return context, sources

    def delete_project_documents(self, project_id: str) -> bool:
        """Delete all documents for a project (vector + BM25)"""
        try:
            # Delete from vector store
            self.vector_store.delete(where={"project_id": project_id})

            # Delete BM25 index
            if project_id in self.bm25_indices:
                del self.bm25_indices[project_id]

                # Delete persisted index file
                index_file = self.bm25_persist_dir / f"{project_id}.pkl"
                if index_file.exists():
                    index_file.unlink()

            logger.info(f"Deleted documents and indices for project {project_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting project documents: {e}")
            return False

    def get_collection_stats(self) -> Dict:
        """Get statistics about the document collection"""
        try:
            count = self.vector_store.count()

            # Get project distribution
            all_docs = self.vector_store.get(include=["metadatas"])
            project_counts = {}

            if all_docs and all_docs["metadatas"]:
                for metadata in all_docs["metadatas"]:
                    project_id = metadata.get("project_id", "unknown")
                    project_counts[project_id] = project_counts.get(project_id, 0) + 1

            return {
                "total_chunks": count,
                "projects_indexed": len(project_counts),
                "project_distribution": project_counts,
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"total_chunks": 0, "projects_indexed": 0}

    def reset_collection(self) -> bool:
        """Reset the entire collection (use with caution!)"""
        try:
            self.vector_store.reset()
            logger.warning("Collection reset successfully")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            return False
