from fastapi import APIRouter, File, UploadFile

router = APIRouter(tags=["documents"])


@router.post("/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "message": "Upload endpoint ready"
    }