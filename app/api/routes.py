"""
API Routes for RepoWise
Handles project management, document extraction, and RAG-powered queries
"""
from typing import List, Optional, Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl, validator
from loguru import logger
import re

from app.core.config import settings
from app.crawler.project_doc_extractor import ProjectDocExtractor
from app.rag.rag_engine import RAGEngine
from app.models.llm_client import LLMClient
from app.models.intent_router import IntentRouter
from app.data.csv_engine import CSVDataEngine
from app.models.question_suggester import QuestionSuggester
from app.data.repo_scraper_client import RepoScraperClient
from app.models.conversation_manager import ConversationManager

router = APIRouter()

# Initialize components
doc_extractor = ProjectDocExtractor()
rag_engine = RAGEngine()
llm_client = LLMClient()
# Use keyword-based intent classification (single-keyword approach, 67.8% accuracy)
intent_router = IntentRouter(llm_client=llm_client, use_llm_classification=False)
csv_engine = CSVDataEngine(llm_client=llm_client)
question_suggester = QuestionSuggester()

# Initialize API-based data fetching components (NO CACHING)
repo_scraper = RepoScraperClient()

# Note: Projects are now stored in ChromaDB only (no JSON file needed)
# All commits/issues data comes from external API (https://ossprey.ngrok.app)


