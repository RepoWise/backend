"""
Core configuration module for OSSPREY-GOV-POC
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
import os
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # GitHub Configuration
    github_token: str = Field(..., env="GITHUB_TOKEN")

    # Ollama Configuration
    ollama_host: str = Field(default="http://localhost:11434", env="OLLAMA_HOST")
    ollama_model: str = Field(default="qwen2.5:3b", env="OLLAMA_MODEL")  # 3B model for better reasoning and reduced hallucinations

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
    app_name: str = Field(default="OSSPREY-GOV-POC", env="APP_NAME")
    app_version: str = Field(default="1.0.0", env="APP_VERSION")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    debug: bool = Field(default=False, env="DEBUG")

    # API Configuration
    api_prefix: str = Field(default="/api", env="API_PREFIX")
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        env="CORS_ORIGINS",
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

    class Config:
        env_file = ".env"
        case_sensitive = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Create necessary directories
        Path(self.chroma_persist_dir).mkdir(parents=True, exist_ok=True)
        Path(self.cache_dir).mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


# Flagship OSS Projects Configuration
FLAGSHIP_PROJECTS = [
    {
        "id": "resilientdb-incubator-resilientdb",  # Match actual indexed project ID
        "name": "Apache ResilientDB",
        "owner": "resilientdb",  # Actual owner on GitHub
        "repo": "incubator-resilientdb",
        "description": "High-performance resilient and scalable blockchain fabric",
        "foundation": "Apache Incubator",
        "governance_url": "https://github.com/resilientdb/incubator-resilientdb",
    },
    {
        "id": "kubernetes",
        "name": "Kubernetes",
        "owner": "kubernetes",
        "repo": "kubernetes",
        "description": "Production-Grade Container Orchestration",
        "foundation": "CNCF",
        "governance_url": "https://github.com/kubernetes/community/tree/master/governance",
    },
    {
        "id": "airflow",
        "name": "Apache Airflow",
        "owner": "apache",
        "repo": "airflow",
        "description": "Platform to programmatically author, schedule and monitor workflows",
        "foundation": "Apache",
        "governance_url": "https://github.com/apache/airflow/blob/main/GOVERNANCE.md",
    },
    {
        "id": "terraform",
        "name": "Terraform",
        "owner": "hashicorp",
        "repo": "terraform",
        "description": "Infrastructure as Code tool",
        "foundation": "HashiCorp",
        "governance_url": "https://github.com/hashicorp/terraform/blob/main/GOVERNANCE.md",
    },
    {
        "id": "vscode",
        "name": "Visual Studio Code",
        "owner": "microsoft",
        "repo": "vscode",
        "description": "Code editor that runs anywhere",
        "foundation": "Microsoft",
        "governance_url": "https://github.com/microsoft/vscode/wiki/Governance",
    },
    {
        "id": "postgresql",
        "name": "PostgreSQL",
        "owner": "postgres",
        "repo": "postgres",
        "description": "The world's most advanced open source database",
        "foundation": "PostgreSQL Global Development Group",
        "governance_url": "https://www.postgresql.org/developer/",
    },
]


# Governance file patterns for detection
GOVERNANCE_FILES = {
    "governance": [
        "GOVERNANCE.md",
        "GOVERNANCE",
        "governance.md",
        "docs/GOVERNANCE.md",
        ".github/GOVERNANCE.md",
    ],
    "contributing": [
        "CONTRIBUTING.md",
        "CONTRIBUTING",
        "contributing.md",
        "docs/CONTRIBUTING.md",
        ".github/CONTRIBUTING.md",
    ],
    "code_of_conduct": [
        "CODE_OF_CONDUCT.md",
        "CODE-OF-CONDUCT.md",
        "CODE_OF_CONDUCT",
        "code_of_conduct.md",
        ".github/CODE_OF_CONDUCT.md",
    ],
    "security": [
        "SECURITY.md",
        "SECURITY",
        "security.md",
        "docs/SECURITY.md",
        ".github/SECURITY.md",
    ],
    "maintainers": [
        "MAINTAINERS.md",
        "MAINTAINERS",
        "maintainers.md",
        "docs/MAINTAINERS.md",
        "OWNERS",
        "CODEOWNERS",
        ".github/CODEOWNERS",
    ],
    "license": [
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
        "COPYING",
        "COPYING.md",
    ],
    "charter": [
        "CHARTER.md",
        "CHARTER",
        "charter.md",
        "docs/CHARTER.md",
    ],
    "readme": [
        "README.md",
        "README",
        "readme.md",
    ],
}
