from typing import Literal

from fastapi import APIRouter, HTTPException, Query, UploadFile

from app.core.config import settings
from app.rag import retrieval
from app.schemas.documents import Document, Hit
from app.services import indexing

router = APIRouter(tags=["documents"])


@router.post("/documents", status_code=202, response_model=Document)
async def upload(file: UploadFile):
    data = await file.read(settings.upload_max_bytes + 1)
    if len(data) > settings.upload_max_bytes:
        raise HTTPException(413, "файл больше допустимого размера")
    if not data:
        raise HTTPException(400, "пустой файл")
    return await indexing.upload(file.filename or "без имени", data)


@router.get("/documents/{doc_id}", response_model=Document)
def get_document(doc_id: str):
    doc = indexing.get(doc_id)
    if doc is None:
        raise HTTPException(404, "документ не найден")
    return doc


@router.get("/search", response_model=list[Hit])
def search(q: str = Query(min_length=2), mode: Literal["hybrid", "vector", "fts"] = "hybrid",
           top_k: int = Query(default=5, ge=1, le=20), filename: str | None = None):
    return retrieval.search(q, mode, top_k, filename)
