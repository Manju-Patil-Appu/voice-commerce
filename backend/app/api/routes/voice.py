from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.voice import VoiceEmbedding
from app.services.user_service import ensure_user_exists
from app.services.voice_auth import compute_voice_match
from app.services.voice_service import embed_with_checks_from_upload

router = APIRouter()
VOICE_REQUIRED_SAMPLES = 5
VOICE_REPEAT_THRESHOLD = 0.62
VOICE_PROCEED_THRESHOLD = 0.72


@router.get("/profile")
def voice_profile(user_id: int, db: Session = Depends(get_db)):
    ensure_user_exists(db, user_id)
    rows = (
        db.query(VoiceEmbedding)
        .filter(VoiceEmbedding.user_id == user_id)
        .order_by(VoiceEmbedding.id.asc())
        .all()
    )
    embedding_ids = [row.id for row in rows]
    return {
        "user_id": user_id,
        "sample_count": len(embedding_ids),
        "required_samples": VOICE_REQUIRED_SAMPLES,
        "embedding_ids": embedding_ids,
    }


@router.post("/reset")
def reset_voice_profile(user_id: int, db: Session = Depends(get_db)):
    ensure_user_exists(db, user_id)
    deleted = db.query(VoiceEmbedding).filter(VoiceEmbedding.user_id == user_id).delete()
    db.commit()
    return {"user_id": user_id, "deleted_samples": int(deleted)}


@router.post("/enroll")
async def enroll_voice(
    user_id: int,
    audio: UploadFile = File(...),
    replace_existing: bool = False,
    db: Session = Depends(get_db),
):
    ensure_user_exists(db, user_id)

    embedding, metrics, reason = await embed_with_checks_from_upload(audio)
    if not embedding:
        return {
            "enrolled": False,
            "reason": reason,
            "metrics": metrics,
        }

    if replace_existing:
        db.query(VoiceEmbedding).filter(VoiceEmbedding.user_id == user_id).delete()
        db.commit()

    row = VoiceEmbedding(user_id=user_id, embedding=embedding)
    db.add(row)
    db.commit()
    db.refresh(row)
    sample_count = db.query(VoiceEmbedding).filter(VoiceEmbedding.user_id == user_id).count()
    return {
        "enrolled": True,
        "message": "Voice enrolled successfully",
        "embedding_id": row.id,
        "sample_count": sample_count,
        "required_samples": VOICE_REQUIRED_SAMPLES,
        "metrics": metrics,
    }


@router.post("/verify")
async def verify_voice(user_id: int, audio: UploadFile = File(...), db: Session = Depends(get_db)):
    ensure_user_exists(db, user_id)

    probe_embedding, metrics, reason = await embed_with_checks_from_upload(audio)
    if not probe_embedding:
        return {
            "authenticated": False,
            "reason": reason,
            "metrics": metrics,
        }

    rows = db.query(VoiceEmbedding).filter(VoiceEmbedding.user_id == user_id).all()
    if not rows:
        return {"authenticated": False, "reason": "User not enrolled"}
    if len(rows) < VOICE_REQUIRED_SAMPLES:
        return {
            "authenticated": False,
            "reason": "voice_profile_incomplete",
            "sample_count": len(rows),
            "threshold": max(float(settings.VOICE_AUTH_THRESHOLD), VOICE_PROCEED_THRESHOLD),
        }

    match = compute_voice_match(probe_embedding, [row.embedding for row in rows])
    threshold = max(float(settings.VOICE_AUTH_THRESHOLD), VOICE_PROCEED_THRESHOLD)
    repeat_threshold = VOICE_REPEAT_THRESHOLD
    authenticated = match["primary_similarity"] >= threshold
    reason = None
    if not authenticated:
        reason = "voice_repeat_required" if match["primary_similarity"] >= repeat_threshold else "voice_mismatch"

    return {
        "authenticated": authenticated,
        "reason": reason,
        "similarity": match["primary_similarity"],
        "best_similarity": match["best_similarity"],
        "second_best_similarity": match["second_best_similarity"],
        "avg_top3_similarity": round(match["avg_top3_similarity"], 6),
        "centroid_similarity": round(match["centroid_similarity"], 6),
        "adaptive_top3_threshold": None,
        "match_margin": round(match["match_margin"], 6),
        "threshold": threshold,
        "repeat_threshold": repeat_threshold,
        "decision_rule": match["decision_rule"] if authenticated else "rejected",
        "sample_count": len(rows),
        "metrics": metrics,
    }
