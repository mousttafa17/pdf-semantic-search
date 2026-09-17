# Implementation Path

## PDF Ingestor & Semantic Search API

This document describes the implementation path for the PDF Ingestor & Semantic Search API.

The project is intentionally developed incrementally. Each stage introduces one major responsibility, verifies that it works independently, and then connects it to the previous stages. The goal is to keep the system understandable, reproducible, and easy to evaluate.

---

## 1. Project Goals

The system provides two primary API capabilities:

1. **PDF ingestion**

   * Accept PDF documents.
   * Extract their text.
   * Split extracted text into meaningful chunks.
   * Generate an embedding for each chunk.
   * Store embeddings and metadata in a vector database.

2. **Semantic search**

   * Accept a natural-language query.
   * Generate an embedding for the query.
   * Perform vector similarity search.
   * Return the most semantically relevant document chunks.

The complete data flow is:

```text
PDF
 │
 ▼
Text Extraction
 │
 ▼
Text Chunking
 │
 ▼
Embedding Generation
 │
 ▼
Vector Database
 │
 └───────────────┐
                 │
User Query       │
 │               │
 ▼               │
Query Embedding  │
 │               │
 └──────► Similarity Search
                 │
                 ▼
          Relevant Chunks
```

---

# 2. Implementation Principles

The implementation follows several principles throughout the project.

### Keep responsibilities separated

PDF processing, chunking, embedding generation, vector storage, and API handling are separate responsibilities.

This allows individual components to be changed or tested without rewriting the entire application.

### Prefer reproducibility

The complete runtime environment is containerized so that the evaluator does not need to install Python packages or database software manually.

### Keep infrastructure self-initializing

The application should be able to start against an empty environment and create the required vector database collection automatically.

### Fail clearly

Invalid files, empty queries, unavailable dependencies, and processing failures should result in clear API responses rather than unhandled exceptions.

### Avoid unnecessary complexity

The assessment focuses on practical engineering and reasoning rather than large-scale infrastructure. The implementation therefore avoids unnecessary services such as Kafka, Redis, Kubernetes, or separate worker systems unless a concrete requirement emerges.

---

# 3. Project Structure

The project is organized around application responsibilities:

```text
pdf-semantic-search/
│
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   └── search.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── pdf.py
│   │   └── vector_store.py
│   │
│   ├── __init__.py
│   ├── config.py
│   ├── main.py
│   └── models.py
│
├── data/
├── tests/
│
├── Dockerfile
├── docker-compose.yml
├── orchestrate.sh
├── requirements.txt
├── README.md
├── IMPLEMENTATION_PATH.md
├── suite.py
└── swagger.yaml
```

The structure may evolve slightly as implementation details become clearer, but responsibilities will remain separated.

---

# 4. Stage 1 — Containerized Application Skeleton

### Objective

Create the minimum runnable FastAPI application and establish Docker as the source of truth for the runtime environment.

### Components

* FastAPI
* Uvicorn
* Docker
* Docker Compose

### Initial API

A basic health endpoint is provided:

```text
GET /health
```

The purpose of this stage is to verify that:

* the application builds successfully,
* the container starts correctly,
* port `8000` is exposed,
* the API is accessible from the host,
* dependencies are isolated from the host machine.

### Verification

```bash
./orchestrate.sh --action start
```

Then:

```bash
curl http://localhost:8000/health
```

Expected result:

```json
{
  "status": "ok"
}
```

---

# 5. Stage 2 — Vector Database Infrastructure

### Objective

Introduce a vector database and establish the storage layer required for semantic search.

### Technology

**Qdrant**

Qdrant is responsible for:

* storing embeddings,
* storing chunk metadata,
* performing vector similarity search.

The FastAPI application communicates with Qdrant through the Qdrant Python client.

### Collection

The application automatically creates the required collection when starting against an empty Qdrant instance.

The collection will use:

* vector size matching the selected embedding model,
* cosine similarity,
* metadata containing document and chunk information.

### Persistence

Qdrant storage is backed by a Docker volume:

```text
qdrant_data
```

This prevents vector data from being tied to the lifecycle of the application container.

### Startup behavior

The API waits until Qdrant becomes reachable before continuing startup.

The startup sequence is therefore:

```text
Start containers
      │
      ▼
Wait for Qdrant
      │
      ▼
Connect successfully
      │
      ▼
Ensure collection exists
      │
      ▼
Start serving API
```

### Verification

The evaluator can inspect the Qdrant collections:

```bash
curl http://localhost:6333/collections
```

The expected collection is:

```text
documents
```

---

