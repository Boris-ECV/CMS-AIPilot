from fastapi import FastAPI

app = FastAPI(title="CMS AI Pilot")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
