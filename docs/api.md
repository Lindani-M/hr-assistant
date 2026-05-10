# API Reference — MSc Research Assistant

The backend is a **FastAPI** app (`app.py`). Start it with:

```bash
uvicorn app:app --reload
# Swagger UI available at http://localhost:8000/docs
```

---

## Authentication

The API itself has **no auth layer** — it is designed to sit behind the React frontend (which uses Microsoft MSAL for Azure AD login). All keys and secrets are loaded from the `.env` file at startup; callers do not supply credentials.

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
