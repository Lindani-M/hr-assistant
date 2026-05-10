"""
TalentGPT API
-------------
Provides a RAG-powered chat endpoint backed by Azure AI Search (vector store)
and Claude (via Azure AI Foundry).

Endpoints
---------
GET  /health          — liveness check
POST /chat            — ask a question; returns answer + sources
POST /search          — raw vector search, no LLM answer

How to run: uvicorn app:app --reload
"""

import os
import re
import time
import uuid
import logging
import traceback
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from openai import AzureOpenAI
from anthropic import AnthropicFoundry
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from jwt import PyJWKClient
import jwt as _jwt

load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
AZURE_OAI_ENDPOINT     = os.getenv("AZURE_OAI_ENDPOINT")
AZURE_OAI_KEY          = os.getenv("AZURE_OAI_KEY")
EMBED_DEPLOYMENT       = os.getenv("EMBED_DEPLOYMENT")

SEARCH_ENDPOINT        = os.getenv("SEARCH_ENDPOINT")
SEARCH_KEY             = os.getenv("SEARCH_KEY")
SEARCH_INDEX           = os.getenv("SEARCH_INDEX")
SEARCH_API_VERSION     = os.getenv("SEARCH_API_VERSION")

CLAUDE_ENDPOINT        = os.getenv("CLAUDE_ENDPOINT")
CLAUDE_API_KEY         = os.getenv("CLAUDE_API_KEY")
CLAUDE_DEPLOYMENT_NAME = os.getenv("CLAUDE_DEPLOYMENT_NAME")

AZURE_AD_TENANT_ID = os.getenv("AZURE_AD_TENANT_ID", "")
AZURE_AD_CLIENT_ID = os.getenv("AZURE_AD_CLIENT_ID", "")
ALLOWED_ORIGINS    = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
_DEBUG             = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

# ── Clients ───────────────────────────────────────────────────────────────────
oai_client = AzureOpenAI(
    azure_endpoint=AZURE_OAI_ENDPOINT,
    api_key=AZURE_OAI_KEY,
    api_version="2024-02-01",
)

claude_client = AnthropicFoundry(
    api_key=CLAUDE_API_KEY,
    base_url=CLAUDE_ENDPOINT,
)

# ── Rate limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Azure AD token validation ─────────────────────────────────────────────────
_jwks_client: PyJWKClient | None = None

def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None and AZURE_AD_TENANT_ID:
        _jwks_client = PyJWKClient(
            f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/discovery/v2.0/keys",
            cache_keys=True,
            lifespan=3600,
        )
    return _jwks_client


def require_auth(request: Request) -> None:
    """FastAPI dependency: validate the Azure AD Bearer token."""
    if not AZURE_AD_TENANT_ID or not AZURE_AD_CLIENT_ID:
        logger.warning("Auth validation skipped — AZURE_AD_TENANT_ID / AZURE_AD_CLIENT_ID not configured")
        return
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorised.")
    token = auth_header[7:]
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = _jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except _jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Unauthorised.")
    except _jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Unauthorised.")
    except Exception as exc:
        logger.error("Token validation error: %s", exc)
        raise HTTPException(status_code=401, detail="Unauthorised.")
    # Verify the token belongs to our tenant
    if payload.get("tid") != AZURE_AD_TENANT_ID:
        raise HTTPException(status_code=401, detail="Unauthorised.")
    # If the token carries an app-ID claim, verify it was issued to our app
    token_client = payload.get("azp") or payload.get("appid")
    if token_client and token_client != AZURE_AD_CLIENT_ID:
        raise HTTPException(status_code=401, detail="Unauthorised.")


# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="TalentGPT API",
    description="RAG-powered research assistant backed by SharePoint → Azure AI Search → Claude.",
    version="1.0.0",
    docs_url="/docs" if _DEBUG else None,
    redoc_url="/redoc" if _DEBUG else None,
    openapi_url="/openapi.json" if _DEBUG else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# ── Request-ID middleware ──────────────────────────────────────────────────────────
@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    rid = str(uuid.uuid4())[:8]
    request.state.rid = rid
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = rid
    logger.info(
        "[%s] %s %s → %d (%.0fms)",
        rid, request.method, request.url.path, response.status_code, elapsed,
    )
    return response


