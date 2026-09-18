# Architecture Decisions

## PDF Ingestor & Semantic Search API

This document records the main architectural decisions made while implementing the PDF Ingestor & Semantic Search API.

The goal is not to maximize architectural complexity. Each decision is based on the requirements of the assessment, expected workload, simplicity, reliability, maintainability, and ease of operation.

---

# ADR-001: FastAPI for the API Layer

## Context

The system requires two HTTP endpoints:

- `POST /ingest/`
- `POST /search/`

The API also needs request validation, structured responses, and OpenAPI/Swagger documentation.

## Decision

Use **FastAPI** as the API framework.

## Alternatives Considered

- Flask
- Django REST Framework

## Rationale

FastAPI provides request validation through Pydantic, automatic OpenAPI documentation, straightforward file-upload handling, and good support for asynchronous application workloads.

It also keeps the implementation relatively small, which fits the scope of this assessment.

## Trade-offs

FastAPI introduces an additional framework abstraction compared with a minimal Python HTTP server.

Flask could also satisfy the requirements and has a simpler conceptual model, but FastAPI provides API-specific features that are directly useful here.

---

# ADR-002: Qdrant for Vector Storage

## Context

The assessment requires embeddings and metadata to be stored in a vector database and searched using semantic similarity.

## Decision

Use **Qdrant** as the vector database.

## Alternatives Considered

- PostgreSQL + pgvector
- Another hosted vector database
- In-memory vector storage

## Rationale

Qdrant is purpose-built for vector search, supports payload metadata, provides a Python client, and runs cleanly as a Docker Compose service.

Using a dedicated vector database keeps similarity-search functionality explicit and avoids implementing nearest-neighbor search ourselves.

## Trade-offs

Using Qdrant introduces a separate infrastructure service whereas PostgreSQL + pgvector could combine relational and vector storage in one database.

For this assessment, the separate service is acceptable because the primary data-access pattern is vector retrieval rather than relational querying.

---

# ADR-003: FastEmbed for Embedding Generation

## Context

The system needs to generate embeddings for document chunks and search queries.

The embedding runtime must be practical inside a container and should not introduce unnecessary resource requirements for a small assessment project.

## Decision

Use **Qdrant FastEmbed** for embedding generation.

### Model

```text
BAAI/bge-small-en-v1.5
```

## Alternatives Considered

- Sentence Transformers + PyTorch
- Larger embedding models
- Hosted embedding APIs

## Rationale

FastEmbed provides a lightweight local embedding runtime based on ONNX Runtime and avoids introducing the full PyTorch stack.

`BAAI/bge-small-en-v1.5` provides 384-dimensional embeddings and is appropriate for retrieval-oriented semantic search.

Running the model locally also avoids external API credentials, network calls during normal inference, and usage-based API costs.

## Trade-offs

A smaller embedding model may provide lower retrieval quality than a larger model.

The decision prioritizes practical CPU inference, simple deployment, and a small container footprint because the assessment emphasizes engineering quality rather than maximum retrieval benchmark performance.

---

# ADR-004: Query and Passage Embedding Prefixes

## Context

The selected BGE embedding model is used for retrieval between search queries and document passages.

## Decision

Prefix document chunks with:

```text
passage:
```

and user queries with:

```text
query:
```

before generating embeddings.

## Rationale

The selected retrieval model distinguishes between queries and passages.

This makes the implementation explicitly aligned with the model's intended information-retrieval usage rather than treating queries and documents as identical embedding inputs.

## Trade-offs

The embedding service becomes somewhat model-specific.

If the project switches to a different embedding model, the prefixing strategy may need to change or be removed.

---

# ADR-005: Cosine Similarity

## Context

The vector database needs a similarity metric for comparing query embeddings with stored document embeddings.

## Decision

Use **cosine similarity** in Qdrant.

## Alternatives Considered

- Dot product
- Euclidean distance

## Rationale

Cosine similarity is intuitive for semantic text retrieval because it measures similarity in vector direction rather than magnitude.

