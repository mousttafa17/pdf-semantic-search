# Implementation Path

## PDF Ingestor & Semantic Search API

This document describes the implementation path for the PDF Ingestor & Semantic Search API.

The project is being developed incrementally. Each stage introduces a major responsibility, verifies it independently, and then integrates it with the rest of the system.

The implementation prioritizes:

* practical engineering,
* clear separation of responsibilities,
* reproducibility,
* predictable failure handling,
* testability,
* and an architecture that is easy to explain and extend.

The implementation intentionally avoids unnecessary infrastructure or optimization that is not justified by the assessment requirements.

---

# 1. Project Goals

The system provides two primary capabilities.

## PDF ingestion

The system must:

1. Accept PDF documents through the API.
2. Extract their text.
3. Split extracted text into chunks.
4. Generate an embedding for each chunk.
5. Store embeddings and metadata in a vector database.

## Semantic search

The system must:

1. Accept a natural-language query.
2. Generate an embedding for the query.
3. Search the vector database using similarity.
4. Return the most relevant document chunks.

The resulting data flow is:

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
Document Embedding
 │
 ▼
Qdrant
 │
 │
 │
User Query
 │
 ▼
Query Embedding
 │
 ▼
Qdrant Similarity Search
 │
 ▼
Relevant Chunks
```

---

# 2. Implementation Principles

## Keep responsibilities separated

PDF extraction, chunking, embedding generation, vector storage, ingestion orchestration, search orchestration, and API handling are separate responsibilities.

This allows individual components to be tested and replaced without rewriting the entire system.

## Prefer reproducibility

Runtime dependencies are isolated inside Docker so that the evaluator does not need to install Python packages or database software manually.

## Keep infrastructure self-initializing

The application waits for Qdrant to become reachable and automatically creates the required collection when starting from an empty environment.

## Fail clearly

Invalid inputs and dependency failures should produce controlled API responses rather than exposing internal tracebacks.

## Avoid unnecessary complexity

The assessment focuses on practical engineering and reasoning rather than large-scale infrastructure.

The implementation therefore does not introduce queues, Redis, Kafka, Kubernetes, or additional services unless a concrete requirement justifies them.

---

# 3. Current Project Structure

The current project is organized around application responsibilities:

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
│   │   ├── ingestion.py
│   │   ├── pdf.py
│   │   ├── search.py
│   │   └── vector_store.py
│   │
│   ├── __init__.py
│   ├── config.py
│   ├── dependencies.py
│   ├── main.py
│   └── models.py
│
├── data/
├── tests/
│   ├── test_chunking.py
│   ├── test_embeddings.py
│   ├── test_ingest_api.py
│   ├── test_ingestion.py
│   ├── test_pdf.py
│   ├── test_search.py
│   ├── test_search_api.py
│   └── test_vector_store.py
│
├── Dockerfile
├── docker-compose.yml
├── docker-compose.dev.yml
├── orchestrate.sh
├── requirements.txt
├── README.md
├── IMPLEMENTATION_PATH.md
├── ARCHITECTURE_DECISIONS.md
├── suite.py
└── swagger.yaml
```

The structure may evolve slightly as hardening continues, but responsibilities will remain separated.

---

# 4. Stage 1 — Containerized Application Skeleton

## Objective

Create the minimum runnable FastAPI application and establish Docker as the source of truth for the runtime environment.

## Components

* FastAPI
* Uvicorn
* Docker
* Docker Compose

## Initial API

```text
GET /health
```

The initial stage verified that:

* the application builds,
* the container starts,
* port `8000` is exposed,
* the API is accessible from the host,
* Python dependencies are isolated from the host.

## Status

**Completed**

---

# 5. Stage 2 — Vector Database Infrastructure

## Objective

Introduce a vector database and establish the storage layer required for semantic search.

## Technology

**Qdrant**

Qdrant is responsible for:

* storing embeddings,
* storing chunk metadata,
* performing vector similarity search.

The application communicates with Qdrant through the Qdrant Python client.

## Collection

The application creates a collection named:

```text
documents
```

The collection is configured using:

```text
vector dimension: 384
distance metric:  cosine
```

The vector dimension is aligned with the selected embedding model.

## Persistence

Qdrant storage is backed by:

```text
qdrant_data
```

This keeps stored vectors independent of the application container lifecycle.

## Startup behavior

The application waits for Qdrant to become reachable before completing startup.

```text
Start containers
      │
      ▼
Wait for Qdrant
      │
      ▼
Qdrant available
      │
      ▼
Ensure collection exists
      │
      ▼
Application ready
```

## Status

**Completed and tested**

---

# 6. Stage 3 — PDF Text Extraction

## Objective

Convert uploaded documents into clean textual content.

## Technology

**PyMuPDF**

The extraction pipeline is:

