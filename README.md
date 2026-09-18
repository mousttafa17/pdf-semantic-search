# PDF Ingestor & Semantic Search API

A fully containerized FastAPI service for ingesting PDF documents, generating semantic embeddings, storing document chunks in Qdrant, and retrieving relevant chunks through semantic search.

The implementation is intentionally kept simple and modular for the scope of the assessment.

## Quick Setup

The project is fully containerized. The evaluator only needs Docker with Docker Compose; Python, `pytest`, Qdrant, and the application dependencies do not need to be installed on the host machine.

### Prerequisites

* Git
* Docker Desktop, or Docker Engine with Docker Compose
* A running Docker daemon

### 1. Clone the repository

```bash
git clone <repository-url>

cd pdf-semantic-search
```

### 2. Start the evaluator-facing environment

Run:

```bash
./orchestrate.sh --action start
```

This builds the application image and starts:

* **FastAPI** at `http://localhost:8000`
* **Qdrant** at `http://localhost:6333`

The application image contains the configured embedding model:

```text
BAAI/bge-small-en-v1.5
```

The model is downloaded during the Docker image build so that the first ingestion request does not need to download the model.

No Hugging Face token is required for normal evaluation.

### 3. Verify the application

Check the health endpoint:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "qdrant": "connected"
}
```

The interactive Swagger/OpenAPI documentation is available at:

```text
http://localhost:8000/docs
```

### 4. Run the project test suite

The project tests are included in the application image, so no host-side Python or `pytest` installation is required.

Run:

```bash
docker compose exec app pytest tests/ -v
```

This executes the developer-authored unit, integration, and edge-case tests.

### 5. Run the supplied evaluator suite

The supplied `suite.py` is kept unchanged and mounted read-only into the application container.

Run:

```bash
docker compose exec app pytest /app/suite.py -v
```

This executes the evaluator-provided tests using the same containerized runtime as the application.

### 6. Stop and clean up

To stop the application and Qdrant and remove the project environment:

```bash
./orchestrate.sh --action terminate
```

The `terminate` operation removes the containers, project network, and Qdrant persistent volume so that the next start begins from a clean state.

> **Note:** Because the Qdrant volume is removed by `terminate`, stored vectors will be deleted. Use normal container restarts when persistence should be preserved.

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

The `input` field supports three modes:

1. A single PDF file.
2. Multiple PDF files by repeating the `input` field.
3. A directory path containing PDF files visible inside the application container.

#### Single PDF

```bash
curl -X POST http://localhost:8000/ingest/ \
  -F "input=@sample.pdf"
```

#### Multiple PDFs

```bash
curl -X POST http://localhost:8000/ingest/ \
  -F "input=@sample1.pdf" \
  -F "input=@sample2.pdf"
```

#### Directory path

The application exposes the repository's `data/` directory inside the container as `/data`.

For example:

```text
data/
└── pdfs/
    ├── document1.pdf
    ├── document2.pdf
    └── document3.pdf
```

The directory can then be ingested with:

```bash
curl -X POST http://localhost:8000/ingest/ \
  -F "input=/data/pdfs"
