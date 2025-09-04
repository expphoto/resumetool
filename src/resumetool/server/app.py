from fastapi import FastAPI

app = FastAPI(title="ResumeTool")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