```text
Uploaded file
     │
     ▼
Open document
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

The extraction service explicitly handles:

* empty files,
* invalid/corrupt binary content,
* PDFs with no extractable text.

## Assessment fixture compatibility

The supplied `suite.py` creates a file named `sample.pdf` containing plain text rather than a real PDF.

To remain compatible with the supplied test, the extraction service has a narrow fallback for readable UTF-8 text after PDF parsing fails.

Binary or unreadable content is still rejected.

This is treated as an assessment compatibility accommodation rather than the preferred production PDF-validation strategy.

## Status

**Completed and tested**

---

# 7. Stage 4 — Text Chunking

## Objective

Split extracted text into retrieval units before generating embeddings.

The initial implementation uses:

```text
chunk_size:    1000 characters
chunk_overlap: 200 characters
```

The chunking process is:

```text
Document
 │
 ├── Chunk 0
 ├── Chunk 1
 ├── Chunk 2
 ├── ...
```

The overlap preserves context across adjacent boundaries.

The chunker is implemented independently from the API, embedding model, and vector database.

## Status

**Completed and tested**

---

# 8. Stage 5 — Embedding Generation

## Objective

Convert document chunks and search queries into numerical vectors suitable for semantic retrieval.

## Technology

**Qdrant FastEmbed**

## Model

```text
BAAI/bge-small-en-v1.5
```

The model produces 384-dimensional embeddings.

The same model is used for both:

```text
document passages
search queries
```

## Retrieval-specific prefixes

Document chunks are embedded using:

```text
passage: <chunk>
```

Search queries are embedded using:

```text
query: <query>
```

This explicitly distinguishes query and passage roles for the selected retrieval model.

## Runtime choice

FastEmbed was selected instead of a Sentence Transformers + PyTorch stack because it provides a lighter local inference path suitable for a CPU-oriented Dockerized assessment.

This reduces unnecessary runtime overhead while remaining fully local and avoiding external embedding API credentials.

## Dimension validation

Generated vectors are checked against the configured embedding dimension before being stored.

The relationship is:

```text
Embedding Model
      │
      ▼
384 dimensions
      │
      ▼
Qdrant collection
      │
      ▼
384-dimensional vectors
```

## Status

**Completed and tested**

---

# 9. Stage 6 — Qdrant Point Storage

## Objective

Persist each document chunk and its embedding in Qdrant.

Each chunk becomes one Qdrant point containing:

```text
ID
Vector
Payload
```

The payload contains:

```json
{
  "document_id": "...",
  "document": "sample.pdf",
  "chunk_index": 3,
  "content": "..."
}
```

## Point identity

Point IDs are deterministic UUIDs derived from:

```text
document_id + chunk_index
```

This makes repeated ingestion of identical document content idempotent at the chunk level.

For the same document and chunk:

```text
document_id + chunk_index
        │
        ▼
same point ID
```

Qdrant upsert semantics can therefore update an existing point rather than creating another point with a different ID.

## Status

**Completed and tested**

---

# 10. Stage 7 — Document Ingestion Service

## Objective

Combine the individual document-processing components into one application-level ingestion workflow.

The ingestion service performs:

```text
PDF bytes
    │
    ▼
PDF extraction
    │
    ▼
Text chunking
    │
    ▼
Document embeddings
    │
    ▼
Qdrant upsert
```

The service is independent of HTTP and FastAPI.

This allows it to be tested without going through the API layer.

## Document identity

A document ID is generated using:

```text
SHA-256(file bytes)
```

This means identical document content receives the same document ID even when filenames differ.

## Status

**Completed and tested**

---

# 11. Stage 8 — Semantic Search Service

## Objective

Combine query embedding and vector retrieval into one application-level search workflow.

The search service performs:

```text
User query
    │
    ▼
Query embedding
    │
    ▼
Qdrant similarity search
    │
    ▼
Ranked points
    │
    ▼
Search results
```

The current default is:

```text
top_k = 5
```

The value is configurable.

## Similarity threshold

No initial score threshold is applied.

The current system returns up to the configured top-K nearest chunks.

This avoids introducing an arbitrary relevance cutoff before retrieval behavior has been evaluated on representative data.

## Status

**Completed and tested**

---

# 12. Stage 9 — `/ingest/` API

## Objective

Expose the complete ingestion pipeline through the required API.

Endpoint:

```text
POST /ingest/
```

The endpoint accepts one or more uploaded files through the `input` field.

The HTTP flow is:

```text
HTTP upload
     │
     ▼
Validate filename/input
     │
     ▼
Read file bytes
     │
     ▼
IngestionService
     │
     ├── PDF extraction
     ├── chunking
     ├── embedding
     └── Qdrant storage
     │
     ▼
