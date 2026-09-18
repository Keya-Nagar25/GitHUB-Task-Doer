from fastapi import FastAPI

from app.api.resolve import router as resolve_router

app = FastAPI(
    title="GitHub Task Doer API",
    description="Turns plain English into explained, confirmable Git/GitHub actions.",
    version="0.1.0",
)

app.include_router(resolve_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
