"""
Core configuration module for RepWise
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    # GitHub Configuration
    github_token: str = Field(..., env="GITHUB_TOKEN")

    # Ollama Configuration
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    ollama_model: str = Field(default="mistral:latest", env="OLLAMA_MODEL")  # 7B model for better reasoning and improved performance

    # ChromaDB Configuration
    chroma_persist_dir: str = Field(default="../chromadb", env="CHROMA_PERSIST_DIR")
    chroma_collection_name: str = Field(
        default="governance_docs", env="CHROMA_COLLECTION_NAME"
    )

    # Embedding Model
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", env="EMBEDDING_MODEL"
    )

    # Application Configuration
    app_name: str = Field(default="RepoWise", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug: bool = Field(default=False, env="DEBUG")

    # API Configuration
    api_prefix: str = Field(default="/api", env="API_PREFIX")
    cors_origins: List[str] | str = Field(
        default_factory=lambda: [
            "https://repowise.netlify.app",
            "https://tianna-unretractive-ellen.ngrok-free.dev",
            "http://localhost:3000",
            "http://localhost:5173",
        ],
        env="CORS_ORIGINS",
    )
    cors_allow_credentials: bool = Field(
        default=True,
        env="CORS_ALLOW_CREDENTIALS",
    )
    cors_allow_methods: List[str] | str = Field(
        default_factory=lambda: [
            "OPTIONS",
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        ],
        env="CORS_ALLOW_METHODS",
    )
    cors_allow_headers: List[str] | str = Field(
        default_factory=lambda: [
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
        ],
        env="CORS_ALLOW_HEADERS",
    )

    # Cache Configuration
    cache_dir: str = Field(default="../data/cache", env="CACHE_DIR")
    cache_ttl_seconds: int = Field(default=86400, env="CACHE_TTL_SECONDS")

    # Rate Limiting
    github_rate_limit_threshold: int = Field(
        default=100, env="GITHUB_RATE_LIMIT_THRESHOLD"
    )
    rate_limit_backoff_seconds: int = Field(
        default=60, env="RATE_LIMIT_BACKOFF_SECONDS"
    )

    # Authentication Configuration
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production-MUST-BE-SECURE-AND-RANDOM-987654321",
        env="JWT_SECRET_KEY"
    )
    database_url: str = Field(
        default="sqlite:///./auth.db",
        env="DATABASE_URL"
    )

    # OAuth Configuration (Optional)
    google_client_id: str = Field(
        default="your-google-client-id-here",
        env="GOOGLE_CLIENT_ID"
    )
    google_client_secret: str = Field(
        default="your-google-client-secret-here",
        env="GOOGLE_CLIENT_SECRET"
    )
    google_redirect_uri: str = Field(
        default="http://localhost:3000/auth/callback/google",
        env="GOOGLE_REDIRECT_URI"
    )
    github_oauth_client_id: str = Field(
        default="your-github-client-id-here",
        env="GITHUB_OAUTH_CLIENT_ID"
    )
    github_oauth_client_secret: str = Field(
        default="your-github-client-secret-here",
        env="GITHUB_OAUTH_CLIENT_SECRET"
    )
    github_oauth_redirect_uri: str = Field(
        default="http://localhost:3000/auth/callback/github",
        env="GITHUB_OAUTH_REDIRECT_URI"
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create necessary directories
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)

    @model_validator(mode="before")
    @classmethod
    def normalize_list_fields(cls, values: dict) -> dict:
        """Normalize comma/space separated environment overrides for list settings."""

        def _normalize(value: object) -> List[str]:
            if value is None or value == "":
                return []

            # Accept JSON-style arrays without raising validation errors
            if isinstance(value, str):
                text = value.strip()
                if text and text[0] in "[\"" and text.endswith("]"):
                    try:
                        parsed = json.loads(text)
                    except json.JSONDecodeError:
                        parsed = text
                    else:
                        value = parsed
                else:
                    # Split on commas or whitespace sequences
                    tokens = re.split(r"[,\s]+", text)
                    cleaned = []
                    for token in tokens:
                        normalized = cls._clean_token(token)
                        if normalized:
                            cleaned.append(normalized)
                    return cleaned

            if isinstance(value, (list, tuple, set)):
                iterable: Iterable[object] = value
            else:
                iterable = [value]

            cleaned: List[str] = []
            for item in iterable:
                normalized = cls._clean_token(item)
                if normalized:
                    cleaned.append(normalized)

            return cleaned

        for field_name in ("cors_origins", "cors_allow_methods", "cors_allow_headers"):
            if field_name in values:
                values[field_name] = _normalize(values[field_name])

        return values

    @staticmethod
    def _clean_token(value: object) -> str:
        """Return a normalized string token for CORS configuration entries."""

        if value is None:
            return ""

        token = str(value).strip()
        if not token:
            return ""

        if token != "*":
            token = token.rstrip("/")

        return token

    def is_origin_allowed(self, origin: str | None) -> bool:
        """Determine whether the supplied origin is allowed by configuration."""

        if origin is None:
            return False

        origin = origin.strip().rstrip("/")
        return "*" in self.cors_origins or origin in self.cors_origins


# Global settings instance
settings = Settings()


# Flagship OSS Projects Configuration
# FLAGSHIP_PROJECTS removed - system now relies entirely on dynamic_projects
# Users add projects via /api/projects/add endpoint
# Projects are stored in data/dynamic_projects.json
FLAGSHIP_PROJECTS = []


# Project documentation file patterns for detection
PROJECT_DOC_FILES = {
    "governance": [
        "GOVERNANCE.md",
        "docs/GOVERNANCE.md",
        ".github/GOVERNANCE.md",
    ],
    "contributing": [
        "CONTRIBUTING.md",
        "CONTRIBUTING.rst",
        "docs/CONTRIBUTING.md",
        "docs/CONTRIBUTING.rst",
        ".github/CONTRIBUTING.md",
        ".github/CONTRIBUTING.rst",
    ],
    "code_of_conduct": [
        "CODE_OF_CONDUCT.md",
        ".github/CODE_OF_CONDUCT.md",
        "docs/CODE_OF_CONDUCT.md",
    ],
    "security": [
        "SECURITY.md",
        ".github/SECURITY.md",
        "docs/SECURITY.md",
    ],
    "maintainers": [
        "MAINTAINERS.md",
        "MAINTAINERS.rst",
        "COMMITTERS.rst",
        "Maintainers.md",
        "CODEOWNERS",
        ".github/CODEOWNERS",
        "docs/CODEOWNERS",
        "docs/MAINTAINERS.md",
        "docs/MAINTAINERS.rst",
        "docs/COMMITTERS.rst",
    ],
    "license": [
        "LICENSE.md",
        "LICENSE",
        "docs/LICENSE.md",
        "LICENCE.md",
        "LICENCE",
        "docs/LICENCE"
    ],
    "charter": [
        "CHARTER.md",
        "docs/CHARTER.md",
    ],
    "readme": [
        "README.md",
        "README.rst",
        "docs/README.md",
        "docs/README.rst",
    ],
}


# Multi-Repository Governance Configuration
# Maps projects that have governance docs in separate repositories
MULTI_REPO_GOVERNANCE = {
    "tensorflow-tensorflow": {
        "governance_repo": "tensorflow/community",
        "description": "TensorFlow governance is maintained in separate community repo",
        "primary_files": [
            "governance/CHARTER.md",
            "governance/GOVERNANCE.md",
            "CONTRIBUTING.md",
            "CODE_OF_CONDUCT.md",
        ],
    },
    "kubernetes-kubernetes": {
        "governance_repo": "kubernetes/community",
        "description": "Kubernetes governance is in separate community repo",
        "primary_files": [
            "governance.md",
            "committee-steering/governance/sig-governance.md",
            "contributors/guide/README.md",
            "code-of-conduct.md",
            "sig-list.md",
        ],
    },
}
