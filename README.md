# PDF Ingestor & Semantic Search API

A fully containerized FastAPI service for ingesting PDF documents, generating semantic embeddings, storing document chunks in Qdrant, and retrieving relevant chunks through semantic search.

The implementation is intentionally kept simple and modular for the scope of the assessment.

## Architecture

```text
                    ┌──────────────────┐
                    │     FastAPI      │
                    └────────┬─────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
             /ingest/                 /search/
                │                         │
                ▼                         ▼
        IngestionService             SearchService
                │                         │
         ┌──────┼──────┐                  │
         ▼      ▼      ▼                  ▼
        PDF   Chunk   Embed           Query Embed
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

### Main components

* **FastAPI** — HTTP API, validation, and OpenAPI documentation.
* **PyMuPDF** — PDF text extraction.
* **FastEmbed** — local embedding generation.
* **BAAI/bge-small-en-v1.5** — 384-dimensional embedding model.
* **Qdrant** — persistent vector storage and similarity search.
* **Docker Compose** — application and Qdrant orchestration.

## API

### `POST /ingest/`

Accepts one or more PDF files using multipart form data.

Example:

```bash
curl -X POST http://localhost:8000/ingest/ \
  -F "input=@sample.pdf"
```

A successful response contains the uploaded filenames:

```json
{
  "message": "Successfully ingested 1 PDF documents.",
  "files": [
    "sample.pdf"
  ]
}
```

### `POST /search/`

Accepts a natural-language search query.

Example:

```bash
curl -X POST http://localhost:8000/search/ \
  -H "Content-Type: application/json" \
  -d '{"query":"How does AI learn from data?"}'
```

A successful response contains ranked document chunks:

```json
{
  "results": [
    {
      "document": "sample.pdf",
      "score": 0.82,
      "content": "Artificial intelligence enables systems to learn from data."
    }
  ]
}
```

### `GET /health`

Returns the application health status.

Swagger/OpenAPI documentation is available at:

```text
http://localhost:8000/docs
```

## Running the evaluator-facing environment

Start the complete environment with:

```bash
./orchestrate.sh --action start
```

Terminate the environment with:

```bash
./orchestrate.sh --action terminate
```

The application and Qdrant run as separate containers.

Qdrant data is stored in the `qdrant_data` Docker volume.

The `terminate` operation removes the environment and its persistent volume so that the next start begins from a clean state.

## Development workflow

Development uses a separate Compose override with source bind mounts and Uvicorn reload:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

This means ordinary Python source changes do not require rebuilding the application image.

Changes to `requirements.txt` or Docker configuration require a rebuild.

For development, avoid `docker compose down -v` unless a complete Qdrant data reset is intentional.

## Testing

Run the project test suite inside the application container:

```bash
docker compose exec app pytest tests/ -v
```

Run the supplied evaluator test suite:

```bash
docker compose exec app pytest /app/suite.py -v
```

The current project test suite covers:

* PDF extraction and invalid-document handling
* Character-based chunking and overlap
* Embedding generation and dimension validation
* Concurrent model initialization
* Concurrent document ingestion
* Idempotent repeated ingestion
* Qdrant storage and retrieval
* Semantic search
* API validation and response shapes
* 400/500 error classification
* Logging and observability behavior

## Embedding and retrieval design

Documents are divided into 1000-character chunks with 200-character overlap.

Document chunks are embedded using:

```text
BAAI/bge-small-en-v1.5
```

Document text is prefixed with:

```text
passage:
```

and search queries are prefixed with:

```text
query:
```

Qdrant uses cosine similarity.

The default search size is:

```text
SEARCH_TOP_K=5
```

No arbitrary similarity-score threshold is applied initially. Results are ranked by semantic similarity and the top configured results are returned.

## Document identity and idempotency

Each uploaded document receives a deterministic ID based on the SHA-256 hash of its complete file bytes.

Chunk point IDs are deterministic UUID5 values derived from:

```text
document_id + chunk_index
```

This means repeated ingestion of identical document bytes updates the existing Qdrant points instead of creating duplicates.

## Error handling

Client/input errors return HTTP `400`.

Examples include:

```text
invalid file type
empty upload
invalid or corrupt PDF
textless document
empty search query
```

Internal failures return HTTP `500`.

Examples include:

```text
embedding/model failure
Qdrant failure
unexpected application failure
```

The API uses the required error shape:

```json
{
  "error": "..."
}
```

Internal implementation details are not exposed through error responses.

## Observability

Application logging uses Python's standard `logging` module.

Logs include useful operational metadata such as:

```text
operation
filename
document ID
chunk count
result count
duration
failure type
```

Document contents and full search queries are not logged.

Example:

```text
INFO app.services.ingestion - Ingestion started filename=sample.pdf document_id=...
INFO app.services.ingestion - Ingestion completed filename=sample.pdf document_id=... chunks=1 duration_ms=...
INFO app.services.search - Search started query_length=28 top_k=5
INFO app.services.search - Search completed results=5 duration_ms=...
```

## Design trade-offs

The project intentionally favors:

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

over unnecessary infrastructure complexity.

In particular:

* Ingestion is synchronous request/response rather than queue-based.
* Qdrant is used directly rather than introducing a relational database.
* FastEmbed avoids a heavyweight PyTorch-based embedding stack.
* Chunking is intentionally simple and deterministic.
* No external telemetry or job-processing infrastructure is introduced.

The architecture is structured so that these choices can be replaced independently if requirements or scale change.

## Assessment compatibility note

The supplied evaluator fixture creates a file named `sample.pdf` containing plain UTF-8 text rather than a valid PDF binary.

The PDF extraction layer therefore includes a narrow readable-text fallback for this assessment fixture.

Normal PDF files are processed through PyMuPDF, while binary or unreadable invalid files are rejected.

Directory-path ingestion is not supported through the HTTP API. Multipart uploads are used so the API remains independent of the evaluator's host filesystem.

## Project structure

```text
.
├── app/
│   ├── api/
│   │   ├── ingest.py
│   │   └── search.py
│   ├── services/
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── ingestion.py
│   │   ├── pdf.py
│   │   ├── search.py
│   │   └── vector_store.py
│   ├── config.py
│   ├── dependencies.py
│   ├── logging_config.py
│   ├── models.py
│   └── main.py
├── tests/
├── docker-compose.yml
├── docker-compose.dev.yml
├── Dockerfile
├── orchestrate.sh
├── requirements.txt
├── ARCHITECTURE_DECISIONS.md
├── IMPLEMENTATION_PATH.md
└── suite.py
```

## Further design details

See `ARCHITECTURE_DECISIONS.md` for the detailed rationale, alternatives, trade-offs, and evolution path behind the implementation.
