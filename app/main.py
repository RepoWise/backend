"""
Main FastAPI application for RepoWise
"""
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
import sys

from app.core.config import settings
from app.api import routes
from app.api import auth_routes
from app.models.user import init_db

# Configure logger
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level=settings.log_level,
)

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Intelligent repository analysis powered by RAG - Ask questions about any GitHub repository",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)

# Include API routes
app.include_router(routes.router, prefix=settings.api_prefix)
app.include_router(auth_routes.router)


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Initialize authentication database
    try:
        init_db()
        logger.success("Authentication database initialized")
    except Exception as e:
        logger.error(f"Failed to initialize auth database: {e}")

    logger.info(f"Ollama Host: {settings.ollama_host}")
    logger.info(f"Ollama Model: {settings.ollama_model}")
    logger.info(f"ChromaDB Path: {settings.chroma_persist_dir}")
    logger.success("Application started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    logger.info("Shutting down application")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "api": settings.api_prefix,
    }


def _build_cors_preflight_response(request: Request) -> Response:
    """Create a CORS preflight response with the configured headers."""
    response = Response(status_code=200)
    origin = request.headers.get("origin")

    if settings.cors_allow_credentials and "*" in settings.cors_origins:
        # Browsers reject wildcard origins when credentials are allowed. Fall back to the
        # request origin only if it is explicitly permitted.
        allowed_origin = origin if settings.is_origin_allowed(origin) else None
    elif settings.is_origin_allowed(origin):
        allowed_origin = origin.strip().rstrip("/") if origin else None
    elif "*" in settings.cors_origins:
        allowed_origin = "*"
    else:
        allowed_origin = None

    if allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = allowed_origin
        vary_header = response.headers.get("Vary")
        if not vary_header:
            response.headers["Vary"] = "Origin"
        elif "origin" not in {value.strip().lower() for value in vary_header.split(",")}:
            response.headers["Vary"] = f"{vary_header}, Origin"

    response.headers["Access-Control-Allow-Methods"] = ", ".join(
        settings.cors_allow_methods
    )

    request_headers = request.headers.get("access-control-request-headers")
    if request_headers:
        response.headers["Access-Control-Allow-Headers"] = request_headers
    else:
        response.headers["Access-Control-Allow-Headers"] = ", ".join(
            settings.cors_allow_headers
        )

    if settings.cors_allow_credentials and allowed_origin:
        response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.options("/")
async def options_root(request: Request) -> Response:
    """Handle root preflight CORS requests."""
    return _build_cors_preflight_response(request)


@app.options("/{rest_of_path:path}")
async def options_catch_all(rest_of_path: str, request: Request) -> Response:
    """Handle preflight CORS requests for any route."""
    return _build_cors_preflight_response(request)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
