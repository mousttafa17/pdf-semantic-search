from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.datastructures import UploadFile

from app.dependencies import get_ingestion_service

from app.services.chunking import ChunkingError
from app.services.embeddings import EmbeddingError
from app.services.ingestion import IngestionError, IngestionService
from app.services.pdf import PDFProcessingError
from app.services.vector_store import VectorStoreError
from starlette.concurrency import run_in_threadpool


router = APIRouter()


@router.post(
    "/ingest/",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "input": {
                                "description": "File(s) or directory path",
                                "oneOf": [
                                    {
                                        "type": "string",
                                        "description": (
                                            "Directory path containing PDF files"
                                        ),
                                    },
                                    {
                                        "type": "string",
                                        "format": "binary",
                                        "description": "Single PDF file",
                                    },
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "string",
                                            "format": "binary",
                                        },
                                        "description": "Multiple PDF files",
                                    },
                                ],
                            }
                        },
                        "required": ["input"],
                    }
                }
            },
        }
    },
)
async def ingest_files(
    request: Request,
    ingestion_service: Annotated[
        IngestionService,
        Depends(get_ingestion_service),
    ] = None,
) -> JSONResponse:
    """Ingest one or more PDF files or a directory containing PDFs."""

    form = await request.form()
    inputs = form.getlist("input")

    if not inputs:
        return JSONResponse(
            status_code=400,
            content={"error": "No input files were provided."},
        )

    uploaded_files: list[UploadFile] = []
    directory_paths: list[str] = []

    for item in inputs:
        if isinstance(item, UploadFile):
            uploaded_files.append(item)
        elif isinstance(item, str):
            path = item.strip()

            if path:
                directory_paths.append(path)
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": "Directory path cannot be empty."},
                )
        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Invalid input."},
            )

    # The request must use either file uploads or a directory path,
    # not both.
    if uploaded_files and directory_paths:
        return JSONResponse(
            status_code=400,
            content={
                "error": (
                    "Input must be either PDF files or a directory path."
                )
            },
        )

    # Directory input: exactly one directory path is allowed.
    if directory_paths:
        if len(directory_paths) != 1:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Only one directory path can be provided."
                },
            )

        directory = Path(directory_paths[0])

        if not directory.exists():
            return JSONResponse(
                status_code=400,
                content={"error": "Directory does not exist."},
            )

        if not directory.is_dir():
            return JSONResponse(
                status_code=400,
                content={"error": "Input path is not a directory."},
            )

        try:
            pdf_paths = sorted(
                path
                for path in directory.iterdir()
                if path.is_file() and path.suffix.lower() == ".pdf"
            )
        except OSError:
            return JSONResponse(
                status_code=400,
                content={"error": "Unable to read the specified directory."},
            )

        if not pdf_paths:
            return JSONResponse(
                status_code=400,
                content={"error": "Directory contains no PDF files."},
            )

        documents: list[tuple[str, bytes]] = []

        for pdf_path in pdf_paths:
            try:
                file_bytes = pdf_path.read_bytes()
            except OSError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": (
                            f"Unable to read PDF file '{pdf_path.name}'."
                        )
                    },
                )

            if not file_bytes:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": (
                            f"PDF file '{pdf_path.name}' is empty."
                        )
                    },
                )

            documents.append((pdf_path.name, file_bytes))

    # File upload input: one or more files can be supplied by
    # repeating the `input` multipart field.
    else:
        documents = []

        for uploaded_file in uploaded_files:
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
            except OSError:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": (
                            f"Unable to read uploaded file '{filename}'."
                        )
                    },
                )

            if not file_bytes:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": f"Uploaded file '{filename}' is empty."
                    },
                )

            documents.append((filename, file_bytes))

    successful_files: list[str] = []

    for filename, file_bytes in documents:
        try:
            await run_in_threadpool(
                ingestion_service.ingest,
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