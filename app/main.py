from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request

from app.core import db
from app.core.logging import bind, get_logger, setup_logging
from app.routers import applications, assistant, documents, health, loans


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    yield
    db.close_pool()


app = FastAPI(title="mortgage-assistant", lifespan=lifespan)
log = get_logger(__name__)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid4().hex[:12]
    bind(request_id=request_id)
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    log.info("request", method=request.method, path=request.url.path, status=response.status_code)
    return response

app.include_router(health.router)
app.include_router(loans.router)
app.include_router(assistant.router)
app.include_router(applications.router)
app.include_router(documents.router)
