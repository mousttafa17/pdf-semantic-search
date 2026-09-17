# Architecture Decisions

## PDF Ingestor & Semantic Search API

This document records the main architectural decisions made while implementing the PDF Ingestor & Semantic Search API.

The goal is not to maximize architectural complexity. Each decision is based on the requirements of the assessment, expected workload, simplicity, reliability, maintainability, and ease of operation.

---

# ADR-001: FastAPI for the API Layer

## Context

The system requires two HTTP endpoints:

* `POST /ingest/`
* `POST /search/`

The API also needs request validation, structured responses, and OpenAPI/Swagger documentation.

## Decision

Use **FastAPI** as the API framework.

## Alternatives Considered

* Flask
* Django REST Framework

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

* PostgreSQL + pgvector
* Another hosted vector database
* In-memory vector storage

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

* Sentence Transformers + PyTorch
* Larger embedding models
* Hosted embedding APIs

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

* Dot product
* Euclidean distance

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

* Token-based chunking
* Paragraph-based chunking
* Sentence-aware chunking
* Semantic chunking

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

* increases embedding computation,
* increases storage requirements,
* can introduce some duplicated text in retrieval results.

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

* Celery
* Redis-backed jobs
* RabbitMQ/Kafka
* Background worker service

## Rationale

The assessment requires a simple API and does not specify very large documents or sustained high ingestion throughput.

Adding a job queue would introduce:

* another infrastructure service,
* job lifecycle management,
* retry semantics,
* additional operational complexity.

None is necessary to demonstrate the required core functionality at the expected scope.

A synchronous endpoint also keeps the response contract simple: a successful `200` response means ingestion has completed.

## Important Concurrency Note

Synchronous request/response processing does **not** mean that only one upload can run at a time.

FastAPI can execute synchronous endpoint functions using its worker threads, allowing multiple HTTP requests to be processed concurrently.

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

A synchronous request occupies a worker while the document is being processed.

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

* networking,
* container lifecycle management,
* volume management,
* environment configuration,
* reproducible local setup.

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

* clearer ownership of configuration,
* easier substitution of fake services during tests,
* cleaner route modules,
* better isolation between production and test infrastructure,
* a straightforward path to future lifecycle management.

It also prevents tests from unintentionally reusing or modifying production-specific resources.

## Trade-offs

Dependency injection introduces an additional abstraction compared with directly instantiating classes inside the route modules.

For a very small application that might be unnecessary, but the project has enough separate responsibilities that the improved testability and separation are worthwhile.

---

# ADR-024: No Directory-Path Ingestion

## Context

The supplied Swagger documentation describes the `input` field as potentially representing:

* a single PDF,
* multiple PDFs,
* or a directory path containing PDFs.

The service itself runs inside a Docker container.

## Decision

Support multipart file uploads for one or multiple PDF files, but do not interpret an arbitrary client-supplied directory path as a host filesystem location.

## Rationale

A host filesystem directory is not naturally available inside a container unless it is explicitly mounted.

Adding arbitrary host-path semantics would couple the HTTP API to the evaluator's local filesystem and require additional volume-mount behavior.

Multipart uploads provide a portable HTTP interface and directly match the normal client/server boundary.

The assessment's provided functional test also exercises file upload rather than directory ingestion.

## Trade-offs

Directory-based batch ingestion is not supported through the HTTP endpoint.

If directory ingestion became a concrete requirement, a separate mounted-data mechanism or a dedicated batch-ingestion interface could be introduced without changing the underlying extraction, chunking, embedding, or vector-storage services.

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
              ┌──────┼──────┐                 │
              ▼      ▼      ▼                 ▼
             PDF   Chunk   Embed         Query Embed
              │      │      │                 │
              └──────┴──────┘                 │
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

Each major component has a clearly defined responsibility and can be replaced independently as requirements evolve.

The architecture intentionally avoids introducing additional infrastructure unless it solves a concrete problem within the scope of the assessment.

The main design principle is:

> **Choose the simplest architecture that satisfies the current requirements reliably, while keeping the system structured enough to evolve when requirements or scale change.**
