from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingestion.document_service import (
    list_documents,
    read_text_document,
    save_uploaded_document,
)

router = APIRouter(tags=["documents"])


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
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .md files are supported for preview right now",
        )


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