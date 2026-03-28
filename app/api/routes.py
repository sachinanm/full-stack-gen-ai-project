import os
import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from app.services.rag_service import get_rag_engine
from app.core.config import settings

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    session_id: str = "default_session"

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(settings.UPLOADS_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        engine = get_rag_engine()
        chunks = engine.ingest_document(file_path, file.filename)
        
        return {"filename": file.filename, "message": f"Successfully ingested {file.filename} into {chunks} chunks."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat")
async def chat(request: ChatRequest):
    try:
        engine = get_rag_engine()
        return StreamingResponse(
            engine.query_stream(request.query, request.session_id),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/stats")
async def get_stats():
    try:
        engine = get_rag_engine()
        return engine.get_db_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clear")
async def clear_db():
    try:
        engine = get_rag_engine()
        engine.clear_database()
        return {"message": "Knowledge base cleared successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
