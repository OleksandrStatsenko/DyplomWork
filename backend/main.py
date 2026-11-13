from fastapi import FastAPI

app = FastAPI(
    title="Cloud Voice Assistant API",
    description="Server-side API for the Telegram and web voice assistant.",
    version="0.1.0",
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    return {
        "service": "cloud-voice-assistant",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
