import io

from gtts import gTTS
from openai import AsyncOpenAI

from backend.config import settings


async def transcribe_audio(audio: bytes, filename: str) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("Для розпізнавання мовлення потрібно налаштувати GROQ_API_KEY.")

    client = AsyncOpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
    )
    try:
        result = await client.audio.transcriptions.create(
            model=settings.groq_transcription_model,
            file=(filename, audio),
            language="uk",
            response_format="json",
            temperature=0,
        )
        transcript = result.text.strip()
        if not transcript:
            raise ValueError("Не вдалося розпізнати мовлення. Спробуйте ще раз.")
        return transcript
    finally:
        await client.close()


def synthesize_speech(text: str) -> bytes:
    audio = io.BytesIO()
    gTTS(text=text, lang="uk").write_to_fp(audio)
    return audio.getvalue()
