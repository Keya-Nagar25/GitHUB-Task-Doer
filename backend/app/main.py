from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.execute import router as execute_router
from app.api.history import router as history_router
from app.api.resolve import router as resolve_router
from app.api.undo import router as undo_router
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

app.include_router(resolve_router)
app.include_router(auth_router)
app.include_router(execute_router)
app.include_router(undo_router)
app.include_router(history_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