HTTP response
```

Successful response:

```json
{
  "message": "Successfully ingested 1 PDF documents.",
  "files": [
    "sample.pdf"
  ]
}
```

Invalid inputs are returned as controlled `400` responses.

## Status

**Completed and tested**

The supplied `suite.py` ingestion test passes.

---

# 13. Stage 10 — `/search/` API

## Objective

Expose semantic retrieval through the required API.

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

Processing flow:

```text
Query
  │
  ▼
Validate
  │
  ▼
Query embedding
  │
  ▼
Qdrant similarity search
  │
  ▼
Top-K points
  │
  ▼
document + score + content
```

Example response:

```json
{
  "results": [
    {
      "document": "sample.pdf",
      "score": 0.81,
      "content": "..."
    }
  ]
}
```

## Status

**Completed and tested**

The supplied `suite.py` search test passes.

---

# 14. Stage 11 — Dependency Injection

## Objective

Centralize application service construction and make API dependencies replaceable during testing.

The dependency layer provides:

```text
EmbeddingService
VectorStore
IngestionService
SearchService
```

The API routes obtain services through FastAPI dependencies rather than constructing them directly.

Conceptually:

```text
FastAPI
  │
  ├── get_ingestion_service()
  │       ├── EmbeddingService
  │       └── VectorStore
  │
  └── get_search_service()
          ├── EmbeddingService
          └── VectorStore
```

This provides:

* centralized configuration,
* reusable service instances,
* cleaner route modules,
* test dependency overrides,
* better separation between API and application logic.

## Status

**Completed and tested**

---

# 15. Stage 12 — Test Isolation

## Objective

Ensure that tests cannot accidentally destroy or modify production application data.

Tests use unique Qdrant collections such as:

```text
test-documents-<unique-id>
```

rather than deleting and recreating the production:

```text
documents
```

collection.

This allows the following workflow:

```text
Production collection
    ↓
contains real documents

Tests
    ↓
use isolated test collections
    ↓
clean up after themselves
```

This is particularly important because the evaluator may run tests against a populated database.

## Status

**Completed**

---

# 16. Stage 13 — Concurrent Upload Handling

## Objective

Verify that multiple ingestion requests can execute concurrently without corrupting application state.

The evaluator explicitly mentions concurrent uploads as an edge case.

The test will verify:

```text
Request A ─┐
Request B ─┤
Request C ─┼──► /ingest/
Request D ─┤
Request E ─┘
```

and confirm:

* all requests complete successfully,
* document IDs remain correct,
* document contents remain isolated,
* chunks are not mixed between documents,
* Qdrant contains all expected points.

A second useful scenario is the same document uploaded concurrently multiple times.

Because document and chunk IDs are deterministic, this should not create duplicate points.

No queue, Redis layer, or separate worker service will be introduced unless the tests reveal a concrete need.

## Status

**Pending**

---

# 17. Stage 14 — Error Handling Hardening

The implementation already handles the main invalid-input cases.

The final hardening pass will verify:

| Case                         | Expected behavior       |
| ---------------------------- | ----------------------- |
| Missing upload               | `400`                   |
| Non-PDF upload               | `400`                   |
| Empty upload                 | `400`                   |
| Invalid/corrupt document     | `400`                   |
| PDF with no extractable text | `400`                   |
| Empty query                  | `400`                   |
| Whitespace-only query        | `400`                   |
| Embedding failure            | `500`                   |
| Qdrant failure               | `500`                   |
| Unexpected internal failure  | controlled server error |

The goal is to ensure that the externally visible API behavior is deliberate and consistent.

## Status

**Partially completed; final hardening pending**

---

# 18. Stage 15 — Observability and Logging

The final implementation will provide useful logs for major lifecycle events, such as:

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

Logs will provide enough context to diagnose failures without unnecessarily logging complete document contents.

## Status

**Pending**

---

# 19. Stage 16 — Testing

Testing is performed at multiple levels.

## Component tests

The project currently tests:

* PDF extraction,
* chunking,
* embedding generation,
* vector storage.

## Service tests

The project currently tests:

* ingestion orchestration,
* semantic-search orchestration.

## API tests

The project currently tests:

* `/ingest/`,
* `/search/`,
* request validation,
* response structure.

FastAPI dependencies are overridden in API tests so API tests do not need to invoke the real embedding model or production collection unnecessarily.

## Supplied functional test

The provided:

```text
suite.py
```

is preserved unchanged and executed directly.

The expected workflow is:

```text
start
  ↓
ingest
  ↓
