from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.routes import router
from backend.api.assistant import router as assistant_router
from backend.config import settings

app = FastAPI(
    title=settings.app_name,
    description="Серверна частина голосового помічника для вебсайту та Telegram.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.web_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(assistant_router)


@app.get("/health", tags=["система"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Вебінтерфейс віддається тим самим сервером, що й REST API.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
