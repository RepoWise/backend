# RepoWise Backend

AI-powered backend service for analyzing open-source repository documentation, contribution guidelines, governance policies, commits, and issues.

## Features

- **Intelligent Query Classification**: Automatically routes queries to appropriate data sources (documents, commits, or issues)
- **Multi-Modal RAG System**: Combines vector search with structured CSV data for comprehensive answers
- **GitHub Repository Crawling**: Automatically extracts governance documents, commits, and issues
- **Advanced Embedding**: Uses Matryoshka Representation Learning (MRL) for efficient two-stage search
- **RESTful API**: FastAPI-based backend with async support

## Tech Stack

- **Framework**: FastAPI
- **Vector Database**: ChromaDB
- **Embeddings**: HuggingFace sentence-transformers with MRL
- **LLM**: Local Ollama (llama3.2) or cloud providers
- **Data Processing**: pandas, BeautifulSoup4
- **API Client**: GitHub API via requests

## Prerequisites

- Python 3.8+
- Ollama (for local LLM) or API keys for cloud providers
- GitHub Personal Access Token (for API access)

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RepoWise/backend.git
   cd backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and configure:
   - `GITHUB_TOKEN`: Your GitHub personal access token
   - `OLLAMA_HOST`: Ollama server URL (default: http://localhost:11434)
   - `OLLAMA_MODEL`: Model name (default: llama3.2:1b)
   - Other configuration as needed

5. **Install and start Ollama** (if using local LLM)
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.com/install.sh | sh
   ollama pull llama3.2:1b
   ollama serve
   ```

## Usage

### Development Server

```bash
# Using the start script
./start_dev.sh

# Or directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Server

```bash
./start_production.sh
```

## API Endpoints

### Repository Management

- `POST /api/projects/add` - Add a GitHub repository
  ```json
  {
    "github_url": "https://github.com/owner/repo"
  }
  ```

- `GET /api/projects` - List all indexed projects
- `DELETE /api/projects/{project_id}` - Remove a project

### Query

- `POST /api/query` - Query project documentation
  ```json
  {
    "project_id": "owner-repo",
    "query": "Who maintains this project?"
  }
  ```

### Health Check

- `GET /health` - Check API status

## Project Structure

```
backend/
├── app/
│   ├── api/           # API routes and endpoints
│   ├── core/          # Core configuration and utilities
│   ├── crawler/       # GitHub repository crawlers
│   ├── data/          # Data storage and patterns
│   ├── models/        # LLM client and intent router
│   ├── rag/           # RAG engine and vector store
│   ├── main.py        # FastAPI application entry point
├── requirements.txt   # Python dependencies
├── .env.example       # Environment variables template
└── README.md          # This file
```

## Configuration

### Environment Variables

Key configuration options in `.env`:

- **GitHub**: `GITHUB_TOKEN` for API access
- **Ollama**: `OLLAMA_HOST`, `OLLAMA_MODEL`
- **ChromaDB**: `CHROMA_PERSIST_DIR`, `CHROMA_COLLECTION_NAME`
- **Embeddings**: `EMBEDDING_MODEL` (MRL-enabled model recommended)
- **MRL Settings**: Enable/disable and configure Matryoshka dimensions
- **CORS**: `CORS_ORIGINS` for frontend access

### Embedding Models

Recommended: `tomaarsen/mpnet-base-nli-matryoshka` (768-dim with MRL)
Alternative: `sentence-transformers/all-MiniLM-L6-v2` (384-dim, faster)

## Features Deep Dive

### Intent Classification

Queries are automatically classified into three categories:
- **Document queries**: General questions about governance, contribution guidelines
- **Commit queries**: Questions about code changes, contributors, development activity
- **Issue queries**: Questions about bugs, feature requests, project health

### Two-Stage Search (MRL)

1. **Shortlist**: Fast search with 128-dim embeddings (top 50 candidates)
2. **Rerank**: Precise reranking with 768-dim embeddings (top 5 results)

This provides 3-5x faster search with minimal accuracy loss.

## Development

### Adding New Data Sources

1. Create a crawler in `app/crawler/`
2. Add extraction logic for your data type
3. Update the intent router in `app/models/intent_router.py`
4. Add query engine in `app/rag/`

### Testing

```bash
# Run with your test framework
pytest tests/
```

## Deployment

### Docker (Coming Soon)

```bash
docker build -t repowise-backend .
docker run -p 8000:8000 --env-file .env repowise-backend
```

### Cloud Platforms

Compatible with:
- AWS Lambda/EC2
- Google Cloud Run
- Azure App Service
- Heroku
- Railway

Ensure environment variables are configured in your deployment platform.

## Troubleshooting

### Common Issues

1. **ChromaDB errors**: Ensure `CHROMA_PERSIST_DIR` exists and has write permissions
2. **Ollama connection**: Verify Ollama is running (`ollama serve`)
3. **GitHub rate limits**: Use a personal access token with appropriate scopes
4. **Memory issues**: Reduce `MRL_SHORTLIST_K` or use smaller embedding model

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see LICENSE file for details

## Support

For issues and questions:
- GitHub Issues: https://github.com/RepoWise/backend/issues
- Documentation: https://github.com/RepoWise/backend/wiki
