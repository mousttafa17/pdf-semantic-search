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
* observability,
* and an architecture that is easy to explain and extend.

The implementation intentionally avoids unnecessary infrastructure or optimization that is not justified by the assessment requirements.

---

# 1. Project Goals

The system provides two primary capabilities.

## PDF ingestion

The system:

1. Accepts PDF documents through the API.
2. Extracts their text.
3. Splits extracted text into chunks.
4. Generates an embedding for each chunk.
5. Stores embeddings and metadata in a vector database.

The `/ingest/` API supports:

* a single PDF upload,
* multiple PDF uploads using repeated `input` fields,
* a directory path containing PDF files visible inside the application container.

## Semantic search

The system:

1. Accepts a natural-language query.
2. Generates an embedding for the query.
3. Searches the vector database using similarity.
4. Returns the most relevant document chunks.

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

The embedding model is downloaded during the application image build so that normal ingestion does not depend on downloading the model at request time.

## Keep infrastructure self-initializing

The application waits for Qdrant to become reachable and automatically creates the required collection when starting from an empty environment.

## Fail clearly

Invalid inputs and dependency failures produce controlled API responses rather than exposing internal tracebacks.

## Avoid unnecessary complexity

The assessment focuses on practical engineering and reasoning rather than large-scale infrastructure.

The implementation therefore does not introduce queues, Redis, Kafka, Kubernetes, or additional services without a concrete requirement.

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

│   ├── logging_config.py

│   ├── main.py

│   └── models.py

│

├── data/

│   └── pdfs/

│

├── tests/

│   ├── test_chunking.py

│   ├── test_concurrent_ingestion.py

│   ├── test_embedding_initialization_concurrency.py

│   ├── test_embeddings.py

│   ├── test_ingest_api.py

│   ├── test_ingestion.py

│   ├── test_pdf.py

│   ├── test_search.py

│   ├── test_search_api.py

│   └── test_vector_store.py

│

├── evaluation/

│   ├── dataset.json

│   └── evaluate.py

│

├── Dockerfile

├── docker-compose.yml

├── docker-compose.dev.yml

├── orchestrate.sh

├── requirements.txt

├── README.md

├── IMPLEMENTATION_PATH.md

├── ARCHITECTURE_DECISIONS.md

└── suite.py
```

The structure evolved during implementation, but responsibilities remain separated by application concern.

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
* invalid or corrupt binary content,
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

The implementation uses:

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

## Bounded inference batches

Document embeddings are generated using a bounded batch size:

```text
EMBEDDING_BATCH_SIZE=32
```

The batch size limits peak memory usage during local embedding inference.

During testing with larger assessment PDFs, the previous unbounded/default batching caused the application container to approach its memory limit. Reducing the inference batch size kept memory usage substantially lower while allowing large multi-document ingestion to complete successfully.

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

The endpoint accepts the `input` field in three supported forms.

## Single PDF

A single PDF can be uploaded directly.

```text
input = PDF file
```

## Multiple PDFs

Multiple PDF files can be supplied by repeating the same multipart field:

```text
input = PDF file 1
input = PDF file 2
input = PDF file 3
```

## Directory path

A directory path can be provided as the `input` value.

The application can read PDF files from directories exposed inside the container through the `/data` mount.

Only PDF files are processed from a directory.

Non-PDF files are ignored.

## Input validation

The API rejects:

* missing input,
* files without filenames,
* non-PDF uploads,
* empty uploads,
* invalid directory paths,
* directories containing no PDFs,
* mixed file-upload and directory-path input.

## HTTP flow

```text
HTTP input

     │

     ▼

Identify input mode

     │

     ├── uploaded PDF file(s)

     │

     └── directory path

     │

     ▼

Read PDF bytes

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

Successful responses contain:

```json
{
  "message": "Successfully ingested 1 PDF documents.",
  "files": [
    "sample.pdf"
  ]
}
```

## Status

**Completed and tested**

The API has been manually verified for:

* single-file ingestion,
* multiple-file ingestion,
* directory ingestion.

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

This is particularly important when the application is already populated.

## Status

**Completed**

---

# 16. Stage 13 — Concurrent Upload Handling

## Objective

Verify that multiple ingestion requests can execute concurrently without corrupting application state.

The evaluator explicitly mentions concurrent uploads as an edge case.