It is compatible with the selected embedding model and straightforward to explain.

## Trade-offs

For normalized vectors, cosine similarity and dot product produce equivalent rankings.

Dot product can be advantageous for implementation efficiency, but the difference is not important for the expected scale of this assessment.

Cosine similarity is therefore preferred for clarity.

---

# ADR-006: Character-Based Text Chunking

## Context

Long PDF documents must be divided into smaller units before embedding.

## Decision

Use a simple fixed-size character-based chunking strategy with overlap.

Initial configuration:

```text
chunk_size:    1000 characters
chunk_overlap: 200 characters
```

## Alternatives Considered

- Token-based chunking
- Paragraph-based chunking
- Sentence-aware chunking
- Semantic chunking

## Rationale

Character-based chunking is deterministic, easy to implement, easy to test, and does not require an additional tokenizer dependency.

The assessment explicitly prioritizes thoughtful engineering over heavy research or optimization, making a simple and understandable strategy appropriate.

## Trade-offs

Character boundaries do not always correspond to semantic or linguistic boundaries.

A token-aware or semantic chunker could produce better retrieval units, but would add complexity.

The current strategy can later be replaced without changing the rest of the ingestion architecture because chunking is isolated behind its own service.

---

# ADR-007: Chunk Overlap

## Context

Splitting text into independent chunks can separate related information across chunk boundaries.

## Decision

Use a fixed overlap between consecutive chunks.

Initial overlap:

```text
200 characters
```

## Rationale

Overlap preserves some context between neighboring chunks and reduces the chance that information spanning a boundary becomes difficult to retrieve.

## Trade-offs

Overlap increases the number of chunks and therefore:

- increases embedding computation,
- increases storage requirements,
- can introduce some duplicated text in retrieval results.

The chosen amount is intentionally modest for the expected document sizes.

---

# ADR-008: One Qdrant Point per Document Chunk

## Context

The system needs to associate each embedding with the original document and text from which it was generated.

## Decision

Store each document chunk as one Qdrant point.

Each point contains:

```text
ID
Vector
Payload
```

The payload contains metadata such as:

```json
{
  "document_id": "...",
  "document": "sample.pdf",
  "chunk_index": 3,
  "content": "..."
}
```

## Rationale

One point per chunk provides a natural retrieval unit.

When a query is executed, Qdrant returns the points whose vectors are most similar to the query vector. Their payloads provide the document name, chunk position, and original text needed for the API response.

## Trade-offs

A document with many chunks produces many stored vectors.

That increases storage and search workload, but provides much more precise retrieval than representing an entire PDF with one vector.

---

# ADR-009: Deterministic UUIDs for Chunk IDs

## Context

The same document may be ingested more than once.

Random point IDs would cause every ingestion to create additional points even when the content represents the same document and chunk.

## Decision

Generate a deterministic UUID from:

```text
document_id + chunk_index
```

## Rationale

The same document and chunk combination produces the same point ID.

This allows Qdrant's `upsert` behavior to update an existing point instead of automatically creating a duplicate.

Conceptually:

```text
document abc123

chunk 0

    ↓

UUID A

same document

chunk 0

    ↓

UUID A
```

## Trade-offs

Deterministic IDs make repeated ingestion easier to handle, but they require a stable document ID.

They also create a separate consideration when replacing documents: if a newer version has fewer chunks, obsolete points must be explicitly removed rather than simply upserting the remaining chunks.

---

# ADR-010: Separate Application Responsibilities into Services

## Context

The ingestion pipeline contains several independent operations:

```text
PDF extraction

chunking

embedding

vector storage
```

## Decision

Implement these responsibilities as separate services/modules.

Current structure:

```text
services/

├── pdf.py
├── chunking.py
├── embeddings.py
├── ingestion.py
├── search.py
└── vector_store.py
```

## Rationale

Each component has one primary responsibility and can be tested independently.

For example:

```text
PDF service

    ↓

verified text

Chunking service

    ↓

verified chunks

Embedding service

    ↓

verified vectors

Vector store

    ↓

verified persistence
```

