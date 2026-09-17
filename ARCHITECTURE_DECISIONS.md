# Architecture Decisions

## PDF Ingestor & Semantic Search API

This document records the main architectural decisions made while implementing the PDF Ingestor & Semantic Search API.

The goal is not to maximize architectural complexity. Each decision is based on the requirements of the assessment, expected workload, simplicity, reliability, and ease of operation.

---

## ADR-001: FastAPI for the API Layer

### Context

The system requires two HTTP endpoints:

* `POST /ingest/`
* `POST /search/`

The API also needs request validation, structured responses, and OpenAPI/Swagger documentation.

### Decision

Use **FastAPI** as the API framework.

### Alternatives Considered

* Flask
* Django REST Framework

### Rationale

FastAPI provides request validation through Pydantic, automatic OpenAPI documentation, straightforward file-upload handling, and good support for asynchronous API workloads.

It also keeps the implementation relatively small, which fits the scope of this assessment.

### Trade-offs

FastAPI introduces an additional framework abstraction compared with a minimal Python HTTP server. Flask could also satisfy the requirements and has a simpler conceptual model, but FastAPI provides API-specific features that are directly useful here.

---

# ADR-002: Qdrant for Vector Storage

### Context

The assessment requires embeddings and metadata to be stored in a vector database and searched using semantic similarity.

### Decision

Use **Qdrant** as the vector database.

### Alternatives Considered

* PostgreSQL + pgvector
* Another hosted vector database
* In-memory vector storage

### Rationale

Qdrant is purpose-built for vector search, supports payload metadata, provides a Python client, and runs cleanly as a Docker Compose service.

Using a dedicated vector database keeps similarity-search functionality explicit and avoids implementing nearest-neighbor search ourselves.

### Trade-offs

Using Qdrant introduces a separate infrastructure service whereas PostgreSQL + pgvector could combine relational and vector storage in one database.

For this assessment, the separate service is acceptable because the primary data-access pattern is vector retrieval rather than relational querying.

---

# ADR-003: FastEmbed for Embedding Generation

### Context

The system needs to generate embeddings for document chunks and search queries.

The embedding runtime must be practical inside a container and should not introduce unnecessary resource requirements for a small assessment project.

### Decision

Use **Qdrant FastEmbed** for embedding generation.

### Model

```text
BAAI/bge-small-en-v1.5
```

### Alternatives Considered

* Sentence Transformers + PyTorch
* Larger embedding models
* Hosted embedding APIs

### Rationale

FastEmbed provides a lightweight local embedding runtime based on ONNX Runtime and avoids introducing the full PyTorch stack.

`BAAI/bge-small-en-v1.5` provides 384-dimensional embeddings and is intended for retrieval-oriented embedding use.

Running the model locally also avoids external API credentials, network calls during normal inference, and usage-based API costs.

### Trade-offs

A smaller embedding model may provide lower retrieval quality than a larger model.

The decision prioritizes practical CPU inference, simple deployment, and a small container footprint because the assessment emphasizes engineering quality rather than maximum retrieval benchmark performance.

---

# ADR-004: Query and Passage Embedding Prefixes

### Context

The selected BGE embedding model is used for retrieval between search queries and document passages.

### Decision

Prefix document chunks with:

```text
passage:
```

and user queries with:

```text
query:
```

before generating embeddings.

### Rationale

The model's retrieval configuration distinguishes between the query and the passage being retrieved.

This makes the implementation explicitly aligned with the model's intended information-retrieval usage rather than treating queries and documents as identical embedding inputs.

### Trade-offs

The embedding service becomes somewhat model-specific.

If the project switches to a different embedding model, the prefixing strategy may need to change or be removed.

---

# ADR-005: Cosine Similarity

### Context

The vector database needs a similarity metric for comparing query embeddings with stored document embeddings.

### Decision

Use **cosine similarity** in Qdrant.

### Alternatives Considered

* Dot product
* Euclidean distance

### Rationale

Cosine similarity is intuitive for semantic text retrieval because it measures the similarity in vector direction rather than magnitude.

It is also compatible with the selected embedding model and makes the retrieval configuration easy to explain.

### Trade-offs

For normalized vectors, cosine similarity and dot product produce equivalent rankings.

Dot product can be advantageous for implementation efficiency, but the difference is not important for the expected scale of this assessment.

Cosine similarity is therefore preferred for clarity.