The tests verify scenarios such as:

```text
Request A ─┐

Request B ─┤

Request C ─┼──► /ingest/

Request D ─┤

Request E ─┘
```

and confirm that:

* concurrent uploads remain isolated,
* document IDs remain correct,
* document contents remain associated with the correct documents,
* repeated concurrent ingestion of the same document remains idempotent.

No queue, Redis layer, or separate worker service is introduced.

## Status

**Completed and tested**

---

# 17. Stage 14 — Error Handling Hardening

The implementation provides controlled handling for client and server failures.

## Client/input errors

The API returns HTTP `400` for cases such as:

```text
missing input

non-PDF upload

empty upload

invalid/corrupt document

PDF with no extractable text

invalid directory

directory containing no PDFs

mixed input modes

empty query

whitespace-only query
```

## Internal failures

The API returns HTTP `500` for cases such as:

```text
embedding/model failure

Qdrant failure

unexpected application failure
```

The externally visible error shape is:

```json
{
  "error": "..."
}
```

Internal implementation details and tracebacks are not exposed through the API.

## Status

**Completed and tested**

---

# 18. Stage 15 — Observability and Logging

The application uses Python's standard `logging` module.

Logs provide operational context for major lifecycle events such as:

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

Operational metadata includes values such as:

```text
operation

filename

document ID

chunk count

result count

duration

failure type
```

Document contents and complete search queries are not logged.

## Status

**Completed and tested**

---

# 19. Stage 16 — Project Test Suite

Testing is performed at multiple levels.

## Component tests

The project tests:

* PDF extraction,
* chunking,
* embedding generation,
* vector storage.

## Service tests

The project tests:

* ingestion orchestration,
* semantic-search orchestration,
* document identity,
* idempotent re-ingestion.

## API tests

The project tests:

* `/ingest/`,
* `/search/`,
* single-file ingestion,
* multiple-file ingestion,
* directory ingestion,
* directory filtering,
* invalid directory handling,
* mixed input rejection,
* request validation,
* response structure,
* 400/500 error classification.

FastAPI dependencies are overridden in API tests so API-level tests can exercise request handling without invoking the production embedding model unnecessarily.

## Concurrency tests

The project also tests:

* concurrent ingestion of different PDFs,
* concurrent repeated ingestion of the same PDF,
* concurrent embedding-model initialization.

## Current test status

The application test suite contains:

```text
62 tests
```

All 62 are passing.

## Status

**Completed**

---

# 20. Stage 17 — Supplied Evaluator

The provided:

```text
suite.py
```

is preserved unchanged.

The evaluator-facing environment supports:

```text
start

  ↓

ingest

  ↓

search
```

The supplied suite currently contains:

```text
2 tests
```

Both pass successfully inside the application container.

## Status

**Completed and verified**

---

# 21. Stage 18 — Retrieval Evaluation

## Objective

Provide a small, manually labeled benchmark for observing semantic retrieval behavior independently from the supplied functional evaluator.

The evaluation dataset is stored in:

```text
evaluation/dataset.json
```

The evaluation script is:

```text
evaluation/evaluate.py
```

## Evaluation flow

```text
Benchmark dataset

       │

       ▼

Generate temporary PDFs

       │

       ▼

POST /ingest/

       │

       ▼

POST /search/

       │

       ▼

Compare retrieved documents

       │

       ▼

Hit@k / Precision@k / Recall@k
```

The benchmark evaluates:

```text
k = 1

k = 3

k = 5
```

The relevance labels are manually defined in the dataset and are independent of the vector similarity scores.

## Evaluation isolation

The benchmark should be run against a clean Qdrant collection.

Documents from previous demo runs should not remain in the collection, because unrelated vectors would affect retrieval results and make the benchmark measurements invalid.

The evaluation is intentionally kept separate from the production API and does not introduce a production-only evaluation endpoint.

## Status

**Completed**

---

# 22. Stage 19 — Development and Evaluator Environments

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

# 23. Stage 20 — Orchestration

## Start

The orchestration script:

1. Builds the application image.
2. Starts the application.
3. Starts Qdrant.
4. Establishes the Docker network.
5. Makes the API available on port `8000`.

Command:

```bash
./orchestrate.sh --action start
```

## Terminate

The termination command:

