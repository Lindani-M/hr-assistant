# API Reference — TalentGPT

The backend is a **FastAPI** app (`app.py`). Start it with:

```bash
uvicorn app:app --reload
# Swagger UI only available when DEBUG=true
```

---

## Authentication

Every request to `/chat` and `/search` must include a valid **Azure AD Bearer token** in the `Authorization` header:

```
Authorization: Bearer <access_token>
```

The frontend acquires this token silently via MSAL (`acquireTokenSilent`) before each request and forwards it automatically. If the session has expired, MSAL will redirect to re-authenticate.

The backend validates the token by:
1. Fetching Azure AD's public signing keys from the JWKS endpoint
2. Verifying the JWT signature (RS256) and expiry
3. Checking the `tid` claim matches `AZURE_AD_TENANT_ID`
4. Optionally checking the `azp` / `appid` claim matches `AZURE_AD_CLIENT_ID`

Any request with a missing, expired, or invalid token receives **`401 Unauthorized`**.

> **Local development**: if `AZURE_AD_TENANT_ID` or `AZURE_AD_CLIENT_ID` is not set in `.env`, token validation is skipped with a warning log. This allows running the backend without auth during development.

---

## Rate limits

Rate limiting is applied per IP address.

| Endpoint | Limit |
|---|---|
| `POST /chat` | **20 requests / minute** |
| `POST /search` | **30 requests / minute** |
| `GET /health` | Unlimited |

Requests exceeding the limit receive **`429 Too Many Requests`**. The frontend shows a user-friendly message and does not expose the raw error.

---

## Input limits

| Field | Constraint |
|---|---|
| `question` / `query` | 1–2000 characters (enforced by both frontend and backend) |
| `top_k` | 1–10 |
| `max_tokens` | 100–4000 |

Requests that violate these constraints receive **`422 Unprocessable Entity`** with a human-readable description.

---

## CORS

Allowed origins are configured via the `ALLOWED_ORIGINS` environment variable (comma-separated). Only `GET` and `POST` methods and the `Content-Type` / `Authorization` headers are permitted. Default: `http://localhost:5173`.

---

## API docs (Swagger / Redoc)

The interactive docs at `/docs` and `/redoc` are **disabled by default** and only enabled when `DEBUG=true` is set. Never enable this in production.

---

## Endpoints

### `GET /health`

Liveness check. Returns `200 OK` when the service is running.

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### `POST /chat`

Ask a question. Returns a grounded answer from Claude plus the source chunks that were retrieved.

**Rate limit:** 20 requests / minute per IP

**Request body**

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `question` | `string` | required | 1–2000 chars | The question to ask |
| `top_k` | `integer` | `5` | 1–10 | Chunks to retrieve |
| `max_tokens` | `integer` | `1500` | 100–4000 | Max tokens in Claude's reply |

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"question": "Why should we use RMSE over MAE?"}'
```

**Response**

```json
{
  "question": "Why should we use RMSE over MAE?",
  "answer": "...",
  "response_type": "rag",
  "sources": [
    {
      "title": "error_metrics_literature.pdf",
      "url": "https://...",
      "chunk_index": 2,
      "source_type": "file",
      "relevance_score": 87.4
    }
  ]
}
```

`response_type` is one of:
- `rag` — answer generated from retrieved context
- `chitchat` — greeting/thanks intercepted locally, no Azure call made
- `off_topic` — Claude classified the question as outside the research scope

---

### `POST /search`

Raw vector search — returns matching chunks without calling Claude. Useful for debugging retrieval quality.

**Rate limit:** 30 requests / minute per IP

**Request body**

| Field | Type | Default | Constraints | Description |
|---|---|---|---|---|
| `query` | `string` | required | 1–2000 chars | Text to embed and search |
| `top_k` | `integer` | `5` | 1–10 | Results to return |

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"query": "Coresignal API candidate data", "top_k": 3}'
```

**Response**

```json
{
  "query": "Coresignal API candidate data",
  "results": [
    {
      "title": "manuscript.docx",
      "url": "https://...",
      "chunk_index": 5,
      "text": "...",
      "relevance_score": 92.1
    }
  ]
}
```

---

## Required `.env` variables

```dotenv
# Azure OpenAI (embeddings)
AZURE_OAI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
AZURE_OAI_KEY=<key>
EMBED_DEPLOYMENT=text-embedding-ada-002

# Azure AI Search
SEARCH_ENDPOINT=https://<resource>.search.windows.net
SEARCH_KEY=<admin-or-query-key>
SEARCH_INDEX=sharepoint-pages
SEARCH_API_VERSION=2024-05-01-preview

# Claude via Azure AI Foundry
CLAUDE_ENDPOINT=https://<project>.services.ai.azure.com/anthropic/
CLAUDE_API_KEY=<key>
CLAUDE_DEPLOYMENT_NAME=claude-sonnet-4-6

# Azure AD — token validation for /chat and /search
AZURE_AD_TENANT_ID=<tenant-id>
AZURE_AD_CLIENT_ID=<client-id>

# CORS — comma-separated list of allowed frontend origins
ALLOWED_ORIGINS=http://localhost:5173,https://<your-production-domain>

# Set to true to expose /docs and /redoc (never in production)
DEBUG=false
```

### `GET /health`

Liveness check. Returns `200 OK` when the service is running.

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

---

### `POST /chat`

Ask a question. Returns a grounded answer from Claude plus the source chunks that were retrieved.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `question` | `string` | required | The question to ask |
| `top_k` | `integer` | `5` | Chunks to retrieve (1–20) |
| `max_tokens` | `integer` | `1500` | Max tokens in Claude's reply (100–15000) |

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Why should we use RMSE over MAE?"}'
```

**Response**

```json
{
  "question": "Why should we use RMSE over MAE?",
  "answer": "...",
  "response_type": "rag",
  "sources": [
    {
      "title": "error_metrics_literature.pdf",
      "url": "https://...",
      "chunk_index": 2,
      "source_type": "file",
      "relevance_score": 87.4
    }
  ]
}
```

`response_type` is one of:
- `rag` — answer generated from retrieved context
- `chitchat` — greeting/thanks intercepted locally, no Azure call made
- `off_topic` — Claude classified the question as outside the research scope

---

### `POST /search`

Raw vector search — returns matching chunks without calling Claude. Useful for debugging retrieval quality.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `query` | `string` | required | Text to embed and search |
| `top_k` | `integer` | `5` | Results to return (1–20) |

```bash
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "Coresignal API candidate data", "top_k": 3}'
```

**Response**

```json
{
  "query": "Coresignal API candidate data",
  "results": [
    {
      "title": "manuscript.docx",
      "url": "https://...",
      "chunk_index": 5,
      "text": "...",
      "relevance_score": 92.1
    }
  ]
}
```

---

## Required `.env` variables

```dotenv
# Azure OpenAI (embeddings)
AZURE_OAI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
AZURE_OAI_KEY=<key>
EMBED_DEPLOYMENT=text-embedding-ada-002

# Azure AI Search
SEARCH_ENDPOINT=https://<resource>.search.windows.net
SEARCH_KEY=<admin-or-query-key>
SEARCH_INDEX=sharepoint-pages
SEARCH_API_VERSION=2024-05-01-preview

# Claude via Azure AI Foundry
CLAUDE_ENDPOINT=https://<project>.services.ai.azure.com/anthropic/
CLAUDE_API_KEY=<key>
CLAUDE_DEPLOYMENT_NAME=claude-sonnet-4-6
```
