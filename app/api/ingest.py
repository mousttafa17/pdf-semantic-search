from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.services.embeddings import get_embedding_service
from app.services.ingestion import IngestionError, IngestionService
from app.services.vector_store import VectorStore


router = APIRouter()

ingestion_service = IngestionService(
    embedding_service=get_embedding_service(),
    vector_store=VectorStore(),
)


@router.post("/ingest/")
def ingest_files(
    input: list[UploadFile] = File(...),
) -> JSONResponse:
    """Ingest one or more PDF documents."""

    if not input:
        return JSONResponse(
            status_code=400,
            content={"error": "No input files were provided."},
        )

    successful_files: list[str] = []

    for uploaded_file in input:
        filename = uploaded_file.filename or ""

        if not filename:
            return JSONResponse(
                status_code=400,
                content={"error": "Uploaded file has no filename."},
            )

        if not filename.lower().endswith(".pdf"):
            return JSONResponse(
                status_code=400,
                content={"error": "Only PDF files are accepted."},
            )

        try:
            file_bytes = uploaded_file.file.read()

            if not file_bytes:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Uploaded file '{filename}' is empty."
                    },
                )

            ingestion_service.ingest(
                file_bytes=file_bytes,
                filename=filename,
            )

            successful_files.append(filename)

        except IngestionError as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
            )

        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Failed to process uploaded file."
                },
            )

    return JSONResponse(
        status_code=200,
        content={
            "message": (
                f"Successfully ingested "
                f"{len(successful_files)} PDF documents."
            ),
            "files": successful_files,
        },
    )