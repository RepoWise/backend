"""
API Routes for OSSPREY-GOV-POC
Handles project management, governance crawling, and RAG queries
"""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl, validator
from loguru import logger
import re
import json
from pathlib import Path

from app.core.config import FLAGSHIP_PROJECTS, settings
from app.crawler.governance_extractor import GovernanceExtractor
from app.rag.rag_engine import RAGEngine
from app.models.llm_client import LLMClient
from app.models.intent_router import IntentRouter
from app.data.csv_engine import CSVDataEngine
from app.models.question_suggester import QuestionSuggester

router = APIRouter()

# Initialize components
gov_extractor = GovernanceExtractor()
rag_engine = RAGEngine()
llm_client = LLMClient()
intent_router = IntentRouter()
csv_engine = CSVDataEngine(csv_data_dir="data/csv_data", llm_client=llm_client)
question_suggester = QuestionSuggester()

# Persistent storage for dynamically added projects
DYNAMIC_PROJECTS_FILE = Path("data/dynamic_projects.json")
CSV_PATHS_FILE = Path("data/csv_paths.json")


def _load_dynamic_projects() -> dict:
    """Load dynamic projects from disk"""
    if DYNAMIC_PROJECTS_FILE.exists():
        try:
            with open(DYNAMIC_PROJECTS_FILE, "r") as f:
                projects = json.load(f)
                logger.info(f"📂 Loaded {len(projects)} dynamic projects from disk")
                return projects
        except Exception as e:
            logger.error(f"Error loading dynamic projects: {e}")
            return {}
    return {}


def _save_dynamic_projects(projects: dict):
    """Save dynamic projects to disk"""
    try:
        DYNAMIC_PROJECTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(DYNAMIC_PROJECTS_FILE, "w") as f:
            json.dump(projects, f, indent=2)
        logger.debug(f"💾 Saved {len(projects)} dynamic projects to disk")
    except Exception as e:
        logger.error(f"Error saving dynamic projects: {e}")


def _load_csv_paths() -> dict:
    """Load CSV paths configuration from disk"""
    if CSV_PATHS_FILE.exists():
        try:
            with open(CSV_PATHS_FILE, "r") as f:
                paths = json.load(f)
                logger.info(f"📂 Loaded CSV paths for {len(paths)} projects from disk")
                return paths
        except Exception as e:
            logger.error(f"Error loading CSV paths: {e}")
            return {}
    return {}


def _save_csv_paths(csv_paths: dict):
    """Save CSV paths configuration to disk"""
    try:
        CSV_PATHS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CSV_PATHS_FILE, "w") as f:
            json.dump(csv_paths, f, indent=2)
        logger.debug(f"💾 Saved CSV paths for {len(csv_paths)} projects to disk")
    except Exception as e:
        logger.error(f"Error saving CSV paths: {e}")


def _auto_load_csv_data():
    """Auto-load CSV data from saved paths on server startup"""
    csv_paths = _load_csv_paths()
    if not csv_paths:
        logger.info("No CSV paths to auto-load")
        return

    logger.info(f"🔄 Auto-loading CSV data for {len(csv_paths)} projects...")
    for project_id, paths in csv_paths.items():
        try:
            result = csv_engine.load_project_data(
                project_id,
                commits_path=paths.get("commits_csv_path"),
                issues_path=paths.get("issues_csv_path")
            )
            logger.info(f"✅ Auto-loaded CSV for {project_id}: commits={result['commits_loaded']}, issues={result['issues_loaded']}")
        except Exception as e:
            logger.error(f"Error auto-loading CSV for {project_id}: {e}")


# Load dynamic projects from disk on startup
dynamic_projects = _load_dynamic_projects()

# Auto-load CSV data on startup
_auto_load_csv_data()


# Pydantic Models
class Project(BaseModel):
    id: str
    name: str
    owner: str
    repo: str
    description: str
    foundation: str
    governance_url: str


class CrawlRequest(BaseModel):
    project_id: str
    use_cache: bool = True


class ConversationMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class QueryRequest(BaseModel):
    project_id: Optional[str] = None  # Optional for conversational queries
    query: str
    max_results: int = 5
    temperature: float = 0.3
    stream: bool = False
    conversation_history: Optional[List[ConversationMessage]] = None