# 6. Stage 3 — PDF Text Extraction

### Objective

Convert uploaded PDF documents into clean textual content.

### Technology

**PyMuPDF**

For each PDF:

```text
Uploaded file
     │
     ▼
Open PDF
     │
     ▼
Read pages
     │
     ▼
Extract text
     │
     ▼
Normalize text
```

The extraction layer will handle invalid or unreadable documents explicitly.

Potential failure cases include:

* invalid PDF content,
* corrupted files,
* documents with no extractable text.

These cases should not silently produce empty embeddings.

---

# 7. Stage 4 — Text Chunking

### Objective

Split extracted document text into smaller units suitable for embedding and retrieval.

Embedding an entire large document as one vector would make retrieval less precise. Instead, the text is divided into chunks that represent focused pieces of information.

The initial strategy will use:

* a bounded chunk size,
* controlled overlap between adjacent chunks.

Conceptually:

```text
Document
│
├── Chunk 0
├── Chunk 1
├── Chunk 2
├── Chunk 3
└── ...
```

Overlap is used to reduce the probability that important context is lost at chunk boundaries.

The exact parameters will be kept configurable so they can be adjusted without changing the API layer.

---

# 8. Stage 5 — Embedding Generation

### Objective

Convert text chunks into numerical vectors that capture semantic meaning.

### Technology

**Sentence Transformers**

Initial model:

```text
all-MiniLM-L6-v2
```

The same embedding model must be used for:

* document chunks,
* search queries.

The flow is:

```text
Text chunk
    │
    ▼
Embedding model
    │
    ▼
Vector
```

The selected model produces vectors with a fixed dimensionality. The Qdrant collection is configured using that same dimensionality.

This creates the contract:

```text
Embedding model dimension
        =
Qdrant vector dimension
```

Changing the embedding model would therefore require corresponding vector-store configuration changes.

---

# 9. Stage 6 — Store Embeddings and Metadata

### Objective

Persist each chunk and its embedding in Qdrant.

Each stored point contains:

### Vector

The embedding generated from the chunk.

### Metadata

At minimum:

```json
{
  "document": "sample.pdf",
  "chunk_index": 0,
  "content": "..."
}
```

A stable document identifier may also be maintained so that two documents with the same filename can still be distinguished.

Conceptually:

```text
Document
   │
   ├── Chunk 0 ──► Vector ──► Qdrant
   ├── Chunk 1 ──► Vector ──► Qdrant
   ├── Chunk 2 ──► Vector ──► Qdrant
   └── ...
```

---

# 10. Stage 7 — `/ingest/` Endpoint

### Objective

Expose the complete ingestion pipeline through the required API.

Endpoint:

```text
POST /ingest/
```

The endpoint accepts the required `input` field.

The processing pipeline becomes:

```text
Upload
  │
  ▼
Validate input
  │
  ▼
Extract PDF text
  │
  ▼
Chunk text
  │
  ▼
Generate embeddings
  │
  ▼
Store vectors + metadata
  │
  ▼
Return ingestion result
```

Successful responses will contain:

```json
{
  "message": "Successfully ingested ...",
  "files": [
    "sample.pdf"
  ]
}
```

Invalid input will produce an appropriate `400` response.

Internal processing failures will produce an appropriate server-side error response without exposing implementation tracebacks to API clients.

---

# 11. Stage 8 — `/search/` Endpoint

### Objective

Expose semantic retrieval over the stored document chunks.

Endpoint:

```text
POST /search/
```

Request:

```json
{
  "query": "How does semantic search work?"
}
```

The search flow is:

```text
User Query
    │
    ▼
Validate query
    │
    ▼
Generate query embedding
    │
    ▼
Qdrant similarity search
    │
    ▼
Retrieve top relevant chunks
    │
    ▼
Return document + score + content
```

Example response:

```json
{
  "results": [
    {
      "document": "sample.pdf",
      "score": 0.89,
      "content": "..."
    }
  ]
}
```

The similarity score is supplied by the vector database.

---

# 12. Stage 9 — Input Validation and Failure Handling

After the core ingestion and search paths are functional, explicit edge-case handling will be added.

The implementation will consider at least:

| Case                         | Expected behavior                    |
| ---------------------------- | ------------------------------------ |
| Missing upload               | `400`                                |
| Non-PDF upload               | `400`                                |
| Invalid/corrupt PDF          | `400`                                |
| PDF with no extractable text | `400`                                |
| Empty query                  | `400`                                |
| Whitespace-only query        | `400`                                |
| Qdrant unavailable           | service error / unavailable response |
| Embedding failure            | server error                         |
| Unexpected internal failure  | controlled server error              |

