"""
Socio-Technical Data Indexer
Indexes issues, PRs, and commits into RAG for comprehensive project querying
"""
import csv
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple
from loguru import logger

from app.rag.rag_engine import RAGEngine


class SocioTechnicalIndexer:
    """
    Indexes GitHub socio-technical data into RAG

    Data Sources:
    - Issues CSV (from OSSScraperService)
    - Pull Requests CSV
    - Commits CSV (basic metadata, not full file changes)

    Purpose:
    - Enable queries like "What issues are open for bug fixes?"
    - "Show me PRs from contributor X"
    - "What was committed in the last month?"
    """

    def __init__(self, rag_engine: RAGEngine = None):
        """Initialize indexer with RAG engine"""
        self.rag_engine = rag_engine or RAGEngine()
        logger.info("SocioTechnicalIndexer initialized")

    async def index_project_data(
        self,
        project_id: str,
        scraper_output: Dict[str, str]
    ) -> Dict[str, int]:
        """
        Index all socio-technical data for a project

        Args:
            project_id: Unique project identifier
            scraper_output: Dict with paths to CSV files from scraper

        Returns:
            Dict with indexing statistics
        """
        logger.info(f"Indexing socio-technical data for {project_id}")

        stats = {
            "issues_indexed": 0,
            "prs_indexed": 0,
            "commits_indexed": 0,
            "total_chunks": 0
        }

        # Index issues
        if "issues_csv" in scraper_output and Path(scraper_output["issues_csv"]).exists():
            stats["issues_indexed"] = await self._index_issues(
                project_id,
                scraper_output["issues_csv"]
            )

        # Index pull requests
        if "prs_csv" in scraper_output and Path(scraper_output["prs_csv"]).exists():
            stats["prs_indexed"] = await self._index_pull_requests(
                project_id,
                scraper_output["prs_csv"]
            )

        # Index commit summaries (not full file changes - that's for Graph RAG)
        if "commits_csv" in scraper_output and Path(scraper_output["commits_csv"]).exists():
            stats["commits_indexed"] = await self._index_commit_summaries(
                project_id,
                scraper_output["commits_csv"]
            )

        stats["total_chunks"] = (
            stats["issues_indexed"] +
            stats["prs_indexed"] +
            stats["commits_indexed"]
        )

        logger.success(
            f"Indexed {stats['total_chunks']} socio-technical chunks for {project_id}"
        )

        return stats

    async def _index_issues(self, project_id: str, issues_csv: str) -> int:
        """
        Index GitHub issues into RAG

        Each issue becomes a searchable document with:
        - Title, body, author, state, labels
        - Allows queries like "What issues mention authentication?"
        """
        logger.info(f"Indexing issues from {issues_csv}")

        documents = []
        metadatas = []
        ids = []

        with open(issues_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Create searchable document text
                doc_text = f"""
ISSUE #{row['number']}: {row['title']}

Status: {row['state']}
Author: {row['author']} ({row['author_association']})
Created: {row['created_at']}
Updated: {row['updated_at']}
Labels: {row['labels']}
Comments: {row['comments_count']}

Description:
{row['body']}

URL: {row['url']}
"""

                # Create metadata
                metadata = {
                    "project_id": project_id,
                    "file_type": "issue",
                    "issue_number": row['number'],
                    "issue_state": row['state'],
                    "issue_author": row['author'],
                    "issue_labels": row['labels'],
                    "file_path": f"issues/#{row['number']}",  # Virtual path for UI
                }

                # Generate unique ID
                doc_id = hashlib.md5(
                    f"{project_id}_issue_{row['number']}".encode()
                ).hexdigest()

                documents.append(doc_text)
                metadatas.append(metadata)
                ids.append(doc_id)

        # Batch add to RAG engine
        if documents:
            logger.info(f"Adding {len(documents)} issues to vector store...")

            # Generate embeddings
            embeddings = self.rag_engine.embedder.embed_documents(
                documents,
                batch_size=100,
                show_progress=False
            )

            # Add to vector store
            self.rag_engine.vector_store.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )

            # Build BM25 index for issues
            self._update_bm25_index(project_id, documents, ids, metadatas)

            logger.success(f"Indexed {len(documents)} issues")

        return len(documents)

    async def _index_pull_requests(self, project_id: str, prs_csv: str) -> int:
        """
        Index GitHub pull requests into RAG

        Each PR becomes searchable with:
        - Title, body, author, state, reviewers
        - File changes summary
        """
        logger.info(f"Indexing pull requests from {prs_csv}")

        documents = []
        metadatas = []
        ids = []

        with open(prs_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                # Create searchable document text
                doc_text = f"""
PULL REQUEST #{row['number']}: {row['title']}

Status: {row['state']}
Author: {row['author']}
Created: {row['created_at']}
Updated: {row['updated_at']}
Merged: {row['merged_at']}
Labels: {row['labels']}

Changes:
- Files changed: {row['changed_files']}
- Lines added: {row['additions']}
- Lines deleted: {row['deletions']}
- Comments: {row['comments_count']}

Description:
{row['body']}

URL: {row['url']}
"""

                # Create metadata
                metadata = {
                    "project_id": project_id,
                    "file_type": "pull_request",
                    "pr_number": row['number'],
                    "pr_state": row['state'],
                    "pr_author": row['author'],
                    "pr_merged": row['merged_at'] != '',
                    "file_path": f"pull-requests/#{row['number']}",
                }

                # Generate unique ID
                doc_id = hashlib.md5(
                    f"{project_id}_pr_{row['number']}".encode()
                ).hexdigest()

                documents.append(doc_text)
                metadatas.append(metadata)
                ids.append(doc_id)

        # Batch add to RAG engine
        if documents:
            logger.info(f"Adding {len(documents)} PRs to vector store...")

            # Generate embeddings
            embeddings = self.rag_engine.embedder.embed_documents(
                documents,
                batch_size=100,
                show_progress=False
            )

            # Add to vector store
            self.rag_engine.vector_store.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )

            # Update BM25 index
            self._update_bm25_index(project_id, documents, ids, metadatas)

            logger.success(f"Indexed {len(documents)} pull requests")

        return len(documents)

    async def _index_commit_summaries(self, project_id: str, commits_csv: str) -> int:
        """
        Index commit summaries (aggregated per commit, not per file)

        This creates searchable commit records for queries like:
        "What was committed by developer X?"
        "Show me commits related to authentication"

        Note: Full file-level commit data is for Graph RAG (loaded separately)
        """
        logger.info(f"Indexing commit summaries from {commits_csv}")

        # Read CSV and aggregate by commit
        commits_by_hash = {}

        with open(commits_csv, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)

            for row in reader:
                # CSV format: project_name, incubation_start, incubation_end, status,
                #            commit_number, commit_hash, author_email, author_name,
                #            commit_date, commit_timestamp, file_path, change_type,
                #            lines_added, lines_deleted

                if len(row) < 14:
                    continue

                commit_hash = row[5]
                author_name = row[7]
                author_email = row[6]
                commit_date = row[8]
                file_path = row[10]
                change_type = row[11]
                lines_added = int(row[12]) if row[12] and row[12] != '' else 0
                lines_deleted = int(row[13]) if row[13] and row[13] != '' else 0

                if commit_hash not in commits_by_hash:
                    commits_by_hash[commit_hash] = {
                        "author_name": author_name,
                        "author_email": author_email,
                        "commit_date": commit_date,
                        "files": [],
                        "total_additions": 0,
                        "total_deletions": 0
                    }

                if file_path:
                    commits_by_hash[commit_hash]["files"].append({
                        "path": file_path,
                        "change_type": change_type,
                        "additions": lines_added,
                        "deletions": lines_deleted
                    })
                    commits_by_hash[commit_hash]["total_additions"] += lines_added
                    commits_by_hash[commit_hash]["total_deletions"] += lines_deleted

        # Create documents from aggregated commits
        documents = []
        metadatas = []
        ids = []

        for commit_hash, commit_data in commits_by_hash.items():
            # Only index commits with meaningful changes
            if len(commit_data["files"]) == 0:
                continue

            # Create searchable text
            files_summary = "\n".join([
                f"  - {f['path']} ({f['change_type']}: +{f['additions']}/-{f['deletions']})"
                for f in commit_data["files"][:20]  # Limit to first 20 files
            ])

            doc_text = f"""
COMMIT {commit_hash[:8]}

Author: {commit_data['author_name']} <{commit_data['author_email']}>
Date: {commit_data['commit_date']}

Changes:
- Files modified: {len(commit_data['files'])}
- Lines added: {commit_data['total_additions']}
- Lines deleted: {commit_data['total_deletions']}

Files changed:
{files_summary}
"""

            metadata = {
                "project_id": project_id,
                "file_type": "commit",
                "commit_hash": commit_hash,
                "commit_author": commit_data['author_name'],
                "commit_date": commit_data['commit_date'],
                "files_changed": len(commit_data['files']),
                "file_path": f"commits/{commit_hash[:8]}",
            }

            doc_id = hashlib.md5(
                f"{project_id}_commit_{commit_hash}".encode()
            ).hexdigest()

            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(doc_id)

        # Batch add to RAG engine
        if documents:
            logger.info(f"Adding {len(documents)} commit summaries to vector store...")

            # Generate embeddings
            embeddings = self.rag_engine.embedder.embed_documents(
                documents,
                batch_size=100,
                show_progress=False
            )

            # Add to vector store
            self.rag_engine.vector_store.add(
                documents=documents,
                embeddings=embeddings.tolist(),
                metadatas=metadatas,
                ids=ids
            )

            # Update BM25 index
            self._update_bm25_index(project_id, documents, ids, metadatas)

            logger.success(f"Indexed {len(documents)} commit summaries")

        return len(documents)

    def _update_bm25_index(
        self,
        project_id: str,
        documents: List[str],
        ids: List[str],
        metadatas: List[Dict]
    ):
        """Update BM25 index with new documents"""
        try:
            if project_id not in self.rag_engine.bm25_indices:
                # Initialize new BM25 index
                from rank_bm25 import BM25Okapi

                tokenized_docs = [self.rag_engine._tokenize(doc) for doc in documents]
                bm25 = BM25Okapi(tokenized_docs)

                self.rag_engine.bm25_indices[project_id] = {
                    "bm25": bm25,
                    "documents": documents,
                    "ids": ids,
                    "metadatas": metadatas
                }
            else:
                # Append to existing index
                existing = self.rag_engine.bm25_indices[project_id]
                existing["documents"].extend(documents)
                existing["ids"].extend(ids)
                existing["metadatas"].extend(metadatas)

                # Rebuild BM25 with all documents
                from rank_bm25 import BM25Okapi
                all_docs = existing["documents"]
                tokenized_docs = [self.rag_engine._tokenize(doc) for doc in all_docs]
                existing["bm25"] = BM25Okapi(tokenized_docs)

            # Save updated index
            self.rag_engine._save_bm25_index(project_id)

            logger.debug(f"Updated BM25 index for {project_id}")

        except Exception as e:
            logger.error(f"Error updating BM25 index: {e}")


# Singleton instance
_indexer_instance: "SocioTechnicalIndexer" = None


def get_socio_technical_indexer(rag_engine: RAGEngine = None) -> SocioTechnicalIndexer:
    """Get or create singleton indexer instance"""
    global _indexer_instance

    if _indexer_instance is None:
        _indexer_instance = SocioTechnicalIndexer(rag_engine=rag_engine)

    return _indexer_instance
