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

from app.core.config import FLAGSHIP_PROJECTS, settings
from app.crawler.governance_extractor import GovernanceExtractor
from app.rag.rag_engine import RAGEngine
from app.models.llm_client import LLMClient
from app.agents.orchestrator import AgenticOrchestrator
from app.services.oss_scraper_service import get_oss_scraper
from app.rag.socio_technical_indexer import get_socio_technical_indexer
from app.services.graph_loader import load_project_graph

router = APIRouter()

# Initialize components
gov_extractor = GovernanceExtractor()
rag_engine = RAGEngine()
llm_client = LLMClient()

# Initialize agentic orchestrator with shared RAG engine
orchestrator = AgenticOrchestrator(rag_engine=rag_engine)

# In-memory storage for dynamically added projects
dynamic_projects = {}


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


class QueryResponse(BaseModel):
    project_id: str
    query: str
    response: str
    sources: List[dict]
    metadata: dict


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

        # Step 1: Index governance documents in RAG system (EXISTING)
        logger.info(f"Indexing governance documents for {project_id}")
        gov_index_result = rag_engine.index_governance_documents(project_id, gov_data)

        # Step 2: Run OSS Scraper to extract issues, PRs, commits (NEW)
        logger.info(f"Scraping socio-technical data for {owner}/{repo}")
        scraper = get_oss_scraper()
        scraper_output = scraper.scrape_project(
            owner=owner,
            repo=repo,
            max_issues=500,  # Limit for initial version
            max_prs=500,
            max_commits=1000
        )

        # Initialize counters
        socio_tech_stats = {"issues_indexed": 0, "prs_indexed": 0, "commits_indexed": 0}
        graph_loaded = False

        # Step 3: Index socio-technical data (issues, PRs, commits) into RAG (NEW)
        if scraper_output.get("status") == "success":
            logger.info(f"Indexing socio-technical data for {project_id}")
            try:
                indexer = get_socio_technical_indexer(rag_engine)
                socio_tech_stats = await indexer.index_project_data(project_id, scraper_output)
                logger.success(f"Indexed {socio_tech_stats['total_chunks']} socio-technical chunks")
            except Exception as e:
                logger.error(f"Error indexing socio-technical data: {e}")
                socio_tech_stats["error"] = str(e)

            # Step 4: Load project-specific Graph RAG (NEW)
            if "commit_file_dev_csv" in scraper_output:
                logger.info(f"Loading Graph RAG for {project_id}")
                try:
                    graph_loader = load_project_graph(
                        project_id=project_id,
                        csv_path=scraper_output["commit_file_dev_csv"]
                    )
                    graph_stats = graph_loader.get_network_stats()
                    graph_loaded = True
                    logger.success(f"Loaded Graph RAG: {graph_stats.get('total_developers', 0)} developers, "
                                 f"{graph_stats.get('total_files', 0)} files")
                except Exception as e:
                    logger.error(f"Error loading Graph RAG: {e}")
                    socio_tech_stats["graph_error"] = str(e)
        else:
            logger.warning(f"Scraper returned non-success status: {scraper_output.get('status')}")
            socio_tech_stats["scraper_error"] = scraper_output.get("error", "Unknown error")

        return {
            "status": "success",
            "message": f"Successfully added {owner}/{repo} with full socio-technical data",
            "project": project,
            "extraction": {
                "files_found": len(gov_data.get("files", {})),
                "extraction_time": gov_data.get("metadata", {}).get("extraction_time_seconds", 0),
            },
            "indexing": {
                "governance": gov_index_result,
                "socio_technical": socio_tech_stats,
                "graph_loaded": graph_loaded,
                "total_indexed": gov_index_result.get("indexed", 0) + socio_tech_stats.get("total_chunks", 0)
            },
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
    """Query governance documents using RAG with cosine similarity"""
    logger.info(
        f"Query request for project {request.project_id}: '{request.query}'"
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
        # Use RAG engine to get relevant context with cosine similarity
        context, sources = rag_engine.get_context_for_query(
            request.query,
            request.project_id,
            max_chunks=request.max_results,
        )

        if not context:
            return QueryResponse(
                project_id=request.project_id,
                query=request.query,
                response="No relevant governance documents found for this project. Please make sure the project has been crawled first.",
                sources=[],
                metadata={"has_context": False},
            )

        # Build conversation history for LLM
        conversation_history = []
        if request.conversation_history:
            for msg in request.conversation_history:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Generate LLM response with conversation history
        llm_response = await llm_client.generate_response(
            query=request.query,
            context=context,
            project_name=project["name"],
            temperature=request.temperature,
            conversation_history=conversation_history,
        )

        return QueryResponse(
            project_id=request.project_id,
            query=request.query,
            response=llm_response.get("response", ""),
            sources=sources,
            metadata={
                "has_context": True,
                "context_length": len(context),
                "llm_model": llm_response.get("model"),
                "generation_time_ms": llm_response.get("total_duration_ms"),
                "tokens_generated": llm_response.get("eval_count"),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query_governance: {e}")
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
        # Get context from RAG
        context, sources = rag_engine.get_context_for_query(
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


@router.post("/query/agentic", response_model=QueryResponse)
async def query_agentic(request: QueryRequest):
    """
    Agentic query endpoint with intent routing

    This endpoint uses the agentic RAG system:
    1. Intent router classifies query (deterministic + LLM)
    2. Routes to specialized agent (General LLM or Governance RAG)
    3. Agent processes query and returns grounded response

    Solves the "Hello" problem - responds naturally to greetings
    without citing governance documents inappropriately

    Note: project_id is optional. If not provided, only conversational queries will work.
    """
    logger.info(
        f"Agentic query for project {request.project_id}: '{request.query}'"
    )

    # Verify project exists (if project_id provided)
    # For conversational queries (Hello, What can you do), project is optional
    project = None
    if request.project_id:
        project = next(
            (p for p in FLAGSHIP_PROJECTS if p["id"] == request.project_id), None
        )
        if not project and request.project_id in dynamic_projects:
            project = dynamic_projects[request.project_id]
        # Don't raise error - let orchestrator decide if project is needed based on intent

    try:
        # Build conversation history
        conversation_history = []
        if request.conversation_history:
            for msg in request.conversation_history:
                conversation_history.append({
                    "role": msg.role,
                    "content": msg.content
                })

        # Process query through agentic orchestrator
        result = await orchestrator.process_query(
            query=request.query,
            project_id=request.project_id,
            conversation_history=conversation_history,
        )

        return QueryResponse(
            project_id=request.project_id or "general",
            query=request.query,
            response=result.get("response", ""),
            sources=result.get("sources", []),
            metadata=result.get("metadata", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in agentic query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/agentic/stats")
async def get_agentic_stats():
    """Get agentic system statistics"""
    try:
        stats = orchestrator.get_stats()
        return {
            "status": "operational",
            "agentic_system": stats,
        }
    except Exception as e:
        logger.error(f"Error getting agentic stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
