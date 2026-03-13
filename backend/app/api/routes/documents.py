from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["documents"])

RAW_DATA_DIR = Path("../data/raw")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

TEXT_FILE_SUFFIXES = {".txt", ".md"}


@router.get("/documents")
def list_documents():
    documents = []

    for file_path in RAW_DATA_DIR.iterdir():
        if file_path.is_file():
            documents.append(
                {
                    "filename": file_path.name,
                    "size_bytes": file_path.stat().st_size,
                    "suffix": file_path.suffix,
                }
            )

    documents.sort(key=lambda item: item["filename"])

    return {
        "count": len(documents),
        "documents": documents,
    }


@router.get("/documents/{filename}")
def read_document(filename: str):
    file_path = RAW_DATA_DIR / filename

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")

    if file_path.suffix not in TEXT_FILE_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Only .txt and .md files are supported for preview right now",
        )

    content = file_path.read_text(encoding="utf-8")

    return {
        "filename": file_path.name,
        "suffix": file_path.suffix,
        "size_bytes": file_path.stat().st_size,
        "content": content,
    }


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    file_path = RAW_DATA_DIR / file.filename

    content = await file.read()
    file_path.write_bytes(content)

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "saved_path": str(file_path),
        "message": "File uploaded successfully",
    }