from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingestion.document_service import (
    chunk_document,
    chunk_document_with_strategy,
    delete_document_with_artifacts,
    list_documents,
    load_persisted_chunks,
    persist_document_chunks,
    read_text_document,
    save_uploaded_document,
)
from app.services.indexing.embedding_service import (
    load_persisted_embeddings,
    persist_document_embeddings,
)

router = APIRouter(tags=["documents"])


def raise_document_value_error(exc: ValueError) -> None:
    """Map document service validation errors to HTTP responses."""
    error_code = str(exc)

    if error_code == "unsupported_file_type":
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .md files are supported for preview right now",
        )

    if error_code == "text_decode_error":
        raise HTTPException(
            status_code=400,
            detail="Document must be UTF-8 encoded for text preview right now",
        )

    raise HTTPException(status_code=400, detail=error_code)


@router.get("/documents")
def get_documents():
    documents = list_documents()
    return {
        "count": len(documents),
        "documents": documents,
    }


@router.get("/documents/{filename}")
def get_document_content(filename: str):
    try:
        return read_text_document(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except ValueError as exc:
        raise_document_value_error(exc)


@router.delete("/documents/{filename}")
def delete_document(filename: str):
    try:
        return delete_document_with_artifacts(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    # Read request payload once before persisting it.
    content = await file.read()

    saved_document = save_uploaded_document(file.filename, content)

    return {
        "filename": saved_document["filename"],
        "content_type": file.content_type,
        "size_bytes": saved_document["size_bytes"],
        "saved_path": saved_document["saved_path"],
        "message": "File uploaded successfully",
    }


@router.get("/documents/{filename}/chunks")
def get_document_chunks(
    filename: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    chunk_strategy: str = "character",
):
    try:
        return chunk_document_with_strategy(
            filename=filename,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_strategy=chunk_strategy,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except ValueError as exc:
        raise_document_value_error(exc)


@router.post("/documents/{filename}/chunks/persist")
def persist_chunks(
    filename: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    chunk_strategy: str = "character",
):
    try:
        return persist_document_chunks(
            filename=filename,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            chunk_strategy=chunk_strategy,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except ValueError as exc:
        raise_document_value_error(exc)


@router.get("/documents/{filename}/chunks/persisted")
def get_persisted_chunks(filename: str):
    try:
        return load_persisted_chunks(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Persisted chunk file not found")


@router.post("/documents/{filename}/embeddings/persist")
def persist_embeddings(filename: str):
    try:
        return persist_document_embeddings(filename)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail="Persisted chunk file not found. Generate chunks first",
        )
    except ValueError as exc:
        raise_document_value_error(exc)


@router.get("/documents/{filename}/embeddings/persisted")
def get_persisted_embeddings(filename: str):
    try:
        return load_persisted_embeddings(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Persisted embedding file not found")