This reduces the amount of logic required inside the API endpoints.

## Trade-offs

The architecture contains more files and abstractions than a single large ingestion function.

The additional structure is justified because each component has different responsibilities and failure modes.

---

# ADR-011: Keep Vector Storage as the Persistent Source of Truth

## Context

The API needs access to ingested document chunks across requests and container restarts.

## Decision

Treat Qdrant as the persistent source of truth for indexed chunks.

Avoid keeping the document corpus primarily in application-level global variables.

## Rationale

Application containers should be disposable.

Persisting indexed data in Qdrant means the API can restart without losing the semantic-search index.

## Trade-offs

The application depends on Qdrant availability.

This is accepted because Qdrant is already a required part of the architecture.

---

# ADR-012: Persistent Docker Volume for Qdrant

## Context

Qdrant stores the vector index and metadata that the application needs between restarts.

## Decision

Use a Docker volume for Qdrant storage.

```text
qdrant_data
```

## Rationale

The volume decouples database data from the lifetime of the Qdrant container.

Restarting or recreating the application container does not require re-ingesting documents.

## Trade-offs

Persistent state means a clean development reset requires explicit volume removal.

The assessment's `terminate` operation intentionally removes volumes so that the evaluator can return the environment to a clean state.

---

# ADR-013: Synchronous Request/Response Ingestion

## Context

PDF ingestion involves several potentially expensive operations:

```text
PDF parsing

chunking

embedding generation

vector insertion
```

A production system at large scale might process ingestion asynchronously.

## Decision

Keep the `/ingest/` API synchronous for the assessment.

This means a request remains open until its document processing has completed.

## Alternatives Considered

- Celery
- Redis-backed jobs
- RabbitMQ/Kafka
- Background worker service

## Rationale

The assessment requires a simple API and does not specify very large documents or sustained high ingestion throughput.

Adding a job queue would introduce:

- another infrastructure service,
- job lifecycle management,
- retry semantics,
- additional operational complexity.

None is necessary to demonstrate the required core functionality at the expected scope.

A synchronous endpoint also keeps the response contract simple: a successful `200` response means ingestion has completed.

## Important Concurrency Note

Synchronous request/response processing does **not** mean that only one upload can run at a time.

The implementation keeps the ingestion operation synchronous from the client's perspective while allowing the application to handle concurrent requests through the web server's request execution model.

The trade-off here is therefore:

```text
synchronous request/response

        vs.

asynchronous job-based ingestion
```

rather than:

```text
synchronous

        =

one request at a time
```

## Trade-offs

A synchronous request occupies execution capacity while the document is being processed.

For larger workloads, the architecture could evolve toward:

```text
Upload

  ↓

Job queue

  ↓

Worker

  ↓

Embedding

  ↓

Qdrant
```

without changing the underlying extraction, chunking, embedding, or vector-storage services.

---

# ADR-014: Development Compose Override

## Context

Rebuilding the Docker image after every Python source-code modification slows development.

## Decision

Use a separate development Compose override with bind mounts and Uvicorn reload.

Development configuration:

```text
docker-compose.dev.yml
```

The application source and tests are mounted into the container.

## Rationale

This allows source changes to appear immediately inside the running container.

Ordinary Python changes therefore do not require an image rebuild.

## Trade-offs

Two Compose configurations must be maintained.

The development configuration is intentionally separate from the evaluator-facing environment so that the final submission remains reproducible and does not depend on local source mounts.

Dependency or Dockerfile changes still require an image rebuild.

---

# ADR-015: Docker Compose for Service Orchestration

## Context

The assessment requires the complete environment to run through Docker Compose and be controlled using:

```bash
./orchestrate.sh --action start
```

and:

```bash
./orchestrate.sh --action terminate
```

## Decision

Use Docker Compose for local service orchestration.

## Rationale

The application and Qdrant are separate containers with a simple dependency relationship.

Docker Compose provides:

- networking,
- container lifecycle management,
- volume management,
- environment configuration,
- reproducible local setup.

## Trade-offs

Docker Compose is designed for relatively small multi-container environments rather than full production cluster orchestration.

A larger deployment could use Kubernetes or another orchestration platform, but that would add complexity far beyond the requirements of this assessment.

---

# ADR-016: Explicit Qdrant Readiness Handling

## Context

A container being started does not necessarily mean the service inside it is ready to accept requests.

## Decision

The application waits for Qdrant connectivity before completing application startup.

## Rationale

Without readiness handling, the FastAPI application could start before Qdrant is available and fail during initialization.

Retrying the connection makes startup more robust and reduces timing-dependent failures.

## Trade-offs

Startup takes slightly longer when Qdrant is unavailable.

This is preferable to immediately failing or accepting requests while a required dependency is unavailable.

---

# ADR-017: Validate Embedding Dimensions

## Context

Qdrant collections require a fixed vector dimension.

The selected embedding model produces vectors of a specific size.

## Decision

Maintain the embedding dimension as configuration and validate generated vectors before storing them.

Current configuration:

```text
384 dimensions
```

## Rationale

A mismatch between the embedding model and Qdrant collection would result in failed inserts or incompatible indexes.

Explicit validation makes configuration errors visible early.

## Trade-offs

There is a small amount of additional validation logic, but this prevents difficult-to-diagnose vector-store failures.

---

# ADR-018: Separate API Logic from Processing Logic

## Context

The API endpoints should coordinate operations without becoming responsible for PDF parsing, chunking, embedding, and vector database implementation details.

## Decision

Keep domain processing in services and use the API layer as an interface/orchestration layer.

The ingestion endpoint follows:

```text
HTTP request

    ↓

Input validation

    ↓

Ingestion service

    ├── PDF extraction

    ├── chunking

    ├── embedding

    └── Qdrant storage

    ↓

HTTP response
```

The search endpoint follows:

```text
HTTP request

    ↓

Query validation

    ↓

Search service

    ├── query embedding

    └── Qdrant similarity search

    ↓

HTTP response
```

## Rationale

This makes the core processing logic reusable and easier to test without HTTP.

It also keeps endpoint implementations small and readable.

## Trade-offs

There is another abstraction layer between the endpoint and individual services.

The benefit is clearer separation of concerns and easier testing.

---

# ADR-019: Content-Based Document Identity

## Context

Repeated uploads need a stable document identity so that identical documents can produce the same deterministic chunk IDs.

Filenames cannot reliably serve as globally unique identifiers.

## Decision

Generate the document ID as the SHA-256 hash of the complete uploaded file bytes.

## Rationale

The document ID then represents document content rather than its filename.

For example:

```text
same PDF bytes

    ↓

same SHA-256

    ↓

same document_id
```

This remains true even if the same document is uploaded under a different filename.

## Trade-offs

Any change to the PDF bytes results in a different document ID.

Therefore, different document versions can coexist in the vector store rather than being silently treated as the same document.

This is intentional for the current assessment scope.

A production system requiring explicit document replacement or version management could maintain a separate document registry and lifecycle operations.

---

# ADR-020: Default Top-K Retrieval Size

## Context

The `/search/` endpoint needs to return relevant chunks, but the supplied API contract does not require a `top_k` request parameter.

## Decision

Return the top 5 results by default.

The value is configurable through:

```text
SEARCH_TOP_K
```

## Rationale

Five results provide enough context to demonstrate retrieval quality without returning unnecessarily large responses.

Keeping the parameter internal preserves the simple API contract supplied by the assessment.

## Trade-offs

A fixed default may not be optimal for every query or document collection.

A production system could expose `top_k` as a validated request parameter or use query-dependent retrieval strategies.

---

# ADR-021: No Initial Similarity Score Threshold

## Context

Semantic similarity scores are useful for ranking retrieved chunks, but the assessment does not specify a minimum relevance score.

## Decision

Return up to the configured top-K results without applying an initial score threshold.

## Rationale

Introducing a threshold would require choosing an arbitrary cutoff before observing retrieval behavior and evaluating representative queries.

Returning ranked results provides predictable behavior and allows retrieval quality to be evaluated directly.

For example, an unrelated query may still have a "nearest" passage even when its similarity is relatively low.

## Trade-offs

The result set may contain weakly relevant chunks when the query has little relationship to the indexed documents.

A production system could introduce a calibrated score threshold, reranking model, or relevance classifier after collecting evaluation data.

---

# ADR-022: Compatibility with the Supplied PDF Test Fixture

## Context

The supplied `suite.py` test creates a file named:

```text
sample.pdf
```

but writes plain-text content into it rather than generating a valid PDF document.

Strict PDF parsing therefore causes the supplied functional test to fail even though the fixture is intended to represent a PDF upload.

## Decision

Maintain normal PDF parsing through PyMuPDF, but provide a narrow fallback for readable UTF-8 text when PDF parsing fails.

Binary or unreadable content is still rejected.

## Rationale

This allows the implementation to remain compatible with the supplied functional test while preserving normal PDF processing for actual PDF files.

The fallback is deliberately limited to readable text rather than accepting arbitrary binary content.

## Trade-offs

A readable plain-text file with a `.pdf` filename can be accepted, which is less strict than validating the PDF binary format.

This is an assessment compatibility accommodation rather than the preferred production validation strategy.

With a corrected test fixture in a production environment, strict PDF validation would be preferable.

---

# ADR-023: Dependency Injection and Centralized Service Construction

## Context

The API depends on several services:

```text
IngestionService

SearchService

EmbeddingService

VectorStore
```

Constructing these services directly inside route functions or scattering their configuration across modules would make testing and configuration more difficult.

## Decision

Construct application services centrally and provide them to the API layer through dependencies.

The intended relationship is:

```text
FastAPI

  │

  ├── IngestionService

  │      ├── EmbeddingService

  │      └── VectorStore

  │

  └── SearchService

         ├── EmbeddingService

         └── VectorStore
```

## Rationale

Centralized construction provides:

- clearer ownership of configuration,
- easier substitution of fake services during tests,
- cleaner route modules,
- better isolation between production and test infrastructure,
- a straightforward path to future lifecycle management.

It also prevents tests from unintentionally reusing or modifying production-specific resources.

## Trade-offs

Dependency injection introduces an additional abstraction compared with directly instantiating classes inside the route modules.

For a very small application that might be unnecessary, but the project has enough separate responsibilities that the improved testability and separation are worthwhile.

---

# ADR-024: Mounted Directory Ingestion

## Context

The supplied Swagger documentation describes the `input` field as potentially representing:

- a single PDF,
- multiple PDFs,
- or a directory path containing PDFs.

The service itself runs inside a Docker container, so an arbitrary client-side host path cannot be assumed to exist inside the container.

## Decision

Support all three input forms through the API contract:

1. a single uploaded PDF,
2. multiple uploaded PDFs,
3. a directory path that is visible inside the container.

Directory ingestion is therefore limited to container-visible paths, such as the explicitly mounted `/data` directory used by the application.

The endpoint does **not** interpret a host filesystem path from the client's machine.

## Rationale

This preserves portability while supporting the directory form described by the supplied API contract.

The evaluator can mount a directory into the container and pass that container-visible path to the endpoint.

For the current project, `/data` is mounted by Docker Compose and can contain batches of PDFs.

This also keeps the HTTP boundary clear: client file uploads are handled as uploads, while directory ingestion operates only on filesystem paths that the container can actually access.

## Trade-offs

Directory ingestion depends on the relevant directory being mounted into the container.

An arbitrary path from the client's host remains unavailable to the container unless explicitly mounted.

The implementation currently treats a directory as a batch input, selects `.pdf` files from it, ignores non-PDF files, and processes the PDFs through the same ingestion service used by normal uploads.

---

# ADR-025: Application Logging and Observability

## Context

The application contains several operations whose execution time and failures are important for debugging and evaluation:

```text
document ingestion

semantic search

Qdrant operations

embedding generation
```

The system runs inside Docker, so operational information should be visible through container logs without introducing a separate observability platform.

## Decision

Use the Python standard-library `logging` module for application observability.

Application loggers use the `app` namespace and emit logs at `INFO` level to standard output.

The application logs:

```text
operation start

operation completion

operation duration

document filename

document ID

chunk count

search result count

validation and infrastructure failures
```

Unexpected failures use exception logging so that the traceback is available in application logs.

## Rationale

Standard Python logging is sufficient for the scope of the assessment and integrates naturally with Docker's stdout/stderr log collection.

Recording operation duration provides basic performance visibility without requiring a separate metrics system.

Logging metadata such as document IDs, filenames, chunk counts, and result counts makes failures and slow operations easier to diagnose.

Document contents and full search queries are intentionally not logged.

This reduces the risk of placing potentially sensitive application data into operational logs.

## Trade-offs

The current approach provides basic operational visibility but does not provide centralized metrics, distributed tracing, dashboards, or long-term log storage.

A production deployment at larger scale could introduce systems such as:

```text
OpenTelemetry

Prometheus

centralized log aggregation

distributed tracing
```

Those systems are intentionally outside the scope of the current assessment.

---

# ADR-026: Error Classification and API Failure Handling

## Context

The application can encounter several fundamentally different categories of failure:

```text
invalid client input

document-processing failures

embedding/model failures

vector-database failures

unexpected application failures
```

These failures should not all produce the same HTTP status or expose internal implementation details.

## Decision

Classify errors according to whether they represent invalid client input or an internal server failure.

Client/input errors return HTTP `400`.

These include:

```text
empty uploads

invalid file types

invalid/corrupt PDFs

textless documents

empty search queries

missing or invalid directory paths
```

Internal failures return HTTP `500`.

These include:

```text
embedding/model failures

Qdrant failures

unexpected application exceptions
```

API responses use the required error format:

```json
{
  "error": "..."
}
```

Internal exception details are not exposed directly to API clients.

Known exceptions are preserved between service layers so that the API layer can make the appropriate classification.

For example:

```text
PDFProcessingError

        ↓

    HTTP 400

EmbeddingError

        ↓

    HTTP 500

VectorStoreError

        ↓

    HTTP 500
```

Unexpected exceptions are wrapped by the relevant service with a generic internal error while preserving the original exception as the cause for diagnostic purposes.

## Rationale

Separating client errors from server errors makes the API contract predictable and prevents infrastructure failures from being incorrectly reported as client mistakes.

Keeping the classification at the API boundary also allows the processing services to remain independent of HTTP concerns.

## Trade-offs

The current classification intentionally uses broad `400` and `500` categories rather than defining a large hierarchy of HTTP-specific errors.

This keeps the implementation simple and appropriate for the assessment while leaving room for more granular error codes in a production API.

The API currently stops processing a multi-file request when it encounters an ingestion failure. Files processed before the failure may already have been stored, so multi-file ingestion is not treated as an atomic transaction.

A production system could introduce per-file result reporting, transactional coordination, or asynchronous job management depending on the required semantics.

---

# ADR-027: Bounded Embedding Batch Size

## Context

FastEmbed can process multiple texts in batches during document embedding.

Using a very large batch can significantly increase memory usage, particularly when ingesting multiple or large PDFs inside a resource-limited Docker container.

The project initially experienced substantial memory growth during multi-document ingestion.

## Decision

Process document chunks using a bounded embedding batch size of:

```text
EMBEDDING_BATCH_SIZE=32
```

The value is configurable through application configuration.

## Rationale

A bounded batch limits the amount of text and intermediate embedding data held by the embedding runtime at once.

This substantially reduces peak memory usage while preserving the existing embedding model and overall synchronous ingestion design.

The choice is therefore a practical runtime trade-off rather than an attempt to maximize raw embedding throughput.

## Trade-offs

Smaller batches can require more embedding calls and may increase total processing time compared with a larger batch.

