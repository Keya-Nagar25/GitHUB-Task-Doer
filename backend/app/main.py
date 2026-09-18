from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.execute import router as execute_router
from app.api.history import router as history_router
from app.api.resolve import router as resolve_router
from app.api.undo import router as undo_router
from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="GitHub Task Doer API",
    description="Turns plain English into explained, confirmable Git/GitHub actions.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(resolve_router)
app.include_router(auth_router)
app.include_router(execute_router)
app.include_router(undo_router)
app.include_router(history_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