# ── Global error handlers ──────────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    rid = getattr(request.state, "rid", "-")
    errors = exc.errors()
    logger.warning("[%s] 422 Validation error: %s", rid, errors)
    # Return a single human-readable detail instead of Pydantic's raw list
    messages = "; ".join(
        f"{' → '.join(str(l) for l in e['loc'] if l != 'body')}: {e['msg']}"
        for e in errors
    )
    return JSONResponse(status_code=422, content={"detail": messages})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "rid", "-")
    logger.error(
        "[%s] Unhandled exception on %s %s\n%s",
        rid, request.method, request.url.path, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected server error occurred. Please try again shortly."},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ══════════════════════════════════════════════════════════════════════════════
# CHITCHAT
# ══════════════════════════════════════════════════════════════════════════════

CHITCHAT_PATTERNS = [
    r"\b(hi|hello|hey|howdy|greetings)\b",
    r"\bhow are you\b",
    r"\bwhat('s| is) your name\b",
    r"\bwho are you\b",
    r"\bwhat can you (do|help|assist)\b",
    r"\bthank(s| you)\b",
    r"\bbye\b|\bgoodbye\b",
]

CHITCHAT_RESPONSE = (
    "👋 Hi there! I'm TalentGPT, your MSc Research Assistant.\n\n"
    "I can help you find information from the MSc Documents SharePoint site, including:\n\n"
    "- The manuscript: 'Consolidating Access to Candidate Data for Recruitment Headhunting: "
    "Leveraging Explainable Machine Learning'\n"
    "- Literature on job recommendation systems using APIs and web crawling\n"
    "- Literature on RMSE vs MAE error metrics\n"
    "- Supplementary manuscript slides (More_On_Manuscript.pptx)\n\n"
    "Just ask me anything related to the research and I'll search the knowledge base for you!"
)


def _is_chitchat(question: str) -> bool:
    q = question.lower().strip()
    return any(re.search(p, q) for p in CHITCHAT_PATTERNS)


def _is_on_topic(question: str) -> bool:
    """Ask Claude to classify whether the question is relevant to MSc research content."""
    check = claude_client.messages.create(
        model=CLAUDE_DEPLOYMENT_NAME,
        max_tokens=10,
        system=(
            "You are a topic classifier. "
            "You only answer with YES or NO. "
            "Decide if the question is relevant to any of these topics: "
            "recruitment headhunting, explainable machine learning, candidate ranking, "
            "TF-IDF, Ridge Regression, Gradient Boosting, Random Forest, Shapash, "
            "Coresignal API, job recommendation systems, web crawling, APIs, "
            "RMSE, MAE, error metrics, statistical evaluation, model performance, "
            "MSc research, academic manuscripts, or any related data science topics. "
            "Answer YES if relevant, NO if not."
        ),
        messages=[{"role": "user", "content": f"Is this question relevant? Question: {question}"}],
    )
    verdict = check.content[0].text.strip().upper()
    return verdict.startswith("YES")


def _embed(text: str) -> list[float]:
    return (
        oai_client.embeddings.create(model=EMBED_DEPLOYMENT, input=[text])
        .data[0]
        .embedding
    )


def _vector_search(embedding: list[float], top_k: int) -> list[dict]:
    resp = requests.post(
        f"{SEARCH_ENDPOINT}/indexes/{SEARCH_INDEX}/docs/search"
        f"?api-version={SEARCH_API_VERSION}",
        headers={"Content-Type": "application/json", "api-key": SEARCH_KEY},
        json={
            "count": True,
            "select": "title,url,text,chunk_index,source_type",
            "top": top_k,
            "vectorQueries": [
                {
                    "kind": "vector",
                    "vector": embedding,
                    "fields": "embedding",
                    "k": top_k,
                }
            ],
        },
    )
    resp.raise_for_status()
    return resp.json().get("value", [])


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST / RESPONSE MODELS
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="The question to ask TalentGPT (max 2000 characters).")
    top_k: Optional[int] = Field(5, ge=1, le=10, description="Number of document chunks to retrieve (1–10).")
    max_tokens: Optional[int] = Field(1500, ge=100, le=4000, description="Maximum tokens for the Claude response (100–4000).")


class Source(BaseModel):
    title: str
    url: str
    chunk_index: int
    source_type: str
    relevance_score: float