The API should remain predictable even when an individual operation fails.

---

# 13. Stage 10 — Concurrent Upload Handling

The evaluator explicitly mentions concurrent uploads, so the ingestion implementation will avoid shared temporary filenames and shared mutable application state.

Each request should operate on its own uploaded data.

The vector database is treated as the persistent source of truth rather than maintaining an in-memory global document list.

The goal is to allow multiple ingestion requests to execute without one request corrupting another request's temporary state.

---

# 14. Stage 11 — Testing

Testing will be performed at multiple levels.

### Supplied functional test

The provided:

```text
suite.py
```

will be executed against the running service.

The project will be checked against its expected:

```text
start → ingest → search
```

flow.

### Additional edge-case tests

Additional tests will cover behaviors such as:

* empty search queries,
* invalid uploads,
* malformed documents,
* repeated ingestion,
* searches against an empty database,
* API health,
* concurrent requests where practical.

The provided `swagger.yaml` will also be used as an API contract reference.

---

# 15. Stage 12 — Observability and Logging

The application will provide useful logs for major lifecycle events, such as:

```text
Application startup
Qdrant connection established
Collection created/found
Document ingestion started
Document ingestion completed
Search request received
Search completed
Processing failure
```

Logs should provide enough context to diagnose failures without exposing sensitive document contents unnecessarily.

---

# 16. Stage 13 — Orchestration

The complete environment must be controllable through:

```bash
./orchestrate.sh --action start
```

and:

```bash
./orchestrate.sh --action terminate
```

### Start

The start operation will:

1. Build the application image.
2. Start the application container.
3. Start Qdrant.
4. Establish the Docker network.
5. Make the API available on port `8000`.

### Terminate

The terminate operation will:

1. Stop the containers.
2. Remove the containers.
3. Remove project-created networks.
4. Remove volumes using Docker Compose volume cleanup.

The goal is to make the complete environment reproducible from a clean state.

---

# 17. Stage 14 — Documentation

The final README will document:

* project purpose,
* architecture,
* prerequisites,
* startup instructions,
* ingestion examples,
* search examples,
* API behavior,
* configuration,
* design decisions,
* testing instructions,
* known limitations.

The documentation will intentionally explain **why** major design decisions were made rather than simply listing technologies.

---

# 18. Final System

Once all stages are complete, the architecture will look like:

```text
                         Docker Compose
┌─────────────────────────────────────────────────────────┐
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │                   FastAPI App                    │  │
│  │                                                   │  │
│  │  /ingest/                                         │  │
│  │      │                                            │  │
│  │      ▼                                            │  │
│  │  PDF Extraction                                   │  │
│  │      │                                            │  │
│  │      ▼                                            │  │
│  │  Chunking                                         │  │
│  │      │                                            │  │
│  │      ▼                                            │  │
│  │  Embedding Model                                  │  │
│  │      │                                            │  │
│  │      └─────────────────────┐                      │  │
│  │                            ▼                      │  │
│  │  /search/              Vector Store              │  │
│  │      │                      │                     │  │
│  │      ▼                      ▼                     │  │
│  │  Query Embedding       Qdrant Client             │  │
│  │                             │                     │  │
│  └─────────────────────────────┼─────────────────────┘  │
│                                │                        │
│                                ▼                        │
│                       ┌────────────────┐               │
│                       │     Qdrant     │               │
│                       │                │               │
│                       │ vectors        │               │
│                       │ metadata       │               │
│                       └───────┬────────┘               │
│                               │                        │
│                        qdrant_data                     │
│                           volume                        │
└─────────────────────────────────────────────────────────┘
```

---

# 19. Development Milestones

The implementation is considered complete when the following milestones have been verified:

```text
[✓] Dockerized FastAPI application starts
[✓] Qdrant starts with the application
[✓] Application waits for Qdrant readiness
[✓] Qdrant collection is created automatically
[✓] PDF text extraction works
[✓] PDF extraction edge cases are tested
[✓] Text chunking works
[✓] Chunking edge cases are tested
[✓] Embedding generation works
[✓] Chunk embeddings are stored in Qdrant
[ ] /ingest/ works
[ ] /search/ works
[ ] Invalid input is handled cleanly
[ ] Concurrent uploads are handled safely
[ ] Supplied suite.py passes
[ ] Documentation is complete
[ ] Clean start/terminate flow verified
```

The checklist is intentionally updated as implementation progresses so that the repository history and this document together show how the system evolved from infrastructure to a complete semantic-search service.
