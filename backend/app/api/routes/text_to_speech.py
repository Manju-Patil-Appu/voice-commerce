from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import io

from openai import OpenAI

from app.core.config import settings
from app.services.language_detector import detect_language

router = APIRouter()


class TextToSpeechIn(BaseModel):
    text: str


def _pick_voice(lang: str) -> str:
    if lang.startswith("kn"):
        return settings.TTS_VOICE_KN
    if lang.startswith("hi"):
        return settings.TTS_VOICE_HI
    return settings.TTS_VOICE_EN


@router.post("/text-to-speech")
def text_to_speech(payload: TextToSpeechIn):
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="Text is required")

    detected = detect_language(payload.text)
    lang = str(detected["language"])
    voice = _pick_voice(lang)

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    with client.audio.speech.with_streaming_response.create(
        model=settings.TTS_MODEL,
        voice=voice,
        input=payload.text,
        response_format=settings.TTS_RESPONSE_FORMAT,
    ) as response:
        audio_bytes = b"".join(response.iter_bytes())

    media_type = "audio/mpeg" if settings.TTS_RESPONSE_FORMAT == "mp3" else f"audio/{settings.TTS_RESPONSE_FORMAT}"
    headers = {"X-Detected-Language": lang}
    return StreamingResponse(io.BytesIO(audio_bytes), media_type=media_type, headers=headers)
