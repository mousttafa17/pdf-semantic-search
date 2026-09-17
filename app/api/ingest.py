from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.dependencies import get_ingestion_service

from app.services.chunking import ChunkingError
from app.services.embeddings import EmbeddingError
from app.services.ingestion import IngestionError, IngestionService
from app.services.pdf import PDFProcessingError
from app.services.vector_store import VectorStoreError


router = APIRouter()


@router.post("/ingest/")
def ingest_files(
    input: list[UploadFile] = File(...),
    ingestion_service: Annotated[
        IngestionService,
        Depends(get_ingestion_service),
    ] = None,
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
                        "error": (
                            f"Uploaded file '{filename}' is empty."
                        )
                    },
                )

            ingestion_service.ingest(
                file_bytes=file_bytes,
                filename=filename,
            )

            successful_files.append(filename)

        except (PDFProcessingError, ChunkingError) as exc:
            return JSONResponse(
                status_code=400,
                content={"error": str(exc)},
            )

        except (EmbeddingError, VectorStoreError, IngestionError):
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error."},
            )

        except Exception:
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error."},
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