```

Only PDF files in the specified directory are processed. Non-PDF files are ignored.

A request must use either uploaded files or a directory path; mixing the two input modes is rejected.

A successful response contains the ingested filenames:

```json
{
  "message": "Successfully ingested 2 PDF documents.",
  "files": [
    "sample1.pdf",
    "sample2.pdf"
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

Returns the application health status and Qdrant connectivity.

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

For development, avoid:

```bash
docker compose down -v
```

unless a complete Qdrant data reset is intentional.

## Testing

Testing is performed at multiple levels.

### Project test suite

Run the developer-authored tests inside the application container:

```bash
docker compose exec app pytest tests/ -v
```

The project test suite covers:

* PDF extraction and invalid-document handling
* Character-based chunking and overlap
* Embedding generation and dimension validation
* Concurrent model initialization
* Concurrent document ingestion
* Idempotent repeated ingestion
* Qdrant storage and retrieval
* Semantic search
* API validation and response shapes
* Single and multiple PDF ingestion
* Directory ingestion
* Directory filtering for non-PDF files
* Invalid directory handling
* Rejection of mixed input modes
* 400/500 error classification
* Logging and observability behavior

### Supplied evaluator suite

Run the supplied `suite.py` unchanged inside the application container:

```bash
docker compose exec app pytest /app/suite.py -v
```

The evaluator-facing suite verifies the core start → ingest → search workflow.

The supplied `suite.py` is not copied into the Docker image by the Dockerfile. It is mounted read-only by Docker Compose so the exact evaluator-provided file in the repository is used.

### Retrieval evaluation

The project also includes a small manually labeled query/relevance dataset for evaluating retrieval quality.

The evaluation dataset is stored in:

```text
evaluation/dataset.json
```

and can be evaluated with:

```bash
docker compose exec app python evaluation/evaluate.py
```

The evaluator:

1. Generates temporary PDFs from the benchmark corpus.
2. Ingests them through the real `/ingest/` endpoint.
3. Runs the labeled queries through the real `/search/` endpoint.
4. Compares retrieved documents against the manually defined relevant documents.
5. Reports Hit@k, Precision@k, and Recall@k for `k = 1, 3, 5`.

The relevance labels are defined independently of similarity scores; similarity is used for ranking, while the dataset provides the ground-truth relevance judgments.

The evaluation script prints both per-query retrieval results and aggregate metrics. It does not modify the production API or introduce an evaluation-only endpoint.

The evaluation benchmark should be run against a clean Qdrant collection so that documents from other runs do not affect the retrieval results.

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

Embeddings are generated in bounded batches to keep memory usage predictable during local inference:

```text
EMBEDDING_BATCH_SIZE=32
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
invalid directory path
directory containing no PDFs
mixed file and directory input
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

* Ingestion remains synchronous request/response rather than queue-based.
* Blocking ingestion work is kept out of the async event loop while the client still waits for the completed response.
* Qdrant is used directly rather than introducing a relational database.
* FastEmbed avoids a heavyweight PyTorch-based embedding stack.
* Embedding inference uses a bounded batch size to control memory usage.
* Chunking is intentionally simple and deterministic.
* No external telemetry or job-processing infrastructure is introduced.

The architecture is structured so that these choices can be replaced independently if requirements or scale change.

## Assessment compatibility note

The supplied evaluator fixture creates a file named `sample.pdf` containing plain UTF-8 text rather than a valid PDF binary.

The PDF extraction layer therefore includes a narrow readable-text fallback for this assessment fixture.

Normal PDF files are processed through PyMuPDF, while binary or unreadable invalid files are rejected.

The `/ingest/` endpoint supports the three input forms described by the supplied API contract:

* a single PDF upload,
* multiple PDF uploads using repeated `input` fields,
* a directory path containing PDFs visible inside the application container.

Directory ingestion is backed by the `/data` container mount used for the repository's `data/` directory.

## Project structure

```text
.

├── app/
│   ├── api/
│   │   ├── ingest.py
│   │   └── search.py
│   │
│   ├── services/
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── ingestion.py
│   │   ├── pdf.py
│   │   ├── search.py
│   │   └── vector_store.py
│   │
│   ├── config.py
│   ├── dependencies.py
│   ├── logging_config.py
│   ├── models.py
│   └── main.py
│
├── data/
│   └── pdfs/
│
├── tests/
│
├── evaluation/
│   ├── dataset.json
│   └── evaluate.py
│
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

See `IMPLEMENTATION_PATH.md` for the incremental implementation and validation process.

```

One deliberate change is the **Assessment compatibility note**: the old statement that directory ingestion was unsupported is now removed, because it is no longer true. The README also reflects the actual `data/pdfs` directory and the new `EMBEDDING_BATCH_SIZE=32` decision.
```
