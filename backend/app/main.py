from fastapi import FastAPI

app = FastAPI(
    title="GitHub Task Doer API",
    description="Turns plain English into explained, confirmable Git/GitHub actions.",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
