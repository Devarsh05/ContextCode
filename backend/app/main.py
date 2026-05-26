from fastapi import FastAPI

app = FastAPI(title="ContextCode API")


@app.get("/health")
async def health():
    return {"status": "ok"}
