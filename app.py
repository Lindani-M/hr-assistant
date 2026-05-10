"""
HR Assistant API
----------------
Provides a RAG-powered chat endpoint backed by Azure AI Search (vector store)
and Claude (via Azure AI Foundry).

Endpoints
---------
GET  /health          — liveness check
POST /chat            — ask a question; returns answer + sources
POST /search          — raw vector search, no LLM answer
"""

import os
import re
import logging
from typing import Optional

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import AzureOpenAI
from anthropic import AnthropicFoundry
from pydantic import BaseModel, Field
from dotenv import load_dotenv

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

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="HR Assistant API",
    description="RAG-powered HR assistant backed by SharePoint → Azure AI Search → Claude.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    "Hi there! I'm the Bellows College HR Assistant.\n\n"
    "I can help you find information from the Bellows College GroupHR SharePoint intranet, such as:\n\n"
    "- Scholarships and awards (e.g. The President's Scholarship)\n"
    "- Scholar profiles and achievements\n"
    "- College values, policies, and programmes\n"
    "- HR-related content published on the intranet\n\n"
    "Just ask me anything related to Bellows College and I'll search the knowledge base for you!"
)


def _is_chitchat(question: str) -> bool:
    q = question.lower().strip()
    return any(re.search(p, q) for p in CHITCHAT_PATTERNS)


def _is_on_topic(question: str) -> bool:
    """Ask Claude to classify whether the question is relevant to Bellows College HR content."""
    check = claude_client.messages.create(
        model=CLAUDE_DEPLOYMENT_NAME,
        max_tokens=10,
        system=(
            "You are a topic classifier for a college HR knowledge base. "
            "You only answer with YES or NO. "
            "Answer YES if the question could plausibly be answered by a college intranet — "
            "this includes questions about: people (students, staff, scholars, employees), "
            "roles, classifications, achievements, awards, scholarships, policies, programmes, "
            "departments, college values, or any named individual who may be a student or staff member. "
            "Only answer NO if the question is clearly about something entirely unrelated to a college "
            "or workplace, such as cooking, sports scores, weather, or general trivia. "
            "When in doubt, answer YES."
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
            "select": "title,url,text,chunk_index",
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
    question: str = Field(..., min_length=1, description="The question to ask the HR assistant.")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of document chunks to retrieve from the vector store (1–20).")
    max_tokens: Optional[int] = Field(1500, ge=100, le=15000, description="Maximum tokens for the Claude response.")


class Source(BaseModel):
    title: str
    url: str
    chunk_index: int
    relevance_score: float


class ChatResponse(BaseModel):
    question: str
    answer: str
    response_type: str = Field(description="One of: 'chitchat', 'off_topic', 'rag'")
    sources: list[Source] = []


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="The text query to embed and search against the vector store.")
    top_k: Optional[int] = Field(5, ge=1, le=20, description="Number of results to return (1–20).")


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
def chat(req: ChatRequest):
    """
    Ask a question to the HR assistant.

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

    logger.info("POST /chat — question=%r top_k=%d", req.question, req.top_k)

    # Step 1: chitchat shortcut
    if _is_chitchat(req.question):
        logger.info("Classified as chitchat — returning canned response")
        return ChatResponse(
            question=req.question,
            answer=CHITCHAT_RESPONSE,
            response_type="chitchat",
        )

    # Step 2: topic relevance
    logger.info("Checking topic relevance...")
    if not _is_on_topic(req.question):
        logger.info("Question classified as off-topic")
        return ChatResponse(
            question=req.question,
            answer=(
                "I'm sorry, I can only answer questions related to Bellows College "
                "and its HR intranet content — things like scholarships, college "
                "policies, scholar profiles, and employee information.\n\n"
                "Is there something about Bellows College I can help you with instead?"
            ),
            response_type="off_topic",
        )

    # Step 3: embed
    logger.info("Embedding question...")
    try:
        q_embedding = _embed(req.question)
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Embedding service error: {e}")

    # Step 4: vector search
    logger.info("Running vector search (top_k=%d)...", req.top_k)
    try:
        hits = _vector_search(q_embedding, req.top_k)
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Search service error: {e}")

    if not hits:
        return ChatResponse(
            question=req.question,
            answer="I couldn't find any relevant content in the knowledge base for that question.",
            response_type="rag",
        )

    # Step 5: build context
    context_blocks = [
        f"[{i}] Title: {h['title']}\n    URL: {h['url']}\n    Chunk: {h['chunk_index']}\n    Content: {h['text']}"
        for i, h in enumerate(hits, 1)
    ]
    context = "\n\n".join(context_blocks)

    # Step 6: ask Claude
    logger.info("Generating answer with Claude (%s)...", CLAUDE_DEPLOYMENT_NAME)
    try:
        response = claude_client.messages.create(
            model=CLAUDE_DEPLOYMENT_NAME,
            max_tokens=req.max_tokens,
            system=(
                "You are a helpful HR assistant for Bellows College. "
                "You ONLY answer questions using the provided SharePoint intranet content. "
                "Do NOT use any external knowledge or training data to answer. "
                "If the answer is not clearly found in the context, say so. "
                "Do NOT include a References or Sources section at the end. "
                "Format your responses using Markdown: use - for bullet lists, ** for bold, and proper paragraph spacing. "
                "Tone: friendly and informative, like a knowledgeable colleague."
            ),
            messages=[
                {
                    "role": "user",
                    "content": f"Context from SharePoint:\n\n{context}\n\nQuestion: {req.question}",
                }
            ],
        )
    except Exception as e:
        logger.error("Claude call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"LLM service error: {e}")

    answer = response.content[0].text
    sources = [
        Source(
            title=h["title"],
            url=h["url"],
            chunk_index=h["chunk_index"],
            relevance_score=round(min(h.get("@search.score", 0) * 100, 100), 2),
        )
        for h in hits
    ]

    logger.info("Answer generated — %d sources returned", len(sources))
    return ChatResponse(
        question=req.question,
        answer=answer,
        response_type="rag",
        sources=sources,
    )


@app.post("/search", response_model=SearchResponse, tags=["RAG"])
def search(req: SearchRequest):
    """
    Run a raw vector search against Azure AI Search without generating an LLM answer.
    Useful for inspecting what chunks would be retrieved for a given query.

    **Parameters**
    - `query` — the text to embed and search (required)
    - `top_k` — number of results to return (default 5, max 20)
    """

    logger.info("POST /search — query=%r top_k=%d", req.query, req.top_k)

    try:
        embedding = _embed(req.query)
    except Exception as e:
        logger.error("Embedding failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Embedding service error: {e}")

    try:
        hits = _vector_search(embedding, req.top_k)
    except Exception as e:
        logger.error("Vector search failed: %s", e)
        raise HTTPException(status_code=502, detail=f"Search service error: {e}")

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

    logger.info("Search complete — %d results", len(results))
    return SearchResponse(query=req.query, results=results)
