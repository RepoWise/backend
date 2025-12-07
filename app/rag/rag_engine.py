"""
Production-Grade RAG Engine with ChromaDB for Governance Document Search
Implements hybrid search, semantic chunking, and advanced retrieval
Using local Sentence Transformers embeddings (free, offline, no API keys)
"""
import hashlib
from collections import defaultdict
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

    def index_project_documents(
        self, project_id: str, governance_data: Dict
    ) -> Dict:
        """
        Index project documents for a project

        Args:
            project_id: Unique project identifier
            governance_data: Governance extraction result

        Returns:
            Indexing statistics
        """
        logger.info(f"Indexing project documents for project: {project_id}")

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
        Intelligent query classification using LLM (Llama 3.2 8B)

        Classifies queries into detailed sub-categories for optimal document routing:
        - who: Entity extraction (maintainers, contributors)
        - what_project_description: General project overview → prioritize README
        - what_sustainability: Sustainability goals/metrics → multi-source analysis
        - what_main_issue: Current/major issues → issues analysis + summarization
        - what_describe: Contextual descriptions → adaptive routing
        - what: Generic "what" questions
        - how: Process/procedure questions
        - list: List/enumeration questions
        - general: Other queries

        Args:
            query: User query

        Returns:
            Detailed query type string
        """
        query_lower = query.lower().strip()

        # Fast path: Simple keyword-based classification for common patterns
        # This avoids LLM overhead for obvious cases

        # Entity extraction queries (who)
        if query_lower.startswith(("who ", "who's", "whos")) or \
           "who are" in query_lower or "who is" in query_lower:
            return "who"

        # Process queries (how)
        if query_lower.startswith(("how ", "how do", "how to", "how can")):
            return "how"

        # List queries
        if query_lower.startswith(("list ", "show me all", "give me all")):
            return "list"

        # Intelligent classification for complex "what" and "describe" queries
        # Use LLM for nuanced understanding
        if query_lower.startswith(("what ", "what's", "whats")) or \
           "what is" in query_lower or "what are" in query_lower or \
           "describe" in query_lower or "give me" in query_lower:

            # Use LLM for intelligent sub-classification
            llm_classification = self._intelligent_classify_what_query(query)
            if llm_classification:
                return llm_classification

            # Fallback to generic "what"
            return "what"

        return "general"

    def _intelligent_classify_what_query(self, query: str) -> str:
        """
        Use Llama 3.2 8B to intelligently classify nuanced "what" and descriptive queries

        This method leverages the LLM to understand query intent beyond simple keywords,
        enabling sophisticated routing for OSS sustainability, issues, and commit analysis.

        Args:
            query: User query

        Returns:
            Specific classification: what_project_description, what_sustainability,
            what_main_issue, what_describe, or empty string for fallback
        """
        from app.models.llm_client import LLMClient

        try:
            llm = LLMClient()

            classification_prompt = f"""You are a query intent classifier for an Open Source Software analysis system.

Given a user query, classify it into ONE of these categories:

1. PROJECT_DESCRIPTION - Query asks for general project overview, purpose, or "what this project does/is"
   Examples: "What is this project?", "What does this project do?", "Tell me about this project"

2. SUSTAINABILITY - Query asks about sustainability goals, practices, metrics, or long-term health
   Examples: "What are the sustainability goals?", "What is the sustainability of this project?",
            "Describe the project's sustainability practices", "How sustainable is this project?"

3. MAIN_ISSUE - Query asks about the primary/main/biggest issue, problem, or current concern
   Examples: "What is the main issue?", "What is the biggest problem?", "What are the major issues?"

4. DESCRIBE - Query asks to describe something specific (not project overview, sustainability, or main issue)
   Examples: "Describe the latest issue", "Give me a description of the contribution process",
            "Describe how testing works"

5. OTHER - Query doesn't fit above categories (generic "what" questions)
   Examples: "What is a pull request?", "What files are in the repo?", "What license?"

USER QUERY: "{query}"

