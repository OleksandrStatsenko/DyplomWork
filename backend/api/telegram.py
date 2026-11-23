import logging
import secrets

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database.models import ConversationHistory, User
from backend.database.session import get_db
from backend.services.ai_service import generate_reply

router = APIRouter(prefix="/api/telegram", tags=["telegram"])
logger = logging.getLogger(__name__)


async def send_message(chat_id: int, text: str) -> None:
    if not settings.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN не налаштовано.")

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            url,
            json={"chat_id": chat_id, "text": text},
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError("Telegram Bot API не підтвердив надсилання повідомлення.")


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
    if not isinstance(chat_id, int) or not isinstance(telegram_id, int) or not text:
        return {"ok": True}

    user = db.scalar(select(User).where(User.telegram_id == telegram_id))
    if user is None:
        user = User(
            telegram_id=telegram_id,
            username=sender.get("username") or sender.get("first_name"),
        )
        db.add(user)
        db.flush()

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
        reply = (
            "Вітаю! Я голосовий помічник для обліку постачальників, товарів і поставок. "
            "Напишіть запитання або скористайтеся командою /ask <текст>."
        )
    elif normalized_command == "/ask":
        if not argument.strip():
            reply = "Напишіть запитання після команди. Наприклад: /ask Як додати нового постачальника?"
        else:
            reply = await generate_reply(argument.strip())
    elif text.startswith("/"):
        reply = "Не знаю такої команди. Надішліть звичайне повідомлення або скористайтеся /ask."
    else:
        reply = await generate_reply(text)

    try:
        await send_message(chat_id, reply)
    except Exception as exc:
        logger.exception("Не вдалося надіслати відповідь Telegram")
        raise HTTPException(status_code=502, detail="Не вдалося надіслати відповідь у Telegram.") from exc

    db.add(ConversationHistory(
        user_id=user.id,
        channel="telegram",
        role="assistant",
        content=reply,
    ))
    db.commit()
    return {"ok": True}