1. Stops containers.
2. Removes containers.
3. Removes project-created networks.
4. Removes project-created volumes.

Command:

```bash
./orchestrate.sh --action terminate
```

The volume cleanup is intentional because it provides a clean evaluator-facing environment for the next start.

## Clean-environment verification

The complete lifecycle has been verified from a fresh repository environment:

```text
clone

  ↓

orchestrate.sh --action start

  ↓

health check

  ↓

application tests

  ↓

supplied suite.py

  ↓

orchestrate.sh --action terminate
```

## Status

**Completed and verified**

---

# 24. Stage 21 — Documentation

The README documents:

* project purpose,
* architecture,
* prerequisites,
* startup instructions,
* ingestion examples,
* single and multiple-file ingestion,
* directory ingestion,
* search examples,
* configuration,
* testing,
* retrieval evaluation,
* design decisions,
* known limitations.

`ARCHITECTURE_DECISIONS.md` records the reasoning and trade-offs behind major design choices.

This document records the implementation sequence and project evolution.

## Status

**Completed**

---

# 25. Final Architecture

The completed architecture is:

```text
                         Docker Compose

┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                     FastAPI App                       │  │
│  │                                                       │  │
│  │   /ingest/                    /search/                │  │
│  │      │                           │                    │  │
│  │      ▼                           ▼                    │  │
│  │ IngestionService           SearchService              │  │
│  │      │                           │                    │  │
│  │      ├── PDF Extraction          │                    │  │
│  │      ├── Chunking                │                    │  │
│  │      ├── Document Embedding      └── Query Embedding  │  │
│  │      │                           │                    │  │
│  │      └───────────────┬───────────┘                    │  │
│  │                      │                                │  │
│  │                      ▼                                │  │
│  │                 Qdrant Client                         │  │
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

The main ingestion data flow is:

```text
PDF

 ↓

PyMuPDF

 ↓

1000-character chunks

 ↓

FastEmbed / BAAI/bge-small-en-v1.5

 ↓

384-dimensional embeddings

 ↓

Qdrant
```

The main retrieval data flow is:

```text
Query

 ↓

FastEmbed / BAAI/bge-small-en-v1.5

 ↓

384-dimensional query embedding

 ↓

Qdrant cosine similarity search

 ↓

Top-K chunks

 ↓

Document + score + content
```

---

# 26. Current Development Milestones

```text
[✓] Dockerized FastAPI application starts

[✓] Qdrant starts with the application

[✓] Application waits for Qdrant readiness

[✓] Qdrant collection is created automatically

[✓] PDF text extraction works

[✓] PDF extraction edge cases are tested

[✓] Assessment text fixture compatibility is implemented

[✓] Text chunking works

[✓] Chunking edge cases are tested

[✓] FastEmbed embedding generation works

[✓] Query/passages use retrieval-specific prefixes

[✓] Embedding dimension is validated

[✓] Bounded embedding batch size is configured

[✓] Chunk embeddings are stored in Qdrant

[✓] Deterministic point IDs work

[✓] Content-based document IDs work

[✓] Idempotent repeated ingestion works

[✓] Document ingestion pipeline works

[✓] Semantic-search pipeline works

[✓] /ingest/ works for a single PDF

[✓] /ingest/ works for multiple PDFs

[✓] /ingest/ works for directory input

[✓] Directory ingestion ignores non-PDF files

[✓] Invalid directory input is rejected

[✓] Mixed file/directory input is rejected

[✓] /search/ works

[✓] Dependency injection is implemented

[✓] API tests use dependency overrides

[✓] Test Qdrant collections are isolated

[✓] Concurrent uploads are tested

[✓] Concurrent model initialization is tested

[✓] Error handling is hardened

[✓] Observability/logging is implemented

[✓] Logging regression tests are implemented

[✓] Application test suite passes: 62/62

[✓] Supplied suite.py passes: 2/2

[✓] Retrieval evaluation benchmark is implemented

[✓] Development environment is separated from evaluator environment

[✓] Clean evaluator start/terminate flow is verified

[✓] README documentation is complete
```

---

# 27. Implementation Philosophy

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

     ↓

Evaluation
```

The objective is not to build the largest possible system.

The objective is to build the **simplest system that satisfies the requirements reliably, is easy to understand, and has clear reasoning behind its design choices**.