class SearchRequest(BaseModel):
    project_id: Optional[str] = None
    query: str
    n_results: int = 5
    file_types: Optional[List[str]] = None


class AddRepositoryRequest(BaseModel):
    github_url: str

    @validator('github_url')
    def validate_github_url(cls, v):
        """Validate and parse GitHub URL"""
        # Support various GitHub URL formats
        patterns = [
            r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
            r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
            r'([^/]+)/([^/]+)$'  # Simple owner/repo format
        ]

        for pattern in patterns:
            match = re.match(pattern, v.strip())
            if match:
                return v.strip()

        raise ValueError('Invalid GitHub URL format. Expected: https://github.com/owner/repo or owner/repo')


class LoadCSVRequest(BaseModel):
    commits_csv_path: Optional[str] = None
    issues_csv_path: Optional[str] = None


class QueryResponse(BaseModel):
    project_id: str
    query: str
    response: str
    sources: List[dict]
    metadata: dict
    suggested_questions: Optional[List[str]] = []


# Helper functions
def parse_github_url(url: str) -> tuple:
    """
    Parse GitHub URL and return (owner, repo)
    Supports various formats:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    - owner/repo
    """
    patterns = [
        r'https?://github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$',
        r'git@github\.com:([^/]+)/([^/]+?)(?:\.git)?$',
        r'^([^/]+)/([^/]+)$'
    ]

    for pattern in patterns:
        match = re.match(pattern, url.strip())
        if match:
            owner, repo = match.groups()
            # Remove .git suffix if present
            repo = repo.replace('.git', '')
            return owner, repo

    raise ValueError(f'Invalid GitHub URL: {url}')


# Routes
@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/system-status")
async def system_status():
    """Get system status including Ollama availability"""
    try:
        model_status = await llm_client.check_model_availability()
        collection_stats = rag_engine.get_collection_stats()

        return {
            "status": "operational",
            "llm": model_status,
            "rag": collection_stats,
            "config": {
                "ollama_host": settings.ollama_host,
                "ollama_model": settings.ollama_model,
                "embedding_model": settings.embedding_model,
            },
        }
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/projects", response_model=List[Project])
async def list_projects():
    """Get list of available OSS projects (flagship + dynamic)"""
    all_projects = list(FLAGSHIP_PROJECTS)
    # Add dynamically added projects
    all_projects.extend(dynamic_projects.values())
    return all_projects