search
```

## Current test status

The application test suite currently contains:

```text
43 tests
```

and all 43 are passing.

The supplied functional suite contains:

```text
2 tests
```

and both are passing.

## Status

**Core testing completed; concurrency/final edge-case tests pending**

---

# 20. Stage 17 — Development and Evaluator Environments

## Development environment

Development uses:

```text
docker-compose.dev.yml
```

with bind mounts and Uvicorn reload.

This allows ordinary source changes to appear immediately inside the container without rebuilding the image.

For source-code changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

For dependency or Dockerfile changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Development cleanup intentionally avoids unnecessary volume deletion.

## Evaluator environment

The evaluator-facing workflow remains:

```bash
./orchestrate.sh --action start
```

and:

```bash
./orchestrate.sh --action terminate
```

The evaluator-facing environment does not depend on host source-code bind mounts.

## Status

**Completed**

---

# 21. Stage 18 — Orchestration

## Start

The orchestration script must:

1. Build the application image.
2. Start the application.
3. Start Qdrant.
4. Establish the Docker network.
5. Make the API available on port `8000`.

Command:

```bash
./orchestrate.sh --action start
```

## Terminate

The termination command must:

1. Stop containers.
2. Remove containers.
3. Remove project-created networks.
4. Remove volumes.

Command:

```bash
./orchestrate.sh --action terminate
```

The use of volume cleanup is intentional because the assessment explicitly requires a clean termination operation.

## Status

**Implemented; final clean-environment verification pending**

---

# 22. Stage 19 — Documentation

The final README will document:

* project purpose,
* architecture,
* technology choices,
* setup,
* startup instructions,
* ingestion examples,
* search examples,
* configuration,
* testing,
* design decisions,
* known limitations.

`ARCHITECTURE_DECISIONS.md` records the reasoning and trade-offs behind major design choices.

This document records the implementation sequence and current project status.

## Status

**Partially completed**

---

# 23. Final Architecture

Once hardening is complete, the architecture is:

```text
                         Docker Compose
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                     FastAPI App                      │  │
│  │                                                       │  │
│  │   /ingest/                    /search/                │  │
│  │      │                           │                    │  │
│  │      ▼                           ▼                    │  │
│  │ IngestionService           SearchService              │  │
│  │      │                           │                    │  │
│  │      ├── PDF Extraction          │                    │  │
│  │      ├── Chunking                │                    │  │
│  │      ├── Document Embedding      └── Query Embedding │  │
│  │      │                           │                    │  │
│  │      └───────────────┬───────────┘                    │  │
│  │                      │                                │  │
│  │                      ▼                                │  │
│  │                 Qdrant Client                          │  │
│  └──────────────────────┼────────────────────────────────┘  │
│                         │                                   │
│                         ▼                                   │
│                  ┌──────────────┐                           │
│                  │    Qdrant    │                           │
│                  │              │                           │
│                  │   Vectors    │                           │
│                  │   Payload    │                           │
│                  └──────┬───────┘                           │
│                         │                                   │
│                   qdrant_data                               │
│                      volume                                 │
└─────────────────────────────────────────────────────────────┘
```

The main runtime data flow is:

```text
PDF
 ↓
PyMuPDF
 ↓
Chunks
 ↓
FastEmbed / BAAI/bge-small-en-v1.5
 ↓
384-dimensional embeddings
 ↓
Qdrant
```

and:

```text
Query
 ↓
FastEmbed / BAAI/bge-small-en-v1.5
 ↓
384-dimensional query embedding
 ↓
Qdrant similarity search
 ↓
Top-K chunks
```

---

# 24. Current Development Milestones

```text
[✓] Dockerized FastAPI application starts
[✓] Qdrant starts with the application
[✓] Application waits for Qdrant readiness
[✓] Qdrant collection is created automatically

[✓] PDF text extraction works
[✓] PDF extraction edge cases are tested

[✓] Text chunking works
[✓] Chunking edge cases are tested

[✓] FastEmbed embedding generation works
[✓] Embedding dimension is validated

[✓] Chunk embeddings are stored in Qdrant
[✓] Deterministic point IDs work
[✓] Content-based document IDs work

[✓] Document ingestion pipeline works
[✓] Semantic-search pipeline works

[✓] /ingest/ works
[✓] /search/ works

[✓] Dependency injection is implemented
[✓] API tests use dependency overrides
[✓] Test Qdrant collections are isolated

[✓] Supplied suite.py passes
[✓] Full application test suite passes

[ ] Concurrent uploads are tested
[ ] Error handling is fully hardened
[ ] Observability/logging is finalized
[ ] README documentation is complete
[ ] Clean evaluator start/terminate flow is verified
[ ] Final end-to-end evaluator test is completed
```

---

# 25. Implementation Philosophy

The implementation intentionally follows a simple progression:

```text
Infrastructure
     ↓
PDF processing
     ↓
Chunking
     ↓
Embedding
     ↓
Vector storage
     ↓
Ingestion service
     ↓
Search service
     ↓
API endpoints
     ↓
Dependency injection
     ↓
Testing
     ↓
Hardening
```

The objective is not to build the largest possible system.

The objective is to build the **simplest system that satisfies the requirements reliably, is easy to understand, and has clear reasoning behind its design choices**.
