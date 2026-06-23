import re
from typing import Dict

from langdetect import detect_langs


_ENGLISH_WORD_RE = re.compile(r"[a-zA-Z]+")
_WORD_RE = re.compile(r"[a-zA-Z]+")
_KANNADA_KEYWORDS = {"ideya", "beku", "sigutha", "illa", "anna", "maga", "yen", "yestu"}
_HINDI_KEYWORDS = {"ka", "hai", "dikhao", "chahiye", "andar", "batao", "karo", "dalo"}


def _english_word_ratio(text: str) -> float:
    words = re.findall(r"\S+", text)
    if not words:
        return 0.0
    english_count = len(_ENGLISH_WORD_RE.findall(text))
    return english_count / len(words)


def detect_language(text: str) -> Dict[str, object]:
    cleaned = (text or "").strip()
    if not cleaned:
        return {"language": "en", "confidence": 0.0, "is_mixed": False}

    try:
        predictions = detect_langs(cleaned)
        if not predictions:
            return {"language": "en", "confidence": 0.0, "is_mixed": False}

        top = predictions[0]
        detected = top.lang
        confidence = float(top.prob)

        if detected in {"hi", "mr"}:
            base_lang = "hi"
        elif detected == "kn":
            base_lang = "kn"
        else:
            base_lang = "en"

        words = {w.lower() for w in _WORD_RE.findall(cleaned)}
        has_kn_keywords = any(k in words for k in _KANNADA_KEYWORDS)
        has_hi_keywords = any(k in words for k in _HINDI_KEYWORDS)

        ratio = _english_word_ratio(cleaned)
        english_words_present = ratio > 0.0

        if base_lang == "en":
            if has_kn_keywords:
                return {"language": "kn-en", "confidence": confidence, "is_mixed": True}
            if has_hi_keywords:
                return {"language": "hi-en", "confidence": confidence, "is_mixed": True}

        if base_lang == "hi" and ratio > 0.30:
            return {"language": "hi-en", "confidence": confidence, "is_mixed": True}
        if base_lang == "kn" and english_words_present:
            return {"language": "kn-en", "confidence": confidence, "is_mixed": True}

        return {"language": base_lang, "confidence": confidence, "is_mixed": False}
    except Exception:
        return {"language": "en", "confidence": 0.0, "is_mixed": False}