# Admin endpoint to reset all data
@router.delete("/admin/reset")
async def reset_all_data():
    """
    Reset all data - clears ChromaDB collections and in-memory data cache.
    WARNING: This will delete ALL indexed projects and their data.
    Use with caution!
    """
    logger.warning("⚠️ Admin reset requested - clearing all data")

    try:
        # Reset ChromaDB (deletes all collections and recreates empty one)
        rag_engine.vector_store.reset()
        logger.info("✅ ChromaDB collections cleared")

        # Clear in-memory data cache (commits/issues)
        csv_engine.data_cache.clear()
        logger.info("✅ In-memory data cache cleared")

        return {
            "status": "success",
            "message": "All data has been reset. ChromaDB collections and data cache cleared.",
            "cleared": {
                "chromadb": True,
                "data_cache": True
            }
        }
    except Exception as e:
        logger.error(f"❌ Error during reset: {e}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


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


class ConversationMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class ConversationState(BaseModel):
    """Running summary state for efficient conversation context"""
    running_summary: str = ""
    last_exchange: Optional[Dict[str, str]] = None
    turn_count: int = 0


class QueryRequest(BaseModel):
    project_id: Optional[str] = None  # Optional for conversational queries
    query: str
    max_results: int = 5
    temperature: float = 0
    stream: bool = False
    conversation_history: Optional[List[ConversationMessage]] = None  # Legacy: full history
    conversation_state: Optional[ConversationState] = None  # New: running summary
    use_llm_classification: bool = False  # Use keyword-based intent classification


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
    suggested_questions: Optional[List[str]] = []
    conversation_state: Optional[ConversationState] = None  # Updated running summary


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


def _fetch_repo_data(owner: str, repo: str, project_id: str) -> dict:
    """
    Fetch repository data from API (NO CACHING - always fresh)

    Strategy:
    1. Fetch from API directly (no cache checks)
    2. Load data into csv_engine
    3. Return results

    Args:
        owner: GitHub owner/organization name
        repo: Repository name
        project_id: Project identifier

    Returns:
        dict with loading results
    """
    result = {
        "data_source": "api",
        "commits_loaded": False,
        "issues_loaded": False,
        "commits_count": 0,
        "issues_count": 0,
        "message": "",
    }

    # Fetch fresh data from API (no caching)
    github_url = f"https://github.com/{owner}/{repo}"
    logger.info(f"🌐 Fetching fresh data from API for {github_url} (no cache)...")

    # Mark fetch as started
    csv_engine.mark_fetch_started(project_id, "commits")
    csv_engine.mark_fetch_started(project_id, "issues")

    success, api_data = repo_scraper.scrape_repository(github_url)

    if success:
        # Load into CSV engine
        load_result = csv_engine.load_from_api_data(project_id, api_data)

        result["data_source"] = "api"
        result["commits_loaded"] = load_result.get("commits_loaded", False)
        result["issues_loaded"] = load_result.get("issues_loaded", False)
        result["commits_count"] = load_result.get("commits_count", 0)
        result["issues_count"] = load_result.get("issues_count", 0)
        result["message"] = f"✅ Fetched from API | {result['commits_count']} commits, {result['issues_count']} issues"
        logger.info(result["message"])

        # Mark fetch as complete
        if result["commits_loaded"]:
            csv_engine.mark_fetch_complete(project_id, "commits")
        if result["issues_loaded"]:
            csv_engine.mark_fetch_complete(project_id, "issues")

        return result
    else:
        # API failed
        error_msg = api_data.get("error", "Unknown error")
        logger.error(f"❌ API fetch failed: {error_msg}")

        # Mark fetch as failed
        csv_engine.mark_fetch_failed(project_id, "commits", error_msg)
        csv_engine.mark_fetch_failed(project_id, "issues", error_msg)

        result["data_source"] = "none"
        result["message"] = f"❌ API failed: {error_msg}. Please try again later or check the commits/issues scraper service."
        logger.error(result["message"])
        return result


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
    """Get list of indexed projects from ChromaDB (no cache, no JSON)"""
    # Get all projects directly from ChromaDB vector store
    try:
        all_projects = rag_engine.vector_store.list_all_projects()
        logger.info(f"Listed {len(all_projects)} projects from ChromaDB")
        return all_projects
    except Exception as e:
        logger.error(f"Error listing projects from ChromaDB: {e}")
        return []


@router.post("/projects/add")
async def add_repository(request: AddRepositoryRequest):
    """Add a new repository from GitHub URL"""
    logger.info(f"Add repository request: {request.github_url}")

    try:
        # Parse GitHub URL
        owner, repo = parse_github_url(request.github_url)
        project_id = f"{owner}-{repo}".lower()

        # Check if project already exists in ChromaDB (single source of truth)
        if rag_engine.vector_store.project_exists(project_id):
            logger.info(f"Project {project_id} already indexed in ChromaDB")
            # Get project info from ChromaDB
            existing_projects = rag_engine.vector_store.list_all_projects()
            existing = next((p for p in existing_projects if p["id"] == project_id), None)

            if existing:
                # Check if commits/issues data needs to be fetched
                needs_data_fetch = not csv_engine.has_project_data(project_id)

                if needs_data_fetch:
                    logger.info(f"Project {project_id} missing commits/issues data, fetching in background")

                    import asyncio
                    from concurrent.futures import ThreadPoolExecutor

                    # Start background task to fetch commits/issues
                    async def background_data_fetch():
                        try:
                            loop = asyncio.get_event_loop()
                            with ThreadPoolExecutor(max_workers=1) as executor:
                                data_result = await loop.run_in_executor(
                                    executor,
                                    _fetch_repo_data,
                                    owner,
                                    repo,
                                    project_id
                                )
                            logger.info(f"✅ Background data fetch complete for {project_id}: {data_result}")
                        except Exception as e:
                            logger.error(f"❌ Background data fetch failed for {project_id}: {e}")

                    asyncio.create_task(background_data_fetch())

                return {
                    "status": "already_exists",
                    "message": f"Project {owner}/{repo} is already indexed in the system",
                    "project": existing,
                    "data_loading": {
                        "status": "loading_in_background" if needs_data_fetch else "available",
                        "message": "Commits/issues data is being fetched" if needs_data_fetch else "All data available"
                    }
                }

        # Extract project documents (always fresh)
        logger.info(f"Extracting project documents for {owner}/{repo}")
        doc_data = doc_extractor.extract_project_documents(owner, repo)

        if "error" in doc_data:
            raise HTTPException(
                status_code=400, detail=f"Error extracting project docs: {doc_data['error']}"
            )

        # Create project object for response (metadata stored in ChromaDB)
        project = {
            "id": project_id,
            "name": repo,
            "owner": owner,
            "repo": repo,
            "description": f"Custom repository: {owner}/{repo}",
            "foundation": "Custom",
            "governance_url": f"https://github.com/{owner}/{repo}",
        }

        # Note: No need to store in dynamic_projects - ChromaDB is our single source of truth

        # Run governance indexing first, then start API data fetching in background
        logger.info(f"Starting governance indexing for {project_id}")

        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        # Run governance indexing (this is blocking and must complete)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            index_future = loop.run_in_executor(
                executor,
                rag_engine.index_project_documents,
                project_id,
                doc_data
            )
            # Wait for governance indexing to complete
            index_result = await index_future

        # Check if governance indexing failed
        if "error" in index_result:
            error_msg = index_result.get("error", "Unknown error during governance indexing")
            logger.error(f"❌ Governance indexing failed for {project_id}: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to index project documents: {error_msg}"
            )

        logger.info(f"✅ Governance indexing complete for {project_id}")

        # Check if commits/issues data already exists in data_cache
        # (edge case: project not in ChromaDB but data_cache has data from previous partial run)
        needs_data_fetch = not csv_engine.has_project_data(project_id)

        if needs_data_fetch:
            # Start API data fetching in background (fire-and-forget)
            # This allows users to start asking governance questions immediately
            # while commits/issues data loads in the background
            async def background_data_fetch():
                try:
                    logger.info(f"Starting background API data fetch for {project_id}")
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        data_result = await loop.run_in_executor(
                            executor,
                            _fetch_repo_data,
                            owner,
                            repo,
                            project_id
                        )
                    logger.info(f"✅ Background API data fetch complete for {project_id}: {data_result}")
                except Exception as e:
                    logger.error(f"❌ Background API data fetch failed for {project_id}: {e}")

            # Create background task (non-blocking)
            asyncio.create_task(background_data_fetch())

            # Prepare response indicating data is loading in background
            data_result = {
                "status": "loading_in_background",
                "message": "Commits and issues data is being loaded in the background. Governance questions can be asked immediately.",
                "commits_loaded": False,
                "issues_loaded": False,
                "data_source": "pending"
            }
        else:
            # Data already exists in cache
            logger.info(f"✅ Commits/issues data already in cache for {project_id}")
            available_data = csv_engine.get_available_data(project_id)
            data_result = {
                "status": "available",
                "message": "Commits and issues data already available in cache.",
                "commits_loaded": available_data.get("commits", False),
                "issues_loaded": available_data.get("issues", False),
                "data_source": "cache"
            }

        logger.info(f"✅ Returning success for {project_id} (API data loading in background)")

        return {
            "status": "success",
            "message": f"Successfully added {owner}/{repo}",
            "project": project,
            "extraction": {
                "files_found": len(doc_data.get("files", {})),
                "extraction_time": doc_data.get("metadata", {}).get("extraction_time_seconds", 0),
            },
            "indexing": index_result,
            "data_loading": data_result,
            "summary": doc_extractor.get_extraction_summary(doc_data),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding repository: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/refresh")
async def refresh_project_data(project_id: str):
    """
    Refresh commits and issues data for a project (NO CACHING - always fresh)

    This endpoint:
    1. Fetches fresh data from the scraping API
    2. Reloads data into the CSV engine

    Useful for getting the latest commits and issues after significant repository activity.
    """
    logger.info(f"Refresh data request for project: {project_id}")

    # Find project (check flagship projects first, then ChromaDB)
    # Get project from ChromaDB (single source of truth)
    all_projects = rag_engine.vector_store.list_all_projects()
    project = next((p for p in all_projects if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Get owner and repo info
        owner = project.get("owner")
        repo = project.get("repo")

        if not owner or not repo:
            raise HTTPException(
                status_code=400,
                detail="Project missing owner or repo information"
            )

        # Fetch fresh data from API (no cache)
        data_result = _fetch_repo_data(owner, repo, project_id)

        if data_result.get("data_source") == "none":
            raise HTTPException(
                status_code=500,
                detail=data_result.get("message", "Failed to fetch data from API")
            )

        return {
            "status": "success",
            "message": f"Successfully refreshed data for {owner}/{repo}",
            "project_id": project_id,
            "data_loading": data_result
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing project data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}")
async def get_project(project_id: str):
    """Get details for a specific project"""
    # Get project from ChromaDB (single source of truth)
    all_projects = rag_engine.vector_store.list_all_projects()
    project = next((p for p in all_projects if p["id"] == project_id), None)

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
async def crawl_governance(project_id: str, background_tasks: BackgroundTasks):
    """Crawl and index project documents for a project"""
    logger.info(f"Crawl request for project: {project_id}")

    # Find project (check flagship projects first, then ChromaDB)
    # Get project from ChromaDB (single source of truth)
    all_projects = rag_engine.vector_store.list_all_projects()
    project = next((p for p in all_projects if p["id"] == project_id), None)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Extract project documents
        logger.info(f"Extracting project documents for {project['owner']}/{project['repo']}")
        doc_data = doc_extractor.extract_project_documents(
            project["owner"], project["repo"]
        )

        if "error" in doc_data:
            raise HTTPException(
                status_code=500,
                detail=f"Error extracting project docs: {doc_data['error']}",
            )

        # Index in RAG system
        logger.info(f"Indexing documents for {project_id}")
        index_result = rag_engine.index_project_documents(project_id, doc_data)

        return {
            "project_id": project_id,
            "status": "success",
            "extraction": {
                "files_found": len(doc_data.get("files", {})),
                "extraction_time": doc_data.get("metadata", {}).get(
                    "extraction_time_seconds", 0
                ),
            },
            "indexing": index_result,
            "summary": doc_extractor.get_extraction_summary(doc_data),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in crawl_governance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query", response_model=QueryResponse)
async def query_project_docs(request: QueryRequest):
    """
    Multi-Modal Query Endpoint with Intent Routing

    Routes queries to appropriate pipeline:
    - GENERAL: Direct LLM (no RAG)
    - GOVERNANCE: Vector RAG (ChromaDB)
    - COMMITS: CSV Query Engine
    - ISSUES: CSV Query Engine
    """
    logger.info(f"Query request: '{request.query}' | Project: {request.project_id} | LLM mode: {request.use_llm_classification}")

    # Step 1: Classify intent
    has_project_context = request.project_id is not None
    if request.use_llm_classification:
        # Use global LLM-based router (default, 97.8% accuracy)
        intent, confidence = intent_router.classify_intent(request.query, has_project_context)
    else:
        # Create keyword-based router for comparison/testing only
        keyword_router = IntentRouter(llm_client=llm_client, use_llm_classification=False)
        intent, confidence = keyword_router.classify_intent(request.query, has_project_context)

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

        # Get project from ChromaDB (single source of truth)
        all_projects = rag_engine.vector_store.list_all_projects()
        project = next((p for p in all_projects if p["id"] == request.project_id), None)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        if intent == "PROJECT_DOC_BASED":
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
                    response="No relevant project documents found for this project. Please make sure the project has been crawled first.",
                    sources=[],
                    metadata={"intent": intent, "has_context": False},
                    suggested_questions=suggested_questions,
                )

            # Build conversation context (support both legacy and running summary)
            conversation_history = []

            # Always create ConversationManager for tracking
            conv_manager = ConversationManager(llm_client)

            if request.conversation_state and request.conversation_state.turn_count > 0:
                # Load existing conversation state
                conv_manager.from_dict({
                    "running_summary": request.conversation_state.running_summary,
                    "last_exchange": request.conversation_state.last_exchange,
                    "turn_count": request.conversation_state.turn_count
                })
                # Get conversation context from manager
                conv_context = conv_manager.get_context_for_prompt()
                if conv_context:
                    context = f"{conv_context}\n\n{context}"
            elif request.conversation_history:
                # Legacy approach: full history
                for msg in request.conversation_history:
                    conversation_history.append({"role": msg.role, "content": msg.content})

            llm_response = await llm_client.generate_response(
                query=request.query,
                context=context,
                project_name=project["name"],
                temperature=request.temperature,
                conversation_history=[],  # Not used anymore, context includes conversation summary
                query_type=query_type,
            )

            # Update conversation state
            conv_manager.update_after_response(
                request.query,
                llm_response.get("response", "")
            )
            updated_state = ConversationState(
                running_summary=conv_manager.running_summary,
                last_exchange=conv_manager.last_exchange,
                turn_count=conv_manager.turn_count
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
                conversation_state=updated_state,
            )

        elif intent in ["COMMITS", "ISSUES"]:
            # Use CSV Query Engine
            data_type = "commits" if intent == "COMMITS" else "issues"

            # Always create ConversationManager for tracking
            conv_manager = ConversationManager(llm_client)

            if request.conversation_state and request.conversation_state.turn_count > 0:
                # Load existing conversation state
                conv_manager.from_dict({
                    "running_summary": request.conversation_state.running_summary,
                    "last_exchange": request.conversation_state.last_exchange,
                    "turn_count": request.conversation_state.turn_count
                })

            # Check if CSV data is available
            available_data = csv_engine.get_available_data(request.project_id)
            if not available_data.get(data_type):
                # Check fetch status to provide helpful message
                fetch_status = csv_engine.get_fetch_status(request.project_id, data_type)
                elapsed_time = csv_engine.get_elapsed_time(request.project_id, data_type)

                # Generate smart error message based on fetch status
                if fetch_status and fetch_status["status"] == "fetching":
                    # Data is currently being fetched
                    response_msg = f"The {data_type} data is still being fetched from the repository (Elapsed: {elapsed_time}s). "
                    response_msg += "The commits/issues scraper API is processing the data. Please try your question again in a few seconds."
                    error_type = f"{data_type}_fetching"
                elif fetch_status and fetch_status["status"] == "failed":
                    # Fetch failed
                    response_msg = f"Failed to fetch {data_type} data: {fetch_status.get('error', 'Unknown error')}. "
                    response_msg += "Please try re-adding the repository or contact support."
                    error_type = f"{data_type}_fetch_failed"
                else:
                    # No fetch started or unknown status
                    response_msg = f"No {data_type} data available for this project. "
                    response_msg += "The repository may need to be re-indexed. Try adding the repository again."
                    error_type = f"no_{data_type}_data"

                suggested_questions = question_suggester.get_initial_suggestions()
                return QueryResponse(
                    project_id=request.project_id,
                    query=request.query,
                    response=response_msg,
                    sources=[],
                    metadata={
                        "intent": intent,
                        "data_source": "csv",
                        "error": error_type,
                        "fetch_status": fetch_status["status"] if fetch_status else "unknown",
                        "elapsed_seconds": elapsed_time
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

                    # Update conversation state for aggregation query
                    conv_manager.update_after_response(request.query, llm_response_text)
                    updated_state = ConversationState(
                        running_summary=conv_manager.running_summary,
                        last_exchange=conv_manager.last_exchange,
                        turn_count=conv_manager.turn_count
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
                        conversation_state=updated_state,
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

                    # Update conversation state for aggregation query
                    conv_manager.update_after_response(request.query, llm_response_text)
                    updated_state = ConversationState(
                        running_summary=conv_manager.running_summary,
                        last_exchange=conv_manager.last_exchange,
                        turn_count=conv_manager.turn_count
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
                        conversation_state=updated_state,
                    )

            # For non-aggregation queries, use LLM to generate response
            # Add conversation context
            llm_context = context
            conv_context = conv_manager.get_context_for_prompt()
            if conv_context:
                llm_context = f"{conv_context}\n\n{context}"

            llm_response = await llm_client.generate_response(
                query=request.query,
                context=llm_context,  # Context with conversation history
                project_name=project["name"],
                temperature=0.0,  # Zero temperature for maximum factual precision, prevent hallucinations
                query_type=data_type,  # "commits" or "issues" - triggers CSV-specific prompting
            )

            # Update conversation state
            conv_manager.update_after_response(
                request.query,
                llm_response.get("response", "")
            )
            updated_state = ConversationState(
                running_summary=conv_manager.running_summary,
                last_exchange=conv_manager.last_exchange,
                turn_count=conv_manager.turn_count
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
                conversation_state=updated_state,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in query endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_documents(request: SearchRequest):
    """Semantic search in project documents"""
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
                "indexed": collection_stats.get("projects_indexed", 0),
            },
        }

    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


