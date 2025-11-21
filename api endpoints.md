# API Endpoints

All paths are relative to the API prefix configured in `settings.api_prefix` (default: `/api`). Authentication routes include an additional `/auth` prefix.

## Service Information

- **Root**
  - **Method:** `GET`
  - **Path:** `/`
  - **Description:** Basic service metadata.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/
    ```

- **Health Check**
  - **Method:** `GET`
  - **Path:** `/api/health`
  - **Description:** Verify the main service is running.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/health
    ```

- **System Status**
  - **Method:** `GET`
  - **Path:** `/api/system-status`
  - **Description:** Returns LLM availability, vector store stats, and configuration details.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/system-status
    ```

- **Statistics**
  - **Method:** `GET`
  - **Path:** `/api/stats`
  - **Description:** Overall RAG collection statistics, including indexed project counts.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/stats
    ```

## View Tracking

- **Record a View**
  - **Method:** `POST`
  - **Path:** `/api/record_view`
  - **Description:** Stores the current UTC timestamp to record a view.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/record_view
    ```

- **Get View Count**
  - **Method:** `GET`
  - **Path:** `/api/view_count`
  - **Description:** Returns the total number of recorded views.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/view_count
    ```

## Processed Repository Tracking

- **Record a Processed Repository**
  - **Method:** `POST`
  - **Path:** `/api/track-processed-repo`
  - **Description:** Records a processed-repository event with a timestamp and increments the cumulative count.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/track-processed-repo
    ```

- **Get Processed Repository Count**
  - **Method:** `GET`
  - **Path:** `/api/processed-repo-count`
  - **Description:** Returns the total number of repositories successfully processed.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/processed-repo-count
    ```

## Project Management

- **List Projects**
  - **Method:** `GET`
  - **Path:** `/api/projects`
  - **Description:** List all indexed projects in ChromaDB.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/projects
    ```

- **Add Repository**
  - **Method:** `POST`
  - **Path:** `/api/projects/add`
  - **Description:** Add a GitHub repository for document extraction and indexing.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/projects/add \
      -H "Content-Type: application/json" \
      -d '{"github_url": "https://github.com/owner/repo"}'
    ```

- **Refresh Project Data**
  - **Method:** `POST`
  - **Path:** `/api/projects/{project_id}/refresh`
  - **Description:** Refresh commits and issues data from the scraping API.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/projects/example-project/refresh
    ```

- **Get Project Details**
  - **Method:** `GET`
  - **Path:** `/api/projects/{project_id}`
  - **Description:** Retrieve project metadata and indexing status.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/projects/example-project
    ```

- **Delete Project Index**
  - **Method:** `DELETE`
  - **Path:** `/api/projects/{project_id}/index`
  - **Description:** Remove indexed documents for a project.
  - **Example (cURL):**
    ```bash
    curl -X DELETE https://your-domain.example/api/projects/example-project/index
    ```

## Document Crawling and Search

- **Crawl Governance Documents**
  - **Method:** `POST`
  - **Path:** `/api/crawl/{project_id}`
  - **Description:** Extract and index governance documents for a project.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/crawl/example-project
    ```

- **Semantic Search**
  - **Method:** `POST`
  - **Path:** `/api/search`
  - **Description:** Semantic search across indexed project documents.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/search \
      -H "Content-Type: application/json" \
      -d '{"project_id": "example-project", "query": "governance policy", "n_results": 5}'
    ```

- **Multi-Modal Query**
  - **Method:** `POST`
  - **Path:** `/api/query`
  - **Description:** Routes queries to governance, commits, issues, or general responses based on intent.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/query \
      -H "Content-Type: application/json" \
      -d '{"project_id": "example-project", "query": "What are the contribution guidelines?", "max_results": 5}'
    ```

## Administration

- **Admin Reset**
  - **Method:** `DELETE`
  - **Path:** `/api/admin/reset`
  - **Description:** Clears ChromaDB collections and in-memory caches. Use cautiously.
  - **Example (cURL):**
    ```bash
    curl -X DELETE https://your-domain.example/api/admin/reset
    ```

## Authentication (Prefixed with `/api/auth`)

- **Signup**
  - **Method:** `POST`
  - **Path:** `/api/auth/signup`
  - **Description:** Create a new user account.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/auth/signup \
      -H "Content-Type: application/json" \
      -d '{"first_name": "Ada", "last_name": "Lovelace", "email": "ada@example.com", "password": "Secret123!"}'
    ```

- **Login**
  - **Method:** `POST`
  - **Path:** `/api/auth/login`
  - **Description:** Log in with email and password to receive a JWT.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email": "ada@example.com", "password": "Secret123!"}'
    ```

- **OAuth Authorization URL**
  - **Method:** `GET`
  - **Path:** `/api/auth/oauth/{provider}/authorize`
  - **Description:** Retrieve provider-specific authorization URL (supports `google` or `github`).
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/auth/oauth/google/authorize
    ```

- **OAuth Callback**
  - **Method:** `POST`
  - **Path:** `/api/auth/oauth/{provider}/callback`
  - **Description:** Exchange OAuth code for a token and authenticate the user.
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/auth/oauth/google/callback \
      -H "Content-Type: application/json" \
      -d '{"code": "AUTH_CODE", "redirect_uri": "https://your-domain.example/oauth/callback"}'
    ```

- **Current User Profile**
  - **Method:** `GET`
  - **Path:** `/api/auth/me`
  - **Description:** Fetch the authenticated user's profile (requires `Authorization: Bearer <token>` header).
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/auth/me \
      -H "Authorization: Bearer <JWT>"
    ```

- **List All Users**
  - **Method:** `GET`
  - **Path:** `/api/auth/users`
  - **Description:** Retrieve all registered users (requires `Authorization: Bearer <token>` header).
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/auth/users \
      -H "Authorization: Bearer <JWT>"
    ```

- **Logout**
  - **Method:** `POST`
  - **Path:** `/api/auth/logout`
  - **Description:** Log out the current user (for logging; JWT remains stateless).
  - **Example (cURL):**
    ```bash
    curl -X POST https://your-domain.example/api/auth/logout \
      -H "Authorization: Bearer <JWT>"
    ```

- **Auth Health Check**
  - **Method:** `GET`
  - **Path:** `/api/auth/health`
  - **Description:** Health check for the authentication subsystem.
  - **Example (cURL):**
    ```bash
    curl https://your-domain.example/api/auth/health
    ```