Respond with ONLY the category name (PROJECT_DESCRIPTION, SUSTAINABILITY, MAIN_ISSUE, DESCRIBE, or OTHER).
Do not include any explanation or additional text."""

            # Use fast, zero-temperature generation for deterministic classification
            result = llm.generate_simple(classification_prompt, temperature=0, max_tokens=20)

            classification = result.strip().upper()
            logger.debug(f"LLM classified query as: {classification}")

            # Map LLM output to internal classification codes
            classification_map = {
                "PROJECT_DESCRIPTION": "what_project_description",
                "SUSTAINABILITY": "what_sustainability",
                "MAIN_ISSUE": "what_main_issue",
                "DESCRIBE": "what_describe",
                "OTHER": "what"
            }

            return classification_map.get(classification, "")

        except Exception as e:
            logger.warning(f"LLM classification failed, using fallback: {e}")
            # Fallback to keyword-based heuristics
            query_lower = query.lower()

            if any(kw in query_lower for kw in ["sustainability", "sustainable", "long-term health", "project health"]):
                return "what_sustainability"

            if any(kw in query_lower for kw in ["main issue", "biggest issue", "major issue", "primary issue", "biggest problem"]):
                return "what_main_issue"

            if "describe" in query_lower or "description" in query_lower:
                return "what_describe"

            if any(kw in query_lower for kw in ["what is this project", "what does this project do", "what this project", "project overview"]):
                return "what_project_description"

            return ""

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
        Intelligent reranking with document type boosting for all query types

        Applies query-specific boosts to prioritize relevant document types:
        - who: Boost CODEOWNERS/MAINTAINERS with @ symbols
        - what_project_description: Strongly boost README, penalize LICENSE
        - what_sustainability: Boost README, CONTRIBUTING, governance docs
        - what_main_issue: Boost recent documents (for issues analysis)
        - what_describe: Contextual boosting based on query keywords
        - what: Moderate README boost
        - how: Boost CONTRIBUTING, how-to docs
        - general: Minimal boosting

        Args:
            results: Initial search results
            query_type: Classified query type
            query: Original query

        Returns:
            Reranked results with adjusted scores
        """
        if not results:
            return results

        query_lower = query.lower()

        # Apply query-type specific boosting
        for result in results:
            file_type = result.get("file_type", "").lower()
            content = result.get("content", "")
            original_score = result["score"]
            boost = 0.0

            # 1. WHO queries: Boost entity-rich documents
            if query_type == "who":
                at_count = content.count("@")
                boost += at_count * 0.1  # +0.1 per @ symbol
                if file_type in ["codeowners", "maintainers", "authors"]:
                    boost += 0.2

            # 2. PROJECT DESCRIPTION queries: Strongly prioritize README
            elif query_type == "what_project_description":
                if file_type == "readme":
                    boost += 0.5  # Strong boost for README
                elif file_type == "license":
                    boost -= 0.3  # Penalize LICENSE (not project description)
                elif file_type == "contributing":
                    boost += 0.1  # Minor boost for context

            # 3. SUSTAINABILITY queries: Multi-source analysis
            elif query_type == "what_sustainability":
                # Sustainability info could be in multiple documents
                if file_type == "readme":
                    boost += 0.3  # Often contains sustainability sections
                elif file_type == "contributing":
                    boost += 0.25  # Contribution processes indicate sustainability
                elif file_type in ["governance", "code_of_conduct"]:
                    boost += 0.2  # Governance indicates organizational sustainability
                elif file_type in ["security", "support"]:
                    boost += 0.15  # Security/support practices

                # Content-based boosting for sustainability keywords
                sustainability_keywords = ["sustainability", "long-term", "roadmap", "future", "maintenance", "support", "community"]
                keyword_count = sum(1 for kw in sustainability_keywords if kw in content.lower())
                boost += keyword_count * 0.05

            # 4. MAIN ISSUE queries: Boost governance/issue-related docs
            elif query_type == "what_main_issue":
                # These queries will often need CSV data, but boost relevant docs
                if file_type in ["issues", "known_issues", "changelog"]:
                    boost += 0.3
                elif file_type == "readme":
                    boost += 0.15  # READMEs sometimes list major issues

                # Content-based boosting
                issue_keywords = ["issue", "problem", "bug", "concern", "challenge"]
                keyword_count = sum(1 for kw in issue_keywords if kw in content.lower())
                boost += keyword_count * 0.05

            # 5. DESCRIBE queries: Adaptive boosting based on what's being described
            elif query_type == "what_describe":
                # Parse what's being described from the query
                if "issue" in query_lower or "bug" in query_lower:
                    if file_type in ["issues", "changelog", "known_issues"]:
                        boost += 0.3
                elif "contribut" in query_lower or "pr" in query_lower or "pull request" in query_lower:
                    if file_type == "contributing":
                        boost += 0.4
                    elif file_type == "readme":
                        boost += 0.15
                elif "test" in query_lower or "testing" in query_lower:
                    if file_type in ["contributing", "readme", "testing"]:
                        boost += 0.3
                elif "security" in query_lower:
                    if file_type == "security":
                        boost += 0.4
                    elif file_type in ["contributing", "readme"]:
                        boost += 0.15
                else:
                    # Generic description - slight README boost
                    if file_type == "readme":
                        boost += 0.2

            # 6. Generic WHAT queries: Moderate README boost
            elif query_type == "what":
                if file_type == "readme":
                    boost += 0.2
                elif file_type == "license":
                    boost -= 0.1  # Slight penalty for LICENSE on generic questions

            # 7. HOW queries: Boost procedural documents
            elif query_type == "how":
                if file_type == "contributing":
                    boost += 0.3
                elif file_type == "readme":
                    boost += 0.15
                elif file_type in ["development", "building", "setup"]:
                    boost += 0.2

            # Apply the boost
            result["rerank_score"] = original_score + boost
            result["original_score"] = original_score
            result["boost_applied"] = boost

        # Sort by reranked score
        reranked = sorted(results, key=lambda x: x.get("rerank_score", x["score"]), reverse=True)

        # Log reranking details
        if reranked and query_type != "general":
            top_result = reranked[0]
            logger.debug(
                f"Reranking for '{query_type}': "
                f"Top doc changed: {results[0].get('file_type')} (score={results[0]['score']:.3f}) → "
                f"{top_result.get('file_type')} (score={top_result['rerank_score']:.3f}, boost={top_result.get('boost_applied', 0):.3f})"
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

            # Deduplicate results to handle any potential duplicates
            results = self.vector_store.deduplicate_results(results)

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
    ) -> Tuple[str, List[Dict], str, float]:
        """
        Retrieve relevant context for LLM query using intelligent search

        Enhanced with multi-source retrieval for complex queries like sustainability
        and main issue analysis. Now includes confidence scoring and source deduplication.

        Args:
            query: User query
            project_id: Project to search
            max_chunks: Maximum chunks to retrieve (default: 10 for better coverage)
            max_chars: Maximum total characters for context (default: 6000)

        Returns:
            (context_string, deduplicated_sources, query_type, confidence_score)
        """
        # Classify query type for downstream use
        query_type = self._classify_query(query)

        # For complex queries, use multi-source retrieval
        if query_type in ["what_sustainability", "what_main_issue"]:
            return self._get_multi_source_context(
                query, project_id, query_type, max_chunks, max_chars
            )

        # Standard single-query search for other query types
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
                    "score": result.get("score", 0),
                }
            )

            if total_chars >= max_chars:
                break

        # Aggregate sources using Noisy OR to deduplicate and calculate chunk counts
        aggregated_sources = self._aggregate_scores_noisy_or(sources)

        # Limit to max 5 unique sources as requested
        aggregated_sources = aggregated_sources[:5]

        # Calculate confidence score based on retrieval quality
        confidence_score = self._calculate_answer_confidence(
            aggregated_sources, query, query_type
        )

        context = "\n\n---\n\n".join(context_parts)
        return context, aggregated_sources, query_type, confidence_score

    def _get_multi_source_context(
        self,
        query: str,
        project_id: str,
        query_type: str,
        max_chunks: int = 10,
        max_chars: int = 6000,
    ) -> Tuple[str, List[Dict], str, float]:
        """
        Multi-source context retrieval for complex queries

        Performs multiple targeted searches and combines results intelligently.
        Used for sustainability and main issue queries that benefit from
        analyzing multiple document types together.

        Now includes confidence scoring and source deduplication.

        Args:
            query: User query
            project_id: Project to search
            query_type: Classified query type (what_sustainability or what_main_issue)
            max_chunks: Maximum chunks total
            max_chars: Maximum total characters

        Returns:
            (context_string, deduplicated_sources, query_type, confidence_score)
        """
        logger.info(f"Using multi-source retrieval for {query_type}")

        all_results = []

        if query_type == "what_sustainability":
            # Sustainability: search across multiple angles
            search_queries = [
                ("sustainability governance", ["governance", "code_of_conduct", "contributing"]),
                ("community contribution maintenance", ["contributing", "readme"]),
                ("roadmap future long-term", ["readme", "governance"]),
            ]

            for search_query, preferred_file_types in search_queries:
                results = self.search(
                    search_query,
                    project_id=project_id,
                    n_results=4,
                    file_types=preferred_file_types if preferred_file_types else None
                )
                all_results.extend(results)

        elif query_type == "what_main_issue":
            # Main issue: search for issue indicators
            search_queries = [
                ("critical issue problem bug", ["issues", "known_issues", "changelog"]),
                ("major concern challenge", ["readme", "issues"]),
                (query, None),  # Original query as well
            ]

            for search_query, preferred_file_types in search_queries:
                results = self.search(
                    search_query,
                    project_id=project_id,
                    n_results=4,
                    file_types=preferred_file_types if preferred_file_types else None
                )
                all_results.extend(results)

        # Deduplicate and re-rank combined results
        seen_ids = set()
        unique_results = []
        for result in all_results:
            result_id = f"{result.get('file_type')}:{result.get('file_path')}"
            if result_id not in seen_ids:
                seen_ids.add(result_id)
                unique_results.append(result)

        # Apply intelligent reranking to combined results
        reranked_results = self._rerank_results(unique_results, query_type, query)

        # Limit to max_chunks
        final_results = reranked_results[:max_chunks]

        # Build context
        context_parts = []
        total_chars = 0
        sources = []

        for result in final_results:
            content = result["content"]
            if total_chars + len(content) > max_chars:
                remaining = max_chars - total_chars
                if remaining > 100:
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
                    "score": result.get("score", 0),
                }
            )

            if total_chars >= max_chars:
                break

        # Aggregate sources using Noisy OR to deduplicate and calculate chunk counts
        aggregated_sources = self._aggregate_scores_noisy_or(sources)

        # Limit to max 5 unique sources as requested
        aggregated_sources = aggregated_sources[:5]

        # Calculate confidence score based on retrieval quality
        confidence_score = self._calculate_answer_confidence(
            aggregated_sources, query, query_type
        )

        context = "\n\n---\n\n".join(context_parts)
        logger.info(
            f"Multi-source context built: {len(aggregated_sources)} unique sources, "
            f"{total_chars} chars from {len(set(s['file_type'] for s in aggregated_sources))} file types, "
            f"confidence={confidence_score:.3f}"
        )

        return context, aggregated_sources, query_type, confidence_score

    def _aggregate_scores_noisy_or(self, sources: List[Dict]) -> List[Dict]:
        """
        Deduplicate sources and aggregate scores using Noisy OR formula

        The Noisy OR aggregation treats multiple chunks from the same document
        as independent pieces of evidence. The probability that at least one
        chunk is relevant is: P(relevant) = 1 - ∏(1 - score_i)

        This rewards having multiple matching chunks from the same document,
        giving higher confidence when evidence appears repeatedly.

        Args:
            sources: List of source dictionaries with file_path, file_type, and score

        Returns:
            List of unique sources with aggregated scores, chunk_count, and confidence_label
        """
        if not sources:
            return []

        # Group sources by file_path
        file_groups = defaultdict(list)
        for source in sources:
            file_path = source.get("file_path", "")
            file_groups[file_path].append(source)

        # Aggregate scores for each unique file
        aggregated_sources = []
        for file_path, chunks in file_groups.items():
            # Get file_type from first chunk (all chunks from same file have same type)
            file_type = chunks[0].get("file_type", "")

            # Apply Noisy OR formula: P(relevant) = 1 - ∏(1 - score_i)
            # This treats each chunk as independent evidence
            prob_not_relevant = 1.0
            for chunk in chunks:
                chunk_score = chunk.get("score", 0)
                # Ensure score is in valid range [0, 1]
                chunk_score = max(0.0, min(1.0, chunk_score))
                prob_not_relevant *= (1 - chunk_score)

            # Final aggregated score
            aggregated_score = 1 - prob_not_relevant

            # Get confidence label for this score
            confidence_label = self._get_confidence_label(aggregated_score)

            aggregated_sources.append({
                "file_path": file_path,
                "file_type": file_type,
                "score": aggregated_score,
                "chunk_count": len(chunks),
                "confidence_label": confidence_label
            })

        # Sort by aggregated score (highest first)
        aggregated_sources.sort(key=lambda x: x["score"], reverse=True)

        logger.debug(
            f"Aggregated {len(sources)} chunks into {len(aggregated_sources)} unique sources"
        )

        return aggregated_sources

    def _get_confidence_label(self, score: float) -> str:
        """
        Map numeric confidence score to categorical label

        Thresholds based on empirical analysis of retrieval quality:
        - Very High (≥0.85): Strong evidence, highly relevant content
        - High (≥0.70): Good evidence, clearly relevant
        - Medium (≥0.50): Moderate evidence, potentially relevant
        - Low (<0.50): Weak evidence, uncertain relevance

        Args:
            score: Numeric confidence score in range [0, 1]

        Returns:
            Confidence label string
        """
        if score >= 0.85:
            return "Very High"
        elif score >= 0.70:
            return "High"
        elif score >= 0.50:
            return "Medium"
        else:
            return "Low"

    def _calculate_answer_confidence(
        self,
        sources: List[Dict],
        query: str,
        query_type: str
    ) -> float:
        """
        Calculate multi-factor confidence score for retrieval quality

        Combines multiple signals to provide a calibrated confidence estimate:
        1. Base retrieval score (weighted combination of max and average)
        2. Evidence quality multiplier (based on number of matching chunks)
        3. Query complexity boost (complex queries get conservative boost)
        4. Source coverage boost (diverse file types indicate thorough retrieval)
        5. Chunk density boost (multiple chunks from same file = strong evidence)

        Args:
            sources: List of retrieved sources with scores
            query: User query
            query_type: Classified query type

        Returns:
            Confidence score in range [0, 1]
        """
        if not sources:
            return 0.0

        # Extract scores from sources
        scores = [s.get("score", 0) for s in sources]

        # 1. Base Score: Weighted combination of max and average top-3
        # This balances the highest quality match with broader evidence
        max_score = max(scores)
        top_3_scores = sorted(scores, reverse=True)[:3]
        avg_top_3 = sum(top_3_scores) / len(top_3_scores) if top_3_scores else 0

        base_score = 0.7 * max_score + 0.3 * avg_top_3

        # 2. Evidence Quality Multiplier
        # More matching chunks = stronger evidence
        total_chunks = sum(s.get("chunk_count", 1) for s in sources)

        if total_chunks >= 8:
            # Very strong evidence: multiple chunks from multiple sources
            evidence_multiplier = 1.15
        elif total_chunks >= 5:
            # Good evidence: several chunks
            evidence_multiplier = 1.10
        elif total_chunks <= 2:
            # Weak evidence: very few chunks
            evidence_multiplier = 0.90
        else:
            # Normal evidence
            evidence_multiplier = 1.0

        # Apply evidence multiplier
        score = base_score * evidence_multiplier

        # 3. Query Complexity Boost
        # Complex queries deserve conservative confidence boost
        query_length = len(query.split())
        complexity_boost = 0.0

        if query_length >= 10:
            # Long, complex query
            complexity_boost = 0.05
        elif query_length >= 6:
            # Moderate complexity
            complexity_boost = 0.03

        # Complex query types also get boost
        if query_type in ["what_sustainability", "what_main_issue"]:
            complexity_boost += 0.05

        score += complexity_boost

        # 4. Source Coverage Boost
        # Diverse file types indicate comprehensive retrieval
        unique_file_types = len(set(s.get("file_type", "") for s in sources))

        if unique_file_types >= 4:
            # Excellent coverage: 4+ different file types
            coverage_boost = 0.08
        elif unique_file_types >= 3:
            # Good coverage: 3 file types
            coverage_boost = 0.05
        elif unique_file_types >= 2:
            # Moderate coverage: 2 file types
            coverage_boost = 0.03
        else:
            # Single file type (no boost)
            coverage_boost = 0.0

        score += coverage_boost

        # 5. Chunk Density Boost
        # Multiple chunks from same file = concentrated relevant content
        max_chunks_per_file = max(s.get("chunk_count", 1) for s in sources)

        if max_chunks_per_file >= 4:
            # Very dense evidence in one file
            density_boost = 0.06
        elif max_chunks_per_file >= 3:
            # Good density
            density_boost = 0.04
        elif max_chunks_per_file >= 2:
            # Moderate density
            density_boost = 0.02
        else:
            density_boost = 0.0

        score += density_boost

        # Clamp final score to [0, 1]
        score = max(0.0, min(1.0, score))

        logger.debug(
            f"Confidence calculation: base={base_score:.3f}, "
            f"evidence={evidence_multiplier:.2f}x, "
            f"complexity_boost={complexity_boost:.3f}, "
            f"coverage_boost={coverage_boost:.3f}, "
            f"density_boost={density_boost:.3f}, "
            f"final={score:.3f}"
        )

        return score

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
