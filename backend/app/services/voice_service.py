import os
import shutil
import subprocess
import tempfile

import numpy as np
import soundfile as sf

from app.core.config import settings
from app.services.voice_auth import extract_embedding


async def embed_from_upload(audio_file):
    ext = os.path.splitext(getattr(audio_file, "filename", "") or "")[1] or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp_path = tmp.name
    work_path = tmp_path
    converted_path = None
    try:
        content = await audio_file.read()
        tmp.write(content)
        tmp.close()
        work_path, converted_path, convert_error = _ensure_readable_audio(tmp_path)
        if convert_error:
            return []
        embedding = extract_embedding(work_path)
        return [float(v) for v in embedding.tolist()]
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if converted_path and os.path.exists(converted_path):
            os.remove(converted_path)


def _zero_crossing_rate(samples: np.ndarray) -> float:
    if samples.size < 2:
        return 0.0
    centered = samples - float(np.mean(samples))
    signs = np.sign(centered)
    crossings = np.sum(np.abs(np.diff(signs)) > 0)
    return float(crossings) / float(samples.size - 1)


def analyze_audio_file(audio_path: str) -> dict:
    samples, sample_rate = sf.read(audio_path)
    if samples.ndim > 1:
        samples = np.mean(samples, axis=1)
    samples = np.asarray(samples, dtype=np.float32)

    duration_sec = float(samples.size / sample_rate) if sample_rate else 0.0
    rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
    zcr = _zero_crossing_rate(samples)

    silence_threshold = max(float(settings.VOICE_MIN_RMS) * 0.35, 1e-4)
    silence_ratio = float(np.mean(np.abs(samples) < silence_threshold)) if samples.size else 1.0

    quality_ok = (
        duration_sec >= float(settings.VOICE_MIN_DURATION_SEC)
        and rms >= float(settings.VOICE_MIN_RMS)
        and silence_ratio <= float(settings.VOICE_MAX_SILENCE_RATIO)
    )
    usable_for_embedding = duration_sec >= 0.45 and rms >= 0.004

    # Basic offline liveness/replay heuristic:
    # extremely low zcr with long silence is often replay/flat audio.
    liveness_ok = not (
        duration_sec >= float(settings.VOICE_MIN_DURATION_SEC)
        and silence_ratio > 0.75
        and zcr < float(settings.VOICE_MIN_ZERO_CROSSING_RATE)
    )

    return {
        "duration_sec": round(duration_sec, 3),
        "rms": round(rms, 6),
        "silence_ratio": round(silence_ratio, 4),
        "zero_crossing_rate": round(zcr, 6),
        "quality_ok": bool(quality_ok),
        "usable_for_embedding": bool(usable_for_embedding),
        "liveness_ok": bool(liveness_ok),
    }


def _ensure_readable_audio(input_path: str) -> tuple[str, str | None, str | None]:
    try:
        sf.read(input_path)
        return input_path, None, None
    except Exception:
        pass

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return input_path, None, "unsupported_audio_format_or_missing_ffmpeg"

    out = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    out_path = out.name
    out.close()
    cmd = [ffmpeg, "-y", "-i", input_path, "-ar", "16000", "-ac", "1", out_path]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        if os.path.exists(out_path):
            os.remove(out_path)
        return input_path, None, "ffmpeg_conversion_failed"
    return out_path, out_path, None


async def embed_with_checks_from_upload(audio_file):
    ext = os.path.splitext(getattr(audio_file, "filename", "") or "")[1] or ".wav"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tmp_path = tmp.name
    work_path = tmp_path
    converted_path = None
    try:
        content = await audio_file.read()
        tmp.write(content)
        tmp.close()

        work_path, converted_path, convert_error = _ensure_readable_audio(tmp_path)
        if convert_error:
            return None, {"quality_ok": False, "liveness_ok": False}, convert_error

        metrics = analyze_audio_file(work_path)
        if not metrics.get("usable_for_embedding"):
            return None, metrics, "low_audio_quality"
        if not metrics["liveness_ok"]:
            return None, metrics, "possible_replay_or_synthetic"

        try:
            embedding = extract_embedding(work_path)
        except Exception:
            return None, metrics, "embedding_extraction_failed"
        return [float(v) for v in embedding.tolist()], metrics, None
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if converted_path and os.path.exists(converted_path):
            os.remove(converted_path)
