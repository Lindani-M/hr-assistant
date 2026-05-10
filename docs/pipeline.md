# Data Pipeline — SharePoint → Azure AI Search → RAG

## Overview

```
SharePoint (.aspx pages + drive files)
        │
        ▼
   ingest.py
        │  1. Authenticate (MSAL)
        │  2. Scrape pages & download files
        │  3. Chunk text
        │  4. Embed (text-embedding-ada-002)
        │  5. Create index + upload
        ▼
  Azure AI Search  ◄──────────────────────────────┐
        │                                          │
        ▼                                          │
   app.py /chat                             vector search
        │  1. Embed question                       │
        │  2. Vector search ────────────────────────┘
        │  3. Send context to Claude
        ▼
     Answer
```

---

## Step 1 — SharePoint Authentication

`ingest.py` uses **MSAL client-credentials flow** (app-only, no user login).

**What you need:**

1. In **Azure Portal → Azure Active Directory → App registrations**, register a new app.
2. Under **Certificates & secrets**, create a client secret → copy the value as `SP_CLIENT_SECRET`.
3. Copy the **Application (client) ID** → `SP_CLIENT_ID`.
4. Copy the **Directory (tenant) ID** → `SP_TENANT_ID`.
5. Under **API permissions**, add `Microsoft Graph → Application permissions`:
   - `Sites.Read.All` (read pages)
   - `Files.Read.All` (read drive files)
   - Click **Grant admin consent**.

```dotenv
SP_TENANT_ID=<tenant-id>
SP_CLIENT_ID=<app-client-id>
SP_CLIENT_SECRET=<client-secret>
SP_HOSTNAME=yourorg.sharepoint.com
SP_SITE_PATH=/sites/YourSiteName
```

---

## Step 2 — Scraping

`ingest.py` runs two scrapers in sequence:

| Function | What it fetches |
|---|---|
| `scrape_all_pages` | Every published `.aspx` page on the site via `GET /sites/{id}/pages`, then fetches canvas layout and web parts for the full text body |
| `scrape_drive_documents` | Walks the entire drive root recursively, downloads every `.pdf`, `.docx`, and `.pptx`, and extracts plain text |

Text extractors: `pdfplumber` (PDF), `python-docx` (Word), `python-pptx` (PowerPoint).

Both return the same document shape — `{page_id, title, url, full_text, source_type}` — so the rest of the pipeline is identical for pages and files.

---

## Step 3 — Chunking

`chunk_documents` splits each document's text into overlapping word-level windows:

- **Chunk size**: 400 words
- **Overlap**: 80 words (ensures sentences at chunk boundaries aren't lost)

Each chunk gets a stable ID: `{page_id}_chunk{index}`.

---

## Step 4 — Embedding

`embed_chunks` calls **Azure OpenAI `text-embedding-ada-002`** in batches of 16. Each chunk's text is replaced with a 1536-dimension float vector.

**Keys needed:**

- In **Azure Portal → Azure OpenAI resource → Keys and Endpoint** → copy the endpoint and key.
- Deploy `text-embedding-ada-002` in **Azure OpenAI Studio → Deployments**.

```dotenv
AZURE_OAI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
AZURE_OAI_KEY=<key>
EMBED_DEPLOYMENT=text-embedding-ada-002
```

---

## Step 5 — Index Creation & Upload

`create_index` calls the Azure AI Search REST API to create (or update) an HNSW vector index with these fields:

`id`, `page_id`, `title`, `url`, `source_type`, `chunk_index`, `text`, `embedding`

`upload_chunks` then bulk-uploads all chunks using `mergeOrUpload` in batches of 100.

**Keys needed:**

- In **Azure Portal → Azure AI Search resource → Keys** → copy the **Admin key** (needed for index creation/upload) or **Query key** (read-only, sufficient for `app.py`).
- The endpoint is on the **Overview** page.

```dotenv
SEARCH_ENDPOINT=https://<resource>.search.windows.net
SEARCH_KEY=<admin-key>
SEARCH_INDEX=sharepoint-pages
SEARCH_API_VERSION=2024-05-01-preview
```

---

## Step 6 — RAG Query (app.py)

When `/chat` receives a question:

1. **Chitchat check** — regex match; if it's a greeting/thanks, returns a canned reply immediately (no Azure calls).
2. **Topic filter** — sends the question to Claude with a one-shot classifier prompt; off-topic questions are rejected early.
3. **Embed** — question is embedded with the same `text-embedding-ada-002` model.
4. **Vector search** — top-K chunks retrieved from Azure AI Search using HNSW approximate nearest-neighbour.
5. **Generate** — retrieved chunks + question sent to **Claude** (via Azure AI Foundry); answer is returned along with ranked source metadata.

**Claude keys:**

- In **Azure AI Foundry portal → Project → Deployments**, deploy a Claude model.  
- Copy the **Target URI** → `CLAUDE_ENDPOINT` and **Key** → `CLAUDE_API_KEY`.

```dotenv
CLAUDE_ENDPOINT=https://<project>.services.ai.azure.com/anthropic/
CLAUDE_API_KEY=<key>
CLAUDE_DEPLOYMENT_NAME=claude-sonnet-4-6
```

---

## Running the pipeline

```bash
# Install dependencies
pip install -r requirements.txt

# Run ingest (scrape → chunk → embed → upload)
python backend/ingest.py

# Start the API server
uvicorn app:app --reload
```

Re-run `ingest.py` whenever SharePoint content changes. The `mergeOrUpload` action means existing chunks are updated in-place and new ones are added.
