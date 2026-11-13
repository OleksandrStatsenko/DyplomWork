import base64
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from backend.schemas import AssistantMessage, AssistantReply, VoiceReply
from backend.services.ai_service import generate_reply
from backend.services.speech_service import synthesize_speech, transcribe_audio

router = APIRouter(prefix="/api/assistant", tags=["голосовий помічник"])
logger = logging.getLogger(__name__)
MAX_AUDIO_SIZE = 12 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {
    "audio/webm", "audio/ogg", "audio/wav", "audio/mpeg",
    "audio/mp4", "audio/x-m4a", "audio/aac",
}


@router.post("/chat", response_model=AssistantReply)
async def chat(payload: AssistantMessage):
    try:
        reply = await generate_reply(payload.message)
        return AssistantReply(reply=reply)
    except Exception as exc:
        logger.exception("Помилка генерації відповіді")
        raise HTTPException(status_code=502, detail="Не вдалося отримати відповідь від ШІ.") from exc


@router.post("/voice", response_model=VoiceReply)
async def voice(file: UploadFile = File(...)):
    media_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if media_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=415, detail="Непідтримуваний формат аудіо.")
    audio = await file.read(MAX_AUDIO_SIZE + 1)
    if not audio:
        raise HTTPException(status_code=400, detail="Аудіофайл порожній.")
    if len(audio) > MAX_AUDIO_SIZE:
        raise HTTPException(status_code=413, detail="Аудіофайл перевищує 12 МБ.")

    try:
        transcript = await transcribe_audio(audio, file.filename or "voice.webm")
        reply = await generate_reply(transcript)
        spoken = await run_in_threadpool(synthesize_speech, reply)
        return VoiceReply(
            transcript=transcript,
            reply=reply,
            audio_base64=base64.b64encode(spoken).decode("ascii"),
            audio_media_type="audio/mpeg",
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Помилка обробки голосового запиту")
        raise HTTPException(status_code=502, detail="Не вдалося обробити голосове повідомлення.") from exc
