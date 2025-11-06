"""
Production-Grade RAG Engine with ChromaDB for Governance Document Search
Implements hybrid search, semantic chunking, and advanced retrieval
Using local Sentence Transformers embeddings (free, offline, no API keys)
"""
import hashlib
from typing import List, Dict, Optional, Tuple
from loguru import logger

from app.core.config import settings
from app.rag.chroma_vector_store import ChromaVectorStore
from app.rag.openai_embedder import get_embedder


class RAGEngine:
    """
    Production-grade Retrieval-Augmented Generation engine

    Features:
    - Semantic document chunking with overlap
    - ChromaDB with persistent storage
    - Hybrid search (semantic + keyword)
    - Multi-project isolation
    - Advanced metadata filtering
    - Relevance scoring and reranking
    - Local embeddings (Sentence Transformers - free, offline)
    """

    def __init__(self):
        """Initialize RAG engine with ChromaDB and embedding model"""

        # Initialize local embedder (Sentence Transformers)
        self.embedder = get_embedder()
        embedder_info = self.embedder.get_info()
        logger.info(
            f"Embedding provider: {embedder_info['provider']} "
            f"({embedder_info['model']}, {embedder_info['dimensions']} dims)"
        )
        logger.info("🆓 Using free local embeddings")

        # Initialize ChromaDB vector store
        self.vector_store = ChromaVectorStore(persist_dir=settings.chroma_persist_dir)

        logger.success("RAG Engine initialized with ChromaDB hybrid search")

    def chunk_document(
        self,
        content: str,
        chunk_size: int = 800,
        overlap: int = 100,
        min_chunk_size: int = 200,
        metadata: Dict = None,
    ) -> List[Tuple[str, Dict]]:
        """
        Split document into semantically meaningful chunks with overlap

        Enhanced chunking strategy:
        - Prefers paragraph boundaries (double newlines)
        - Falls back to sentence boundaries
        - Enforces minimum chunk size for context
        - Prevents tiny fragment chunks

        Args:
            content: Document text
            chunk_size: Target chunk size in characters
            overlap: Number of characters to overlap between chunks
            min_chunk_size: Minimum chunk size to prevent fragments
            metadata: Metadata to attach to each chunk

        Returns:
            List of (chunk_text, chunk_metadata) tuples
        """
        if not content or not content.strip():
            return []

        chunks = []
        start = 0
        content_length = len(content)

        # For very small documents (e.g., CODEOWNERS), index as-is without chunking
        if content_length < min_chunk_size:
            chunk_metadata = {
                **(metadata or {}),
                "chunk_index": 0,
                "chunk_start": 0,
                "chunk_end": content_length,
            }
            chunks.append((content.strip(), chunk_metadata))
            logger.debug(f"Small document ({content_length} chars) indexed as single chunk")
            return chunks

        while start < content_length:
            # Calculate target end position
            end = min(start + chunk_size, content_length)

            # If we're at the end, take everything remaining
            if end >= content_length:
                chunk_text = content[start:].strip()
                if chunk_text and len(chunk_text) >= min_chunk_size:
                    chunk_metadata = {
                        **(metadata or {}),
                        "chunk_index": len(chunks),
                        "chunk_start": start,
                        "chunk_end": content_length,
                    }
                    chunks.append((chunk_text, chunk_metadata))
                elif chunk_text and chunks:
                    # Merge small final chunk with previous chunk
                    prev_chunk_text, prev_metadata = chunks[-1]
                    merged_text = prev_chunk_text + "\n\n" + chunk_text
                    chunks[-1] = (merged_text, prev_metadata)
                break

            # Try to find a good break point
            best_break = end

            # 1. Try paragraph break (double newline) within reasonable range
            paragraph_search_start = max(start + min_chunk_size, end - 200)
            paragraph_pos = content.rfind("\n\n", paragraph_search_start, end + 100)
            if paragraph_pos > start + min_chunk_size:
                best_break = paragraph_pos + 2
            else:
                # 2. Try sentence boundary
                sentence_search_start = max(start + min_chunk_size, end - 150)
                for sep in [".\n", ". ", "!\n", "! ", "?\n", "? "]:
                    sep_pos = content.rfind(sep, sentence_search_start, end + 100)
                    if sep_pos > start + min_chunk_size:
                        best_break = sep_pos + len(sep)
                        break

                # 3. If no good break found, try newline
                if best_break == end:
                    newline_pos = content.rfind("\n", sentence_search_start, end + 50)
                    if newline_pos > start + min_chunk_size:
                        best_break = newline_pos + 1

            # Extract chunk
            chunk_text = content[start:best_break].strip()

            # Only add chunk if it meets minimum size
            if chunk_text and len(chunk_text) >= min_chunk_size:
                chunk_metadata = {
                    **(metadata or {}),
                    "chunk_index": len(chunks),
                    "chunk_start": start,
                    "chunk_end": best_break,
                }
                chunks.append((chunk_text, chunk_metadata))

                # Move to next chunk with overlap
                start = best_break - overlap
            else:
                # Chunk too small, extend the range
                start = best_break

            # Safety: ensure we always make progress
            if start >= best_break:
                start = best_break + 1

        logger.debug(f"Created {len(chunks)} chunks from document (min_size={min_chunk_size})")
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

        # Batch add to ChromaDB
        if documents:
            logger.info(f"Starting embedding generation for {total_chunks} chunks...")
            try:
                # Generate embeddings using local embedder
                logger.info(f"Generating embeddings for {total_chunks} chunks...")
                embeddings = self.embedder.embed_documents(
                    documents,
                    batch_size=32,
                    show_progress=False
                )

                # Convert to list for ChromaDB
                embeddings_list = embeddings.tolist()

                logger.info(f"Adding {total_chunks} chunks to ChromaDB vector store...")
                self.vector_store.add(
                    project_id=project_id,
                    documents=documents,
                    embeddings=embeddings_list,
                    metadatas=metadatas,
                    ids=ids
                )

                logger.success(
                    f"Indexed {total_chunks} chunks from {len(files)} files for {project_id}"
                )

                return {
                    "indexed": total_chunks,
                    "files": len(files),
                    "project_id": project_id,
                }

            except Exception as e:
                logger.error(f"Error indexing documents: {e}")
                return {"indexed": 0, "error": str(e)}

        return {"indexed": 0, "files": 0}

    def _classify_query(self, query: str) -> str:
        """
        Classify query type for task-specific retrieval

        Args:
            query: User query

        Returns:
            Query type: 'who', 'what', 'how', 'why', 'list', 'boolean', 'general'
        """
        query_lower = query.lower().strip()

        # Entity extraction queries (who, what maintainer/author/contributor)
        if query_lower.startswith(("who ", "who's", "whos")) or \
           "who are" in query_lower or "who is" in query_lower:
            return "who"

        # Definition queries
        if query_lower.startswith(("what ", "what's", "whats")) or \
           "what is" in query_lower or "what are" in query_lower:
            return "what"

        # Process queries
        if query_lower.startswith(("how ", "how do", "how to", "how can")):
            return "how"

        # List queries
        if "list " in query_lower or query_lower.startswith("show ") or \
           query_lower.startswith("give me"):
            return "list"

        return "general"

    def _expand_query(self, query: str, query_type: str) -> List[str]:
        """
        Expand query for better retrieval based on query type

        Args:
            query: Original query
            query_type: Classified query type

        Returns:
            List of query variations
        """
        queries = [query]

        # For "who" questions, add entity-focused variations
        if query_type == "who":
            if "maintainer" in query.lower():
                queries.append("M: @")  # MAINTAINERS file format pattern
                queries.append("email address maintainer contact")
            if "author" in query.lower() or "contributor" in query.lower():
                queries.append("author email contact")

        # For "how" questions, emphasize process words
        if query_type == "how":
            queries.append(query + " step process procedure")

        return queries

    def _rerank_results(
        self,
        results: List[Dict],
        query_type: str,
        query: str
    ) -> List[Dict]:
        """
        Simplified reranking for "who" queries only

        Boosts results containing @ symbols (maintainers, contributors)

        Args:
            results: Initial search results
            query_type: Classified query type
            query: Original query

        Returns:
            Reranked results (only for "who" queries)
        """
        # Only rerank for "who" queries (entity extraction)
        if query_type != "who":
            logger.debug(f"Skipping reranking for query_type={query_type}")
            return results

        # Simple boost for @ symbols (GitHub usernames, emails)
        for result in results:
            at_count = result["content"].count("@")
            boost = at_count * 0.1  # +0.1 per @ symbol
            result["rerank_score"] = result["score"] + boost
            result["original_score"] = result["score"]

        # Sort by reranked score
        reranked = sorted(results, key=lambda x: x.get("rerank_score", x["score"]), reverse=True)

        if reranked:
            logger.debug(
                f"Reranking applied for 'who' query: "
                f"Top score changed from {results[0]['score']:.3f} to {reranked[0]['rerank_score']:.3f}"
            )

        return reranked

    def search(
        self,
        query: str,
        project_id: Optional[str] = None,
        n_results: int = 5,
        file_types: Optional[List[str]] = None,
        enable_reranking: bool = True,
    ) -> List[Dict]:
        """
        Intelligent semantic search with query classification and reranking

        Args:
            query: Search query
            project_id: Filter by project (optional)
            n_results: Number of results to return
            file_types: Filter by file types (optional)
            enable_reranking: Whether to apply reranking (default: True)

        Returns:
            List of search results with content and metadata
        """
        logger.info(f"Searching for: '{query}' in project: {project_id}")

        try:
            # Classify query type for intelligent retrieval
            query_type = self._classify_query(query)
            logger.debug(f"Query classified as: {query_type}")

            # Expand query for better coverage
            query_variations = self._expand_query(query, query_type)

            # Build where clause for filtering (file_types only)
            where_clause = {}
            if file_types:
                where_clause["file_type"] = {"$in": file_types}

            # Retrieve more candidates for reranking (2x the requested amount)
            retrieval_count = n_results * 2 if enable_reranking else n_results

            # Generate query embedding (use original query)
            query_embedding = self.embedder.embed_query(query).tolist()

            # Perform search in ChromaDB (project-specific collection)
            results = self.vector_store.query(
                project_id=project_id,  # ChromaDB isolates by collection
                query_embedding=query_embedding,
                n_results=retrieval_count,
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

            # Apply reranking if enabled
            if enable_reranking and formatted_results:
                formatted_results = self._rerank_results(
                    formatted_results,
                    query_type,
                    query
                )
                # Trim to requested number
                formatted_results = formatted_results[:n_results]

            logger.info(f"Found {len(formatted_results)} results (type={query_type})")
            return formatted_results

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    def get_context_for_query(
        self,
        query: str,
        project_id: str,
        max_chunks: int = 10,
        max_chars: int = 6000,
    ) -> Tuple[str, List[Dict], str]:
        """
        Retrieve relevant context for LLM query using intelligent search

        Args:
            query: User query
            project_id: Project to search
            max_chunks: Maximum chunks to retrieve (default: 10 for better coverage)
            max_chars: Maximum total characters for context (default: 6000)

        Returns:
            (context_string, source_chunks, query_type)
        """
        # Classify query type for downstream use
        query_type = self._classify_query(query)

        # Use intelligent search with reranking
        results = self.search(query, project_id=project_id, n_results=max_chunks)

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
                }
            )

            if total_chars >= max_chars:
                break

        context = "\n\n---\n\n".join(context_parts)
        return context, sources, query_type

    def delete_project_documents(self, project_id: str) -> bool:
        """Delete all documents for a project (deletes entire collection)"""
        try:
            # Delete project collection from ChromaDB
            success = self.vector_store.delete_collection(project_id)

            if success:
                logger.info(f"Deleted collection for project {project_id}")
            else:
                logger.warning(f"No collection found for project {project_id}")

            return success

        except Exception as e:
            logger.error(f"Error deleting project documents: {e}")
            return False

    def get_collection_stats(self) -> Dict:
        """Get statistics about all indexed projects"""
        try:
            # Get stats from ChromaDB for all projects
            stats = self.vector_store.get_all_stats()

            # Format for compatibility with existing code
            total_docs = sum(p["document_count"] for p in stats.get("projects", {}).values())
            project_distribution = {
                project_id: p["document_count"]
                for project_id, p in stats.get("projects", {}).items()
            }

            return {
                "total_chunks": total_docs,
                "projects_indexed": stats.get("total_collections", 0),
                "project_distribution": project_distribution,
            }

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {"total_chunks": 0, "projects_indexed": 0, "project_distribution": {}}

    def reset_collection(self) -> bool:
        """Reset the entire collection (use with caution!)"""
        try:
            self.vector_store.reset()
            logger.warning("Collection reset successfully")
            return True
        except Exception as e:
            logger.error(f"Error resetting collection: {e}")
            return False
