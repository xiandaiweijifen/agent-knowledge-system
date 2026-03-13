from pathlib import Path

from fastapi import APIRouter, File, UploadFile

router = APIRouter(tags=["documents"])

RAW_DATA_DIR = Path("../data/raw")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


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