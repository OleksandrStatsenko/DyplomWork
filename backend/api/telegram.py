import io
import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.config import settings
from backend.database.models import ConversationHistory, User
from backend.database.session import get_db
from backend.services.ai_service import generate_reply
from backend.services.speech_service import synthesize_speech, transcribe_audio
from backend.services.telegram_commands import handle_accounting_command

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)
MAX_TELEGRAM_AUDIO_SIZE = 12 * 1024 * 1024


async def telegram_api(method: str, *, data: dict | None = None, files: dict | None = None):
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не налаштовано.")
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, data=data, files=files)
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram Bot API: {method} завершився помилкою.")
        return payload["result"]


async def send_message(chat_id: int, text: str) -> None:
    await telegram_api("sendMessage", data={"chat_id": str(chat_id), "text": text})


async def send_voice(chat_id: int, text: str) -> None:
    audio = await run_in_threadpool(synthesize_speech, text)
    await telegram_api(
        "sendVoice",
        data={"chat_id": str(chat_id), "caption": text[:1024]},
        files={"voice": ("reply.mp3", io.BytesIO(audio), "audio/mpeg")},
    )


async def download_telegram_audio(file_id: str) -> tuple[bytes, str]:
    file_info = await telegram_api("getFile", data={"file_id": file_id})
    file_path = file_info.get("file_path")
    file_size = file_info.get("file_size", 0)
    if not file_path:
        raise RuntimeError("Telegram не повернув шлях до аудіофайлу.")
    if file_size and file_size > MAX_TELEGRAM_AUDIO_SIZE:
        raise ValueError("Аудіофайл перевищує дозволені 12 МБ.")

    url = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}/{file_path}"
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        audio = response.content
    if not audio:
        raise ValueError("Отримано порожній аудіофайл.")
    if len(audio) > MAX_TELEGRAM_AUDIO_SIZE:
        raise ValueError("Аудіофайл перевищує дозволені 12 МБ.")
    return audio, file_path.rsplit("/", 1)[-1]


@router.post("/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    expected_secret = settings.telegram_webhook_secret
    if not expected_secret or not x_telegram_bot_api_secret_token:
        raise HTTPException(status_code=503, detail="Telegram webhook не налаштовано.")
    if not secrets.compare_digest(x_telegram_bot_api_secret_token, expected_secret):
        raise HTTPException(status_code=403, detail="Невірний секрет webhook.")

    update = await request.json()
    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return {"ok": True}

    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    chat_id = chat.get("id")
    telegram_id = sender.get("id")
    text = (message.get("text") or "").strip()
    voice = message.get("voice") or message.get("audio")
    if not isinstance(chat_id, int) or not isinstance(telegram_id, int):
        return {"ok": True}
    if not text and not isinstance(voice, dict):
        return {"ok": True}

    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=sender.get("username") or sender.get("first_name"),
        )
        db.add(user)
        db.flush()

    try:
        if isinstance(voice, dict):
            audio, filename = await download_telegram_audio(voice["file_id"])
            text = await transcribe_audio(audio, filename)
        db.add(ConversationHistory(
            user_id=user.id,
            channel="telegram",
            role="user",
            content=text,
        ))
        db.commit()

        command, _, argument = text.partition(" ")
        normalized_command = command.split("@", 1)[0].lower()
        if normalized_command == "/start":
            reply = handle_accounting_command("/start", db)
        elif normalized_command == "/ask":
            if not argument.strip():
                reply = "Напишіть запитання після команди /ask."
            else:
                reply = await generate_reply(argument.strip())
        else:
            try:
                reply = handle_accounting_command(text, db)
            except ValueError as exc:
                reply = f"Не вдалося виконати команду: {exc}"
            if reply is None:
                if text.startswith("/"):
                    reply = "Не знаю такої команди. Надішліть /help, щоб побачити доступні команди."
                else:
                    reply = await generate_reply(text)

        if isinstance(voice, dict):
            await send_voice(chat_id, reply)
        else:
            await send_message(chat_id, reply)

        db.add(ConversationHistory(
            user_id=user.id,
            channel="telegram",
            role="assistant",
            content=reply,
        ))
        db.commit()
        return {"ok": True}
    except ValueError as exc:
        db.rollback()
        await send_message(chat_id, str(exc))
        return {"ok": True}
    except Exception as exc:
        db.rollback()
        logger.exception("Помилка обробки Telegram update")
        raise HTTPException(status_code=502, detail="Не вдалося обробити повідомлення Telegram.") from exc