---

# ADR-006: Character-Based Text Chunking

### Context

Long PDF documents must be divided into smaller units before embedding.

### Decision

Use a simple fixed-size character-based chunking strategy with overlap.

Initial configuration:

```text
chunk_size:    1000 characters
chunk_overlap: 200 characters
```

### Alternatives Considered

* Token-based chunking
* Paragraph-based chunking
* Sentence-aware chunking
* Semantic chunking

### Rationale

Character-based chunking is deterministic, easy to implement, easy to test, and does not require an additional tokenizer dependency.

The assessment explicitly prioritizes thoughtful engineering over heavy research or optimization, making a simple and understandable strategy appropriate.

### Trade-offs

Character boundaries do not always correspond to semantic or linguistic boundaries.

A token-aware or semantic chunker could produce better retrieval units, but would add complexity.

The current strategy can later be replaced without changing the rest of the ingestion architecture because chunking is isolated behind its own service.

---

# ADR-007: Chunk Overlap

### Context

Splitting text into independent chunks can separate related information across chunk boundaries.

### Decision

Use a fixed overlap between consecutive chunks.

Initial overlap:

```text
200 characters
```

### Rationale

Overlap preserves some context between neighboring chunks and reduces the chance that information spanning a boundary becomes difficult to retrieve.

### Trade-offs

Overlap increases the number of chunks and therefore:

* increases embedding computation,
* increases storage requirements,
* can introduce some duplicated text in retrieval results.

The chosen amount is intentionally modest for the expected document sizes.

---

# ADR-008: One Qdrant Point per Document Chunk

### Context

The system needs to associate each embedding with the original document and text from which it was generated.

### Decision

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

### Rationale

One point per chunk provides a natural retrieval unit.

When a query is executed, Qdrant returns the points whose vectors are most similar to the query vector. Their payloads then provide the document name, chunk position, and original text needed for the API response.

### Trade-offs

A document with many chunks produces many stored vectors.

That increases storage and search workload, but provides much more precise retrieval than representing an entire PDF with one vector.

---

# ADR-009: Deterministic UUIDs for Chunk IDs

### Context

The same document may be ingested more than once.

Random point IDs would cause every ingestion to create additional points even when the content represents the same document and chunk.

### Decision

Generate a deterministic UUID from:

```text
document_id + chunk_index
```

### Rationale

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

### Trade-offs

Deterministic IDs make repeated ingestion easier to handle, but they require a stable document ID.

They also create a separate consideration when replacing documents: if a newer version has fewer chunks, obsolete points must be explicitly removed rather than simply upserting the remaining chunks.

---

# ADR-010: Separate Application Responsibilities into Services

### Context

The ingestion pipeline contains several independent operations:

```text
PDF extraction
chunking
embedding
vector storage
```

### Decision

Implement these responsibilities as separate services/modules.

Current structure:

```text
services/
├── pdf.py
├── chunking.py
├── embeddings.py
└── vector_store.py
```

### Rationale

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

### Trade-offs

The architecture contains more files and abstractions than a single large ingestion function.

The additional structure is justified because each component has different responsibilities and failure modes.

---

# ADR-011: Keep Vector Storage as the Persistent Source of Truth

### Context

The API needs access to ingested document chunks across requests and container restarts.

### Decision

Treat Qdrant as the persistent source of truth for indexed chunks.

Avoid keeping the document corpus primarily in application-level global variables.

### Rationale

Application containers should be disposable.

Persisting indexed data in Qdrant means the API can restart without losing the semantic-search index.

### Trade-offs

The application depends on Qdrant availability.

This is accepted because Qdrant is already a required part of the architecture.

---

# ADR-012: Persistent Docker Volume for Qdrant

### Context

Qdrant stores the vector index and metadata that the application needs between restarts.

### Decision

Use a Docker volume for Qdrant storage.

```text
qdrant_data
```

### Rationale

The volume decouples database data from the lifetime of the Qdrant container.

Restarting or recreating the application container does not require re-ingesting documents.

### Trade-offs

Persistent state means a clean development reset requires explicit volume removal.

The assessment's `terminate` operation intentionally removes volumes so that the evaluator can return the environment to a clean state.

---

# ADR-013: Synchronous Ingestion for the Assessment Scope

### Context

PDF ingestion involves several potentially expensive operations:

```text
PDF parsing
chunking
embedding generation
vector insertion
```

A production system at large scale might process these asynchronously.

### Decision

Keep ingestion synchronous for the assessment.

### Alternatives Considered

* Celery
* Redis-backed jobs
* RabbitMQ/Kafka
* Background worker service

### Rationale

The assessment requires a simple API and does not specify very large documents or sustained high ingestion throughput.

Adding a queue would introduce:

* another infrastructure service,
* job lifecycle management,
* retry semantics,
* additional operational complexity.

None is necessary to demonstrate the required core functionality at the expected scope.

### Trade-offs

A synchronous request occupies a request worker while the document is being processed.

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

### Context

Rebuilding the Docker image after every Python source-code modification slows development.

### Decision

Use a separate development Compose override with bind mounts and Uvicorn reload.

Development configuration:

```text
docker-compose.dev.yml
```

The application source and tests are mounted into the container.

### Rationale

This allows source changes to appear immediately inside the running container.

Ordinary Python changes therefore do not require an image rebuild.

### Trade-offs

Two Compose configurations must be maintained.

The development configuration is intentionally separate from the evaluator-facing environment so that the final submission remains reproducible and does not depend on local source mounts.

---

# ADR-015: Docker Compose for Service Orchestration

### Context

The assessment requires the complete environment to run through Docker Compose and be controlled using:

```bash
./orchestrate.sh --action start
```

and:

```bash
./orchestrate.sh --action terminate
```

### Decision

Use Docker Compose for local service orchestration.

### Rationale

The application and Qdrant are separate containers with a simple dependency relationship.

Docker Compose provides:

* networking,
* container lifecycle management,
* volume management,
* environment configuration,
* reproducible local setup.

### Trade-offs

Docker Compose is designed for relatively small multi-container environments rather than full production cluster orchestration.

A larger deployment could use Kubernetes or another orchestration platform, but that would add complexity far beyond the requirements of this assessment.

---

# ADR-016: Explicit Qdrant Readiness Handling

### Context

A container being started does not necessarily mean the service inside it is ready to accept requests.

### Decision

The application waits for Qdrant connectivity before completing application startup.

### Rationale

Without readiness handling, the FastAPI application could start before Qdrant is available and fail during initialization.

Retrying the connection makes startup more robust and reduces timing-dependent failures.

### Trade-offs

Startup takes slightly longer when Qdrant is unavailable.

This is preferable to immediately failing or accepting requests while a required dependency is unavailable.

---

# ADR-017: Validate Embedding Dimensions

### Context

Qdrant collections require a fixed vector dimension.

The selected model produces vectors of a specific size.

### Decision

Maintain the embedding dimension as configuration and validate generated vectors before storing them.

Current configuration:

```text
384 dimensions
```

### Rationale

A mismatch between the embedding model and Qdrant collection would result in failed inserts or incompatible indexes.

Explicit validation makes configuration errors visible early.

### Trade-offs

There is a small amount of additional validation logic, but this prevents difficult-to-diagnose vector-store failures.

---

# ADR-018: Separate API Logic from Processing Logic

### Context

The API endpoints should coordinate operations without becoming responsible for PDF parsing, chunking, embedding, and vector database implementation details.

### Decision

Keep domain processing in services and use the API layer as an orchestration/interface layer.

The intended ingestion endpoint flow is:

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

### Rationale

This makes the core processing logic reusable and easier to test without HTTP.

It also keeps endpoint implementations small and readable.

### Trade-offs

There is another abstraction layer between the endpoint and individual services.

The benefit is clearer separation of concerns and easier testing.

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

The major design flow is:

```text
                    ┌──────────────────┐
                    │     FastAPI      │
                    └────────┬─────────┘
                             │
                 ┌───────────┴───────────┐
                 │                       │
              /ingest/                /search/
                 │                       │
                 ▼                       ▼
          PDF Extraction          Query Embedding
                 │                       │
                 ▼                       │
             Chunking                    │
                 │                       │
                 ▼                       │
          Document Embedding             │
                 │                       │
                 └──────────┬────────────┘
                            ▼
                      ┌──────────┐
                      │  Qdrant  │
                      │          │
                      │ Vectors  │
                      │ Payload  │
                      └──────────┘
```

Each component can be replaced independently as requirements evolve.

The key principle is that architectural complexity should be introduced only when it solves a concrete problem.
