from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    DATABASE_URL: str
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    VOICE_AUTH_THRESHOLD: float = 0.80

    OPENAI_API_KEY: str | None = None

    TTS_MODEL: str = "gpt-4o-mini-tts"
    TTS_RESPONSE_FORMAT: str = "mp3"
    TTS_VOICE_EN: str = "alloy"
    TTS_VOICE_HI: str = "nova"
    TTS_VOICE_KN: str = "shimmer"

    INTENT_MODEL: str = "gpt-4o-mini"

    REDIS_URL: str | None = None

    FASTTEXT_LID_MODEL_PATH: str = "models/lid.176.bin"

    VOICE_MIN_DURATION_SEC: float = 0.7
    VOICE_MIN_RMS: float = 0.01
    VOICE_MAX_SILENCE_RATIO: float = 0.7
    VOICE_MIN_ZERO_CROSSING_RATE: float = 0.02

    class Config:
        env_file = BASE_DIR / ".env"

settings = Settings()
