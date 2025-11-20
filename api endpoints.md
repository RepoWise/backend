# API Endpoints for View Tracking

This backend now exposes two endpoints for tracking and retrieving view counts. All paths are relative to the configured API prefix (default: `/api`).

## Record a View
- **Method:** `POST`
- **Path:** `/api/record_view`
- **Description:** Stores the current UTC timestamp to record a view.
- **Example (cURL):**
  ```bash
  curl -X POST https://your-domain.example/api/record_view
  ```
- **Sample Response:**
  ```json
  {
    "message": "View recorded",
    "timestamp": "2024-06-20T12:34:56Z"
  }
  ```

## Get View Count
- **Method:** `GET`
- **Path:** `/api/view_count`
- **Description:** Returns the total number of recorded views.
- **Example (cURL):**
  ```bash
  curl https://your-domain.example/api/view_count
  ```
- **Sample Response:**
  ```json
  {
    "count": 42
  }
  ```
