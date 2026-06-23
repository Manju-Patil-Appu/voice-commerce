from pydantic import BaseModel

class VoiceEnrollOut(BaseModel):
    user_id: int
    embedding_id: int

class VoiceVerifyOut(BaseModel):
    user_id: int
    similarity: float
    authenticated: bool