@router.post("/projects/add")
async def add_repository(request: AddRepositoryRequest):
    """Add a new repository from GitHub URL"""
    logger.info(f"Add repository request: {request.github_url}")

    try:
        # Parse GitHub URL
        owner, repo = parse_github_url(request.github_url)
        project_id = f"{owner}-{repo}".lower()

        # Check if project already exists
        existing = next((p for p in FLAGSHIP_PROJECTS if p["id"] == project_id), None)
        if existing:
            return {
                "status": "already_exists",
                "message": f"Project {owner}/{repo} already exists as a flagship project",
                "project": existing,
            }

        if project_id in dynamic_projects:
            return {
                "status": "already_exists",
                "message": f"Project {owner}/{repo} has already been added",
                "project": dynamic_projects[project_id],
            }

        # Extract governance documents
        logger.info(f"Extracting governance documents for {owner}/{repo}")
        gov_data = gov_extractor.extract_governance_documents(owner, repo, use_cache=True)

        if "error" in gov_data:
            raise HTTPException(
                status_code=400, detail=f"Error extracting governance: {gov_data['error']}"
            )

        # Create project object
        project = {
            "id": project_id,
            "name": repo,
            "owner": owner,
            "repo": repo,
            "description": f"Custom repository: {owner}/{repo}",
            "foundation": "Custom",
            "governance_url": f"https://github.com/{owner}/{repo}",
        }

        # Store in dynamic projects
        dynamic_projects[project_id] = project
        _save_dynamic_projects(dynamic_projects)  # Persist to disk

        # Index governance documents in RAG system
        logger.info(f"Indexing governance documents for {project_id}")
        index_result = rag_engine.index_governance_documents(project_id, gov_data)

        return {
            "status": "success",
            "message": f"Successfully added {owner}/{repo}",
            "project": project,
            "extraction": {
                "files_found": len(gov_data.get("files", {})),
                "extraction_time": gov_data.get("metadata", {}).get("extraction_time_seconds", 0),
            },
            "indexing": index_result,
            "summary": gov_extractor.get_extraction_summary(gov_data),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get details for a specific project"""
    # Check flagship projects first
    project = next((p for p in FLAGSHIP_PROJECTS if p["id"] == project_id), None)

    # Then check dynamic projects
    if not project and project_id in dynamic_projects:
        project = dynamic_projects[project_id]

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if governance data is indexed
    try:
        collection_stats = rag_engine.get_collection_stats()
        is_indexed = project_id in collection_stats.get("project_distribution", {})
        chunk_count = collection_stats.get("project_distribution", {}).get(project_id, 0)

        return {
            **project,
            "indexed": is_indexed,
            "chunk_count": chunk_count,
        }
    except Exception as e:
        logger.error(f"Error getting project {project_id}: {e}")
        return {
            **project,
            "indexed": False,
            "chunk_count": 0,
        }


@router.post("/projects/{project_id}/load-csv")
async def load_csv_data(project_id: str, request: LoadCSVRequest):
    """
    Load CSV data (commits and/or issues) for a project

    This enables querying commits and issues data alongside governance documents.
    """
    logger.info(f"Load CSV request for project: {project_id}")

    # Verify project exists
    project = next((p for p in FLAGSHIP_PROJECTS if p["id"] == project_id), None)
    if not project and project_id in dynamic_projects:
        project = dynamic_projects[project_id]
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not request.commits_csv_path and not request.issues_csv_path:
        raise HTTPException(status_code=400, detail="At least one CSV path must be provided")

    try:
        # Load CSV data
        result = csv_engine.load_project_data(
            project_id,
            commits_path=request.commits_csv_path,
            issues_path=request.issues_csv_path
        )

        # Save CSV paths to disk for auto-reload on server restart
        if result.get("commits_loaded") or result.get("issues_loaded"):
            csv_paths = _load_csv_paths()
            csv_paths[project_id] = {
                "commits_csv_path": request.commits_csv_path,
                "issues_csv_path": request.issues_csv_path
            }
            _save_csv_paths(csv_paths)
            logger.info(f"💾 Saved CSV paths for {project_id} to disk for auto-reload")

        # Get statistics
        available_data = csv_engine.get_available_data(project_id)

        return {
            "status": "success",
            "project_id": project_id,
            "loaded": result,
            "available_data": available_data,
            "message": f"Successfully loaded CSV data for {project['name']}"
        }

    except Exception as e:
        logger.error(f"Error loading CSV data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/crawl/{project_id}")
async def crawl_governance(project_id: str, background_tasks: BackgroundTasks, use_cache: bool = True):
    """Crawl and index governance documents for a project"""
    logger.info(f"Crawl request for project: {project_id}")

    # Find project
    project = next((p for p in FLAGSHIP_PROJECTS if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Extract governance documents
        logger.info(f"Extracting governance documents for {project['owner']}/{project['repo']}")
        gov_data = gov_extractor.extract_governance_documents(
            project["owner"], project["repo"], use_cache=use_cache
        )

        if "error" in gov_data:
            raise HTTPException(
                status_code=500,
                detail=f"Error extracting governance: {gov_data['error']}",
            )

        # Index in RAG system
        logger.info(f"Indexing documents for {project_id}")
        index_result = rag_engine.index_governance_documents(project_id, gov_data)

        return {
            "project_id": project_id,
            "status": "success",
            "extraction": {
                "files_found": len(gov_data.get("files", {})),
                "extraction_time": gov_data.get("metadata", {}).get(
                    "extraction_time_seconds", 0
                ),
            },
            "indexing": index_result,
            "summary": gov_extractor.get_extraction_summary(gov_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in crawl_governance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance/{project_id}")
async def get_governance_data(project_id: str):
    """Get cached governance data for a project"""
    project = next((p for p in FLAGSHIP_PROJECTS if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Try to load from cache
        cached = gov_extractor._load_from_cache(project["owner"], project["repo"])

        if not cached:
            raise HTTPException(
                status_code=404,
                detail="Governance data not found. Please crawl the project first.",
            )

        # Return summary without full content
        files_summary = {
            file_type: {
                "path": file_data.get("path"),
                "content_length": file_data.get("content_length", 0),
                "fetched_at": file_data.get("fetched_at"),
            }
            for file_type, file_data in cached.get("files", {}).items()
        }

        return {
            "project_id": project_id,
            "owner": cached.get("owner"),
            "repo": cached.get("repo"),
            "extracted_at": cached.get("extracted_at"),
            "files": files_summary,
            "metadata": cached.get("metadata"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting governance data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_governance(request: QueryRequest):
    """
    Multi-Modal Query Endpoint with Intent Routing

    Routes queries to appropriate pipeline:
    - GENERAL: Direct LLM (no RAG)
    - GOVERNANCE: Vector RAG (ChromaDB)
    - COMMITS: CSV Query Engine
    - ISSUES: CSV Query Engine
    """
    logger.info(f"Query request: '{request.query}' | Project: {request.project_id}")

    # Step 1: Classify intent
    has_project_context = request.project_id is not None
    intent, confidence = intent_router.classify_intent(request.query, has_project_context)

    logger.info(f"🎯 Intent: {intent} (confidence: {confidence:.2f})")

    # Step 2: Route to appropriate handler
    try:
        if intent == "OUT_OF_SCOPE":
            # Return a polite message for out-of-scope queries
            # Get initial suggestions for when no query has been made
            suggested_questions = question_suggester.get_initial_suggestions()

            return QueryResponse(
                project_id=request.project_id or "general",
                query=request.query,
                response="I'm a project governance assistant designed to help you understand open-source project documentation, contribution guidelines, maintainers, issues, and commit history. Please ask me questions about the selected project's governance, contributors, issues, or commits.",
                sources=[],
                metadata={
                    "intent": intent,
                    "confidence": confidence,
                    "data_source": "out_of_scope",
                },
                suggested_questions=suggested_questions,
            )

        elif intent == "GENERAL":
            # Direct LLM response (no RAG, no project data)
            llm_response = await llm_client.generate_response(
                query=request.query,
                context="You are a helpful AI assistant. Answer the user's question based on your knowledge.",
                project_name="General",
                temperature=request.temperature,
                query_type="general",
            )

            # Get initial suggestions for general queries
            suggested_questions = question_suggester.get_initial_suggestions()

            return QueryResponse(
                project_id=request.project_id or "general",
                query=request.query,
                response=llm_response.get("response", ""),
                sources=[],
                metadata={
                    "intent": intent,
                    "confidence": confidence,
                    "data_source": "llm_knowledge",
                    "llm_model": llm_response.get("model"),
                    "generation_time_ms": llm_response.get("total_duration_ms"),
                },
                suggested_questions=suggested_questions,
            )

        # For project-specific intents, verify project exists
        if not request.project_id:
            suggested_questions = question_suggester.get_initial_suggestions()
            return QueryResponse(
                project_id="none",
                query=request.query,
                response="Please select a project first to query project-specific information.",
                sources=[],
                metadata={"intent": intent, "error": "no_project_selected"},
                suggested_questions=suggested_questions,
            )

        project = next((p for p in FLAGSHIP_PROJECTS if p["id"] == request.project_id), None)
        if not project and request.project_id in dynamic_projects:
            project = dynamic_projects[request.project_id]
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if intent == "GOVERNANCE":
            # Use existing ChromaDB vector RAG
            context, sources, query_type = rag_engine.get_context_for_query(
                request.query,
                request.project_id,
                max_chunks=request.max_results,
            )

            if not context:
                suggested_questions = question_suggester.get_initial_suggestions()
                return QueryResponse(
                    project_id=request.project_id,
                    query=request.query,
                    response="No relevant governance documents found for this project. Please make sure the project has been crawled first.",
                    sources=[],
                    metadata={"intent": intent, "has_context": False},
                    suggested_questions=suggested_questions,
                )

            # Build conversation history
            conversation_history = []
            if request.conversation_history:
                for msg in request.conversation_history:
                    conversation_history.append({"role": msg.role, "content": msg.content})

            llm_response = await llm_client.generate_response(
                query=request.query,
                context=context,
                project_name=project["name"],
                temperature=request.temperature,
                conversation_history=conversation_history,
                query_type=query_type,
            )

            # Generate contextual follow-up questions
            suggested_questions = question_suggester.suggest_questions(
                current_query=request.query,
                intent=intent,
                answer=llm_response.get("response", ""),
                project_context={"project_name": project["name"], "project_id": request.project_id}
            )

            return QueryResponse(
                project_id=request.project_id,
                query=request.query,
                response=llm_response.get("response", ""),
                sources=sources,
                metadata={
                    "intent": intent,
                    "confidence": confidence,
                    "data_source": "vector_db",
                    "context_length": len(context),
                    "llm_model": llm_response.get("model"),
                    "generation_time_ms": llm_response.get("total_duration_ms"),
                },
                suggested_questions=suggested_questions,
            )

        elif intent in ["COMMITS", "ISSUES"]:
            # Use CSV Query Engine
            data_type = "commits" if intent == "COMMITS" else "issues"

            # Check if CSV data is available
            available_data = csv_engine.get_available_data(request.project_id)
            if not available_data.get(data_type):
                suggested_questions = question_suggester.get_initial_suggestions()
                return QueryResponse(
                    project_id=request.project_id,
                    query=request.query,
                    response=f"No {data_type} data available for this project. Please load the CSV data first.",
                    sources=[],
                    metadata={
                        "intent": intent,
                        "data_source": "csv",
                        "error": f"no_{data_type}_data"
                    },
                    suggested_questions=suggested_questions,
                )

            # Get context from CSV engine
            context, records = csv_engine.get_context_for_query(
                request.project_id,
                request.query,
                data_type
            )

            if not context or len(records) == 0:
                suggested_questions = question_suggester.suggest_questions(
                    current_query=request.query,
                    intent=intent,
                    answer=None,
                    project_context={"project_name": project["name"], "project_id": request.project_id}
                )
                return QueryResponse(
                    project_id=request.project_id,
                    query=request.query,
                    response=f"No {data_type} data found matching your query.",
                    sources=[],
                    metadata={"intent": intent, "data_source": "csv"},
                    suggested_questions=suggested_questions,
                )

            # Check if this is an aggregation query (how many, count, total, etc.)
            is_aggregation = intent_router.is_aggregation_query(request.query)

            # For aggregation queries with stats data, format response directly
            if is_aggregation and len(records) > 0:
                first_record = records[0]

                # Check if this is a stats record (has aggregate fields)
                if data_type == "issues" and "total_issues" in first_record:
                    # Format stats directly without LLM
                    total = first_record.get('total_issues', 0)
                    open_count = first_record.get('open_issues', 0)
                    closed_count = first_record.get('closed_issues', 0)
                    unique_reporters = first_record.get('unique_reporters', 0)

                    llm_response_text = f"There are **{open_count} open issues** and **{closed_count} closed issues** ({total} total). These issues were reported by {unique_reporters} unique contributors."

                    # Create single source showing the stats
                    sources = [{
                        "file_path": f"{data_type.capitalize()} Statistics",
                        "file_type": data_type,
                        "score": 1.0,
                        "content": f"Total: {total}, Open: {open_count}, Closed: {closed_count}, Reporters: {unique_reporters}"
                    }]

                    # Generate contextual follow-up questions
                    suggested_questions = question_suggester.suggest_questions(
                        current_query=request.query,
                        intent=intent,
                        answer=llm_response_text,
                        project_context={"project_name": project["name"], "project_id": request.project_id}
                    )

                    return QueryResponse(
                        project_id=request.project_id,
                        query=request.query,
                        response=llm_response_text,
                        sources=sources,
                        metadata={
                            "intent": intent,
                            "data_source": "csv",
                            "query_type": "aggregation",
                            "stats": first_record
                        },
                        suggested_questions=suggested_questions,
                    )

                elif data_type == "commits" and "total_commits" in first_record:
                    # Format commit stats directly
                    total = first_record.get('total_commits', 0)
                    unique_authors = first_record.get('unique_authors', 0)
                    files_changed = first_record.get('files_changed', 0)

                    llm_response_text = f"There are **{total} total commits** from {unique_authors} unique authors, affecting {files_changed} files."

                    sources = [{
                        "file_path": f"{data_type.capitalize()} Statistics",
                        "file_type": data_type,
                        "score": 1.0,
                        "content": f"Total commits: {total}, Authors: {unique_authors}, Files: {files_changed}"
                    }]

                    # Generate contextual follow-up questions
                    suggested_questions = question_suggester.suggest_questions(
                        current_query=request.query,
                        intent=intent,
                        answer=llm_response_text,
                        project_context={"project_name": project["name"], "project_id": request.project_id}
                    )

                    return QueryResponse(
                        project_id=request.project_id,
                        query=request.query,
                        response=llm_response_text,
                        sources=sources,
                        metadata={
                            "intent": intent,
                            "data_source": "csv",
                            "query_type": "aggregation",
                            "stats": first_record
                        },
                        suggested_questions=suggested_questions,
                    )

            # For non-aggregation queries, use LLM to generate response
            llm_response = await llm_client.generate_response(
                query=request.query,
                context=context,  # Just pass the DataFrame string
                project_name=project["name"],
                temperature=0.0,  # Zero temperature for maximum factual precision, prevent hallucinations
                query_type=data_type,  # "commits" or "issues" - triggers CSV-specific prompting
            )

            # Format sources from CSV records
            sources = []
            for i, record in enumerate(records[:5]):  # Top 5 records
                if data_type == "commits":
                    sources.append({
                        "file_path": f"Commit: {record.get('commit_sha', 'N/A')[:8]}",
                        "file_type": "commits",
                        "score": 1.0 - (i * 0.1),  # Decreasing relevance
                        "content": f"{record.get('name')} - {record.get('filename')} ({record.get('date')})"
                    })
                else:  # issues
                    sources.append({
                        "file_path": f"Issue #{record.get('issue_num', 'N/A')}",
                        "file_type": "issues",
                        "score": 1.0 - (i * 0.1),
                        "content": f"{record.get('title', 'N/A')} by {record.get('user_login', 'N/A')}"
                    })

            # Generate contextual follow-up questions
            suggested_questions = question_suggester.suggest_questions(
                current_query=request.query,
                intent=intent,
                answer=llm_response.get("response", ""),
                project_context={"project_name": project["name"], "project_id": request.project_id}
            )

            return QueryResponse(
                project_id=request.project_id,
                query=request.query,
                response=llm_response.get("response", ""),
                sources=sources,
                metadata={
                    "intent": intent,
                    "confidence": confidence,
                    "data_source": "csv",
                    "records_found": len(records),
                    "llm_model": llm_response.get("model"),
                    "generation_time_ms": llm_response.get("total_duration_ms"),
                },
                suggested_questions=suggested_questions,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/stream")
async def query_governance_stream(request: QueryRequest):
    """Stream LLM response for governance query"""
    logger.info(
        f"Stream query request for project {request.project_id}: '{request.query}'"
    )

    # Verify project exists (check both flagship and dynamic projects)
    project = next(
        (p for p in FLAGSHIP_PROJECTS if p["id"] == request.project_id), None
    )
    if not project and request.project_id in dynamic_projects:
        project = dynamic_projects[request.project_id]
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Get context from RAG with intelligent search
        context, sources, query_type = rag_engine.get_context_for_query(
            request.query,
            request.project_id,
            max_chunks=request.max_results,
        )

        if not context:
            async def error_stream():
                yield "No relevant governance documents found. Please make sure the project has been crawled first."

            return StreamingResponse(error_stream(), media_type="text/plain")

        # Stream LLM response
        return StreamingResponse(
            llm_client.generate_response_stream(
                query=request.query,
                context=context,
                project_name=project["name"],
                temperature=request.temperature,
                query_type=query_type,
            ),
            media_type="text/plain",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query_governance_stream: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_documents(request: SearchRequest):
    """Semantic search in governance documents"""
    logger.info(f"Search request: '{request.query}'")

    try:
        results = rag_engine.search(
            query=request.query,
            project_id=request.project_id,
            n_results=request.n_results,
            file_types=request.file_types,
        )

        return {
            "query": request.query,
            "project_id": request.project_id,
            "total_results": len(results),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error in search_documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/projects/{project_id}/index")
async def delete_project_index(project_id: str):
    """Delete indexed documents for a project"""
    logger.info(f"Delete index request for project: {project_id}")

    try:
        success = rag_engine.delete_project_documents(project_id)

        if success:
            return {"status": "success", "project_id": project_id}
        else:
            raise HTTPException(
                status_code=404, detail="No documents found for project"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting project index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_stats():
    """Get overall system statistics"""
    try:
        collection_stats = rag_engine.get_collection_stats()

        return {
            "collection": collection_stats,
            "projects": {
                "total_available": len(FLAGSHIP_PROJECTS),
                "indexed": collection_stats.get("projects_indexed", 0),
            },
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


