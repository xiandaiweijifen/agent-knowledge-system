from pathlib import Path

from fastapi import APIRouter, File, UploadFile

router = APIRouter(tags=["documents"])

RAW_DATA_DIR = Path("../data/raw")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)


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
        "message": "File uploaded successfully"
    }