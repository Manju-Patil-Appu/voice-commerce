from fastapi import APIRouter, File, UploadFile, Form, HTTPException
import tempfile
from openai import OpenAI
from app.core.config import settings
from app.services.language_detector import detect_language

router = APIRouter()

@router.post("/voice-to-text")
def voice_to_text(
    audio: UploadFile = File(...),
    prompt: str | None = Form(None),
):
    try:
        if not settings.OPENAI_API_KEY:
            raise HTTPException(status_code=500, detail="OPENAI_API_KEY not configured")

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Preserve actual extension
        suffix = "." + audio.filename.split(".")[-1] if audio.filename else ".webm"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            content = audio.file.read()

            if not content:
                raise HTTPException(status_code=400, detail="Empty audio file")

            tmp.write(content)
            tmp.flush()

            with open(tmp.name, "rb") as f:
                transcription = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    prompt=prompt,
                    response_format="json",
                )

        detected = detect_language(transcription.text)

        return {
            "success": True,
            "text": transcription.text,
            "language": detected["language"]
        }

    except Exception as e:
        print("VOICE_TO_TEXT_ERROR:", str(e))
        raise HTTPException(status_code=500, detail=str(e))