class ChatResponse(BaseModel):
    question: str
    answer: str
    response_type: str = Field(description="One of: 'chitchat', 'off_topic', 'rag'")
    sources: list[Source] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000, description="The text query to embed and search (max 2000 characters).")
    top_k: Optional[int] = Field(5, ge=1, le=10, description="Number of results to return (1–10).")


class SearchResult(BaseModel):
    title: str
    url: str
    chunk_index: int
    text: str
    relevance_score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Utility"])
def health():
    """Liveness check. Returns 200 when the service is running."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse, tags=["RAG"])
@limiter.limit("20/minute")
def chat(req: ChatRequest, request: Request, _: None = Depends(require_auth)):
    """
    Ask a question to TalentGPT.

    **Flow**
    1. If the message is chitchat (greeting, thanks, etc.) → returns a canned response immediately.
    2. Asks Claude to classify whether the question is on-topic for Bellows College HR content.
    3. Embeds the question with `text-embedding-ada-002`.
    4. Runs a vector search against Azure AI Search.
    5. Sends the retrieved chunks + question to Claude for a grounded answer.

    **Parameters**
    - `question` — the user's question (required)
    - `top_k` — how many document chunks to retrieve (default 5, max 20)
    - `max_tokens` — max tokens in Claude's answer (default 1500, max 15000)
    """

    logger.info("[%s] POST /chat — length=%d top_k=%d", request.state.rid, len(req.question), req.top_k)

    # Step 1: chitchat shortcut
    if _is_chitchat(req.question):
        logger.info("[%s] Classified as chitchat", request.state.rid)
        return ChatResponse(
            question=req.question,
            answer=CHITCHAT_RESPONSE,
            response_type="chitchat",
        )

    # Step 2: topic relevance
    logger.info("[%s] Checking topic relevance...", request.state.rid)
    t0 = time.perf_counter()
    try:
        on_topic = _is_on_topic(req.question)
    except Exception as e:
        logger.error("[%s] Topic check failed: %s", request.state.rid, e)
        raise HTTPException(status_code=502, detail="Topic classification service unavailable. Please try again.")
    logger.info("[%s] Topic check: %s (%.0fms)", request.state.rid, on_topic, (time.perf_counter() - t0) * 1000)

    if not on_topic:
        logger.info("[%s] Off-topic question", request.state.rid)
        return ChatResponse(
            question=req.question,
            answer=(
                "I'm sorry, I can only answer questions related to the MSc research documents — "
                "topics like recruitment headhunting, explainable ML, candidate ranking, "
                "TF-IDF, regression models, error metrics (RMSE/MAE), job recommendation "
                "systems, or the manuscript and its supporting literature.\n\n"
                "Is there something about the research I can help you with instead?"
            ),
            response_type="off_topic",
        )

    # Step 3: embed
    logger.info("[%s] Embedding question...", request.state.rid)
    t0 = time.perf_counter()
    try:
        q_embedding = _embed(req.question)
        logger.info("[%s] Embedding complete (%.0fms)", request.state.rid, (time.perf_counter() - t0) * 1000)
    except Exception as e:
        logger.error("[%s] Embedding failed: %s\n%s", request.state.rid, e, traceback.format_exc())
        raise HTTPException(status_code=502, detail="The embedding service is currently unavailable. Please try again shortly.")

    # Step 4: vector search
    logger.info("[%s] Running vector search (top_k=%d)...", request.state.rid, req.top_k)
    t0 = time.perf_counter()
    try:
        hits = _vector_search(q_embedding, req.top_k)
        logger.info("[%s] Vector search returned %d hits (%.0fms)", request.state.rid, len(hits), (time.perf_counter() - t0) * 1000)
    except Exception as e:
        logger.error("[%s] Vector search failed: %s\n%s", request.state.rid, e, traceback.format_exc())
        raise HTTPException(status_code=502, detail="The knowledge base search service is currently unavailable. Please try again shortly.")

    if not hits:
        logger.info("[%s] No hits returned for question", request.state.rid)
        return ChatResponse(
            question=req.question,
            answer="I couldn't find any relevant content in the knowledge base for that question.",
            response_type="rag",
        )

    # Step 5: build context
    context_blocks = [
        f"[{i}] {'SharePoint Page' if h.get('source_type') == 'page' else 'Document'}: {h['title']}\n"
        f"    URL: {h['url']}\n    Chunk: {h['chunk_index']}\n    Content: {h['text']}"
        for i, h in enumerate(hits, 1)
    ]
    context = "\n\n".join(context_blocks)

    # Step 6: ask Claude
    logger.info("[%s] Calling Claude (%s)...", request.state.rid, CLAUDE_DEPLOYMENT_NAME)
    t0 = time.perf_counter()
    try:
        response = claude_client.messages.create(
            model=CLAUDE_DEPLOYMENT_NAME,
            max_tokens=req.max_tokens,
            system=(
                "You are a knowledgeable research assistant helping with an MSc thesis on "
                "recruitment headhunting and explainable machine learning. "
                "The knowledge base contains:\n"
                "  1. An MSc manuscript on consolidating candidate data using the Coresignal API "
                "and explainable ML (TF-IDF + Ridge/Gradient Boosting/Random Forest + Shapash)\n"
                "  2. Literature on technical job recommendation systems using APIs and web crawling\n"
                "  3. Literature on RMSE vs MAE error metrics\n"
                "  4. Supplementary manuscript slides\n\n"
                "Answer questions ONLY using the provided context from these documents. "
                "If the answer is not in the context, say so clearly. "
                "Do NOT include a References or Sources section at the end of your answer. "
                "Use precise academic language appropriate for MSc-level research discussion."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Context from MSc research documents:\n\n{context}\n\nQuestion: {req.question}",
                }
            ],
        )
    except Exception as e:
        logger.error("[%s] Claude call failed: %s\n%s", request.state.rid, e, traceback.format_exc())
        raise HTTPException(status_code=502, detail="The AI answer service is currently unavailable. Please try again shortly.")

    answer = response.content[0].text
    sources = [
        Source(
            title=h["title"],
            url=h["url"],
            chunk_index=h["chunk_index"],
            source_type=h.get("source_type", "unknown"),
            relevance_score=round(min(h.get("@search.score", 0) * 100, 100), 2),
        )
        for h in hits
    ]

    logger.info(
        "[%s] Answer generated — %d sources, %.0fms",
        request.state.rid, len(sources), (time.perf_counter() - t0) * 1000,
    )
    return ChatResponse(
        question=req.question,
        answer=answer,
        response_type="rag",
        sources=sources,
    )


@app.post("/search", response_model=SearchResponse, tags=["RAG"])
@limiter.limit("30/minute")
def search(req: SearchRequest, request: Request, _: None = Depends(require_auth)):
    """
    Run a raw vector search against Azure AI Search without generating an LLM answer.
    Useful for inspecting what chunks would be retrieved for a given query.

    **Parameters**
    - `query` — the text to embed and search (required)
    - `top_k` — number of results to return (default 5, max 20)
    """

    logger.info("[%s] POST /search — length=%d top_k=%d", request.state.rid, len(req.query), req.top_k)

    t0 = time.perf_counter()
    try:
        embedding = _embed(req.query)
        logger.info("[%s] Embedding complete (%.0fms)", request.state.rid, (time.perf_counter() - t0) * 1000)
    except Exception as e:
        logger.error("[%s] Embedding failed: %s\n%s", request.state.rid, e, traceback.format_exc())
        raise HTTPException(status_code=502, detail="The embedding service is currently unavailable. Please try again shortly.")

    t0 = time.perf_counter()
    try:
        hits = _vector_search(embedding, req.top_k)
        logger.info("[%s] Search returned %d results (%.0fms)", request.state.rid, len(hits), (time.perf_counter() - t0) * 1000)
    except Exception as e:
        logger.error("[%s] Vector search failed: %s\n%s", request.state.rid, e, traceback.format_exc())
        raise HTTPException(status_code=502, detail="The knowledge base search service is currently unavailable. Please try again shortly.")

    results = [
        SearchResult(
            title=h["title"],
            url=h["url"],
            chunk_index=h["chunk_index"],
            text=h["text"],
            relevance_score=round(min(h.get("@search.score", 0) * 100, 100), 2),
        )
        for h in hits
    ]

    logger.info("[%s] Search complete — %d results", request.state.rid, len(results))
    return SearchResponse(query=req.query, results=results)