The selected value provides a practical balance for the containerized assessment environment.

A larger deployment could benchmark batch size against available CPU and memory and tune it accordingly.

---

# ADR-028: Cleanly Isolated Retrieval Evaluation

## Context

The project includes a small retrieval benchmark in addition to the functional test suite.

Qdrant is persistent, so evaluation data can interfere with other documents already stored in the collection.

This can make retrieval metrics difficult to interpret if the benchmark runs against a collection containing unrelated application data.

## Decision

Run retrieval evaluation against a clean Qdrant collection/state.

The evaluation script:

- creates the benchmark documents,
- ingests them through the API,
- executes the benchmark queries through the API,
- reports Hit@k, Precision@k, and Recall@k.

The evaluation does not produce an additional results artifact as part of the assessment workflow.

## Rationale

Keeping evaluation isolated makes the benchmark reproducible and prevents unrelated documents from changing retrieval results.

Using the actual HTTP API also exercises the same ingestion and search paths that the evaluator uses.

The benchmark remains intentionally lightweight and focused on retrieval behavior rather than becoming a separate production analytics subsystem.

## Trade-offs

A clean evaluation state requires resetting Qdrant data before the benchmark.

The current benchmark is primarily a development/evaluation aid rather than a comprehensive retrieval-quality framework.

---

# ADR-029: Test Isolation and Coverage Strategy

## Context

The application contains several external dependencies and failure paths:

```text
Qdrant

embedding model

PDF parsing

multipart form parsing
```

Tests should verify application behavior without requiring every test to operate against shared persistent production-like state.

The assessment also supplies a functional `suite.py` test that must continue to pass.

## Decision

Use a layered test strategy:

- unit/service tests for individual components,
- API tests using injected/fake services where appropriate,
- integration tests for real Qdrant interactions,
- the supplied `suite.py` functional test,
- a separate retrieval evaluation script.

Test Qdrant collections are isolated from normal application collections when integration tests need a real vector store.

## Rationale

This keeps the test suite fast while still exercising important infrastructure boundaries.

The resulting suite verifies the main input modes, validation failures, service failures, concurrency behavior, and the supplied evaluator contract.

At the current implementation point, the project test suite contains 62 passing tests, and the supplied `suite.py` contains 2 passing tests.

## Trade-offs

Some integration tests are slower and more infrastructure-dependent than pure unit tests.

Maintaining several test layers adds some organization overhead, but it avoids turning every test into a full-stack Docker/Qdrant exercise.

---

# Decision Summary

The resulting architecture deliberately favors:

```text
Simple

    +

Explicit

    +

Containerized

    +

Testable

    +

Observable

    +

Easy to explain
```

over maximum scalability or infrastructure complexity.

The major data flow is:

```text
                         ┌──────────────────┐
                         │     FastAPI      │
                         └────────┬─────────┘
                                  │
                     ┌────────────┴────────────┐
                     │                         │
                  /ingest/                  /search/
                     │                         │
                     ▼                         ▼
             IngestionService             SearchService
                     │                         │
              ┌──────┼──────┐                  │
              ▼      ▼      ▼                  ▼
             PDF   Chunk   Embed          Query Embed
              │      │      │                  │
              └──────┴──────┘                  │
                     │                         │
                     └──────────┬──────────────┘
                                ▼
                          ┌──────────┐
                          │  Qdrant  │
                          │          │
                          │ Vectors  │
                          │ Payload  │
                          └──────────┘
```

The `/ingest/` interface currently supports:

```text
single PDF upload
        │
        ├── multiple PDF uploads
        │
        └── mounted directory path
```

with directory ingestion restricted to paths visible inside the container.

Each major component has a clearly defined responsibility and can be replaced independently as requirements evolve.

The architecture intentionally avoids introducing additional infrastructure unless it solves a concrete problem within the scope of the assessment.

The main design principle is:

> **Choose the simplest architecture that satisfies the current requirements reliably, while keeping the system structured enough to evolve when requirements or scale change.**
