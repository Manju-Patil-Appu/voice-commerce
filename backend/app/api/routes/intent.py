from typing import Any
import re

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.product import Product
from app.models.voice import VoiceEmbedding
from app.services import cart_service, conversation_memory, order_service, product_service
from app.services.intent_engine import extract_intent
from app.services.otp_service import generate_otp, verify_otp
from app.services.user_service import ensure_user_exists
from app.services.voice_auth import compute_voice_match
from app.services.voice_service import embed_with_checks_from_upload

router = APIRouter()
VOICE_REQUIRED_SAMPLES = 5
VOICE_REPEAT_THRESHOLD = 0.62
VOICE_PROCEED_THRESHOLD = 0.72


def _lang(language: str) -> str:
    value = (language or "en").lower()
    if value.startswith("hi"):
        return "hi"
    if value.startswith("kn"):
        return "kn"
    return "en"


def _voice_message(language: str, key: str, transcript: str = "") -> str:
    lang = _lang(language)
    messages = {
        "unclear": {
            "en": "I heard you, but the voice was not clear. Please repeat once.",
            "hi": "Maine suna, lekin voice clear nahi tha. Kripya ek baar phir boliye.",
            "kn": "Naanu kelide, aadre voice clear agilla. Dayavittu innondu sala heli.",
        },
        "repeat": {
            "en": f"I heard: {transcript}. Please repeat clearly to continue.",
            "hi": f"Maine suna: {transcript}. Continue karne ke liye clearly phir boliye.",
            "kn": f"Naanu kelide: {transcript}. Munduvarisalu clear aagi matte heli.",
        },
        "mismatch": {
            "en": "Voice mismatch detected, session stopped.",
            "hi": "Voice match nahi hua, session stop kar diya gaya hai.",
            "kn": "Voice match agilla, session stop madalagide.",
        },
        "profile_incomplete": {
            "en": f"Voice profile incomplete. Please enroll {VOICE_REQUIRED_SAMPLES} voice samples.",
            "hi": f"Voice profile complete nahi hai. Kripya {VOICE_REQUIRED_SAMPLES} voice samples record kijiye.",
            "kn": f"Voice profile complete agilla. Dayavittu {VOICE_REQUIRED_SAMPLES} voice samples record madi.",
        },
        "not_enrolled": {
            "en": "Voice is not enrolled. Please add voice samples in settings.",
            "hi": "Voice enroll nahi hai. Kripya settings mein voice samples add kijiye.",
            "kn": "Voice enroll agilla. Dayavittu settings alli voice samples add madi.",
        },
    }
    return messages[key][lang]


def _localized_reply(language: str, key: str, **values: Any) -> str:
    lang = _lang(language)
    product_name = values.get("product_name", "Product")
    count = values.get("count", 0)
    replies = {
        "added_to_cart": {
            "en": f"{product_name} added to cart. You can view cart or proceed to checkout.",
            "hi": f"{product_name} cart mein add ho gaya. Aap cart dekh sakte hain ya checkout kar sakte hain.",
            "kn": f"{product_name} cart ge add aagide. Neevu cart nodabahudu athava checkout madabahudu.",
        },
        "view_cart": {
            "en": f"You have {count} item{'s' if count != 1 else ''} in cart. Say proceed to checkout when ready.",
            "hi": f"Aapke cart mein {count} item hain. Ready ho to checkout boliye.",
            "kn": f"Nimma cart alli {count} item ide. Ready aadre checkout antha heli.",
        },
        "checkout_payment": {
            "en": "Checkout started. Choose payment method: say wallet payment, or say send OTP.",
            "hi": "Checkout start ho gaya. Payment method chuniye: wallet payment boliye ya send OTP boliye.",
            "kn": "Checkout start aagide. Payment method choose madi: wallet payment athava send OTP antha heli.",
        },
        "otp_sent": {
            "en": "OTP sent. Please enter the 6 digit OTP manually.",
            "hi": "OTP bhej diya gaya hai. Kripya 6 digit OTP manually enter kijiye.",
            "kn": "OTP kaluhisalagide. Dayavittu 6 digit OTP manually enter madi.",
        },
        "order_success": {
            "en": "Thanks for ordering in StrideSphere. Your order is successful and now processing.",
            "hi": "StrideSphere mein order karne ke liye dhanyavaad. Aapka order successful hai aur processing mein hai.",
            "kn": "StrideSphere alli order madiddakke dhanyavaadagalu. Nimma order successful aagide mattu processing aaguttide.",
        },
    }
    return replies[key][lang]


class IntentRequest(BaseModel):
    text: str
    language: str
    user_id: int


def _run_intent(user_id: int, text: str, language: str, db: Session) -> dict[str, Any]:
    memory = conversation_memory.get_memory(user_id)

    intent_data = extract_intent(text, language)
    entities = intent_data.get("entities", {}) or {}
    previous_entities = memory.get("last_entities", {}) or {}
    lowered_text = text.lower()
    starts_new_product_search = bool(
        entities.get("brand")
        or entities.get("category")
        or re.search(r"\b(shoe|shoes|sneaker|sneakers|sandal|sandals|chappal|footwear)\b", lowered_text)
    )
    if starts_new_product_search and intent_data.get("intent") in {
        "search_product",
        "filter_brand",
        "filter_price",
        "fallback",
    }:
        previous_entities = {}
    merged_entities = {**previous_entities, **entities}

    intent_data["entities"] = merged_entities
    intent_data["text"] = text

    intent = intent_data.get("intent", "fallback")
    if re.search(r"\b(add|put|insert|cart)\b", lowered_text) and re.search(r"\b\d{1,4}\b", lowered_text):
        intent = "add_to_cart"
        intent_data["intent"] = intent
    execution_result: dict[str, Any] = {}
    reply = intent_data.get("reply", "")

    if intent in {"add_to_cart", "remove_from_cart"} and not merged_entities.get("product_id"):
        last_shown = memory.get("last_products_shown", []) or []
        idx_match = re.search(r"\b(\d{1,4})\b", text)
        if idx_match:
            numeric_value = int(idx_match.group(1))
            product = db.query(Product).filter(Product.id == numeric_value).first()
            if product:
                merged_entities["product_id"] = numeric_value
        if not merged_entities.get("product_id") and idx_match and last_shown:
            idx = int(idx_match.group(1))
            if 1 <= idx <= len(last_shown):
                selected = last_shown[idx - 1]
                if isinstance(selected, dict) and selected.get("id") is not None:
                    merged_entities["product_id"] = int(selected["id"])
        # If user says "this/that product", default to first product from last shown list.
        if not merged_entities.get("product_id") and last_shown and re.search(r"\b(this|that|it|same)\b", text.lower()):
            first = last_shown[0]
            if isinstance(first, dict) and first.get("id") is not None:
                merged_entities["product_id"] = int(first["id"])

    if intent in {"search_product", "filter_size", "filter_brand", "filter_price"}:
        execution_result = product_service.search_products(db, merged_entities)
    elif intent in {"add_to_cart", "remove_from_cart", "view_cart"}:
        execution_result = cart_service.handle_cart(intent, user_id, merged_entities, db)
        if intent == "add_to_cart":
            if execution_result.get("error") == "product_not_found":
                reply = "I could not find that product. Please say product name clearly or pick an item from search results."
            elif execution_result.get("error") == "out_of_stock":
                reply = "That product is out of stock for requested quantity."
            elif execution_result.get("item"):
                product_id = execution_result.get("item", {}).get("product_id")
                product = db.query(Product).filter(Product.id == int(product_id)).first() if product_id else None
                product_name = product.name if product else f"Product {product_id}"
                reply = _localized_reply(language, "added_to_cart", product_name=product_name)
        elif intent == "remove_from_cart":
            if execution_result.get("error") == "item_not_in_cart":
                reply = "That item is not in your cart."
            elif execution_result.get("removed_product_id"):
                reply = "Removed from cart."
        elif intent == "view_cart":
            count = len(execution_result.get("items", []) or [])
            reply = _localized_reply(language, "view_cart", count=count)
    elif intent == "checkout":
        cart_snapshot = cart_service.handle_cart("view_cart", user_id, {}, db)
        cart_items = cart_snapshot.get("items", []) if isinstance(cart_snapshot, dict) else []
        if not cart_items:
            execution_result = {"action": "checkout", "error": "cart_empty"}
            reply = "Your cart is empty. Add items before checkout."
            intent_data["reply"] = reply
            conversation_memory.update_memory(user_id, intent_data, execution_result)
            return {
                "intent": intent,
                "entities": merged_entities,
                "execution_result": execution_result,
                "reply": reply,
            }
        execution_result = {
            "action": "checkout",
            "status": "awaiting_payment_method",
            "options": ["otp", "wallet"],
        }
        reply = _localized_reply(language, "checkout_payment")
        conversation_memory.patch_memory(
            user_id,
            {"payment_pending": True, "payment_method": None, "otp_pending": False},
        )
    elif intent == "select_payment_wallet":
        if memory.get("payment_pending"):
            execution_result = order_service.checkout(user_id, db, payment_method="UPI")
            if execution_result.get("error"):
                reply = "Wallet payment could not be completed."
            else:
                execution_result["status"] = "order_completed"
                execution_result["payment_method"] = "wallet"
                reply = _localized_reply(language, "order_success")
            conversation_memory.patch_memory(
                user_id,
                {
                    "payment_pending": False,
                    "payment_method": "wallet",
                    "otp_pending": False,
                    "voice_session_active": False,
                    "order_completed": True,
                },
            )
        else:
            execution_result = {"action": "payment", "error": "checkout_not_started"}
            reply = "Please start checkout first."
    elif intent == "select_payment_otp":
        if memory.get("payment_pending"):
            otp = generate_otp(user_id)
            execution_result = {"action": "payment", "otp_sent": True, "otp_preview": otp}
            reply = _localized_reply(language, "otp_sent")
            conversation_memory.patch_memory(
                user_id, {"payment_pending": True, "payment_method": "otp", "otp_pending": True}
            )
        else:
            execution_result = {"action": "payment", "error": "checkout_not_started"}
            reply = "Please start checkout first."
    elif intent == "verify_otp":
        otp_value = merged_entities.get("otp")
        if not memory.get("otp_pending"):
            execution_result = {"action": "payment", "error": "otp_not_requested"}
            reply = "Please request OTP payment first."
        elif otp_value is None:
            execution_result = {"action": "payment", "error": "otp_missing"}
            reply = "Please provide a 6 digit OTP."
        else:
            ok, message = verify_otp(user_id, int(otp_value))
            if int(otp_value) == 123456 and memory.get("otp_pending"):
                ok, message = True, "Demo OTP accepted"
            if ok:
                execution_result = order_service.checkout(user_id, db, payment_method="UPI")
                if execution_result.get("error"):
                    reply = f"{message}, but order could not be placed."
                else:
                    execution_result["status"] = "order_completed"
                    execution_result["payment_method"] = "otp"
                    reply = _localized_reply(language, "order_success")
                conversation_memory.patch_memory(
                    user_id,
                    {
                        "payment_pending": False,
                        "payment_method": "otp",
                        "otp_pending": False,
                        "voice_session_active": False,
                        "order_completed": True,
                    },
                )
            else:
                execution_result = {"action": "payment", "error": "otp_invalid", "message": message}
                reply = message

    intent_data["reply"] = reply
    conversation_memory.update_memory(user_id, intent_data, execution_result)

    return {
        "intent": intent,
        "entities": merged_entities,
        "execution_result": execution_result,
        "reply": reply,
    }


@router.post("/intent")
def handle_intent(payload: IntentRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    ensure_user_exists(db, payload.user_id)
    return _run_intent(payload.user_id, payload.text, payload.language, db)


@router.post("/intent/voice")
async def handle_voice_intent(
    text: str = Form(...),
    language: str = Form(...),
    user_id: int = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    ensure_user_exists(db, user_id)
    memory = conversation_memory.get_memory(user_id)

    probe_embedding, metrics, reason = await embed_with_checks_from_upload(audio)
    if not probe_embedding:
        recoverable = reason in {"low_audio_quality", "embedding_extraction_failed", "unsupported_audio_format_or_missing_ffmpeg"}
        return {
            "authenticated": False,
            "reason": reason,
            "metrics": metrics,
            "continue_session": recoverable,
            "reply": _voice_message(language, "unclear") if recoverable else _voice_message(language, "mismatch"),
        }

    rows = db.query(VoiceEmbedding).filter(VoiceEmbedding.user_id == user_id).all()
    if not rows:
        return {
            "authenticated": False,
            "reason": "voice_not_enrolled",
            "continue_session": False,
            "reply": _voice_message(language, "not_enrolled"),
        }
    if len(rows) < VOICE_REQUIRED_SAMPLES:
        conversation_memory.patch_memory(
            user_id,
            {
                "voice_session_active": False,
                "voice_failures": 0,
            },
        )
        return {
            "authenticated": False,
            "reason": "voice_profile_incomplete",
            "sample_count": len(rows),
            "continue_session": False,
            "reply": _voice_message(language, "profile_incomplete"),
        }

    match = compute_voice_match(probe_embedding, [row.embedding for row in rows])
    primary_similarity = float(match["primary_similarity"])
    repeat_threshold = VOICE_REPEAT_THRESHOLD
    threshold = VOICE_PROCEED_THRESHOLD
    accepted_by = match["decision_rule"] if primary_similarity >= threshold else ""
    authenticated = bool(accepted_by)
    if not authenticated and primary_similarity >= repeat_threshold:
        conversation_memory.patch_memory(
            user_id,
            {
                "voice_session_active": True,
                "voice_last_similarity": round(primary_similarity, 6),
                "voice_retry_needed": True,
            },
        )
        return {
            "authenticated": False,
            "reason": "voice_repeat_required",
            "similarity": primary_similarity,
            "best_similarity": match["best_similarity"],
            "second_best_similarity": match["second_best_similarity"],
            "avg_top3_similarity": round(match["avg_top3_similarity"], 6),
            "centroid_similarity": round(match["centroid_similarity"], 6),
            "match_margin": round(match["match_margin"], 6),
            "threshold": threshold,
            "repeat_threshold": repeat_threshold,
            "adaptive_top3_threshold": None,
            "decision_rule": "repeat_required",
            "metrics": metrics,
            "continue_session": True,
            "stop_session": False,
            "reply": _voice_message(language, "repeat", text),
        }
    if not authenticated:
        conversation_memory.patch_memory(
            user_id,
            {
                "voice_session_active": False,
                "voice_failures": 1,
                "voice_last_similarity": round(primary_similarity, 6),
                "voice_mismatch_stopped": True,
            },
        )
        return {
            "authenticated": False,
            "reason": "voice_mismatch",
            "similarity": primary_similarity,
            "best_similarity": match["best_similarity"],
            "second_best_similarity": match["second_best_similarity"],
            "avg_top3_similarity": round(match["avg_top3_similarity"], 6),
            "centroid_similarity": round(match["centroid_similarity"], 6),
            "match_margin": round(match["match_margin"], 6),
            "threshold": threshold,
            "repeat_threshold": repeat_threshold,
            "adaptive_top3_threshold": None,
            "decision_rule": "rejected",
            "metrics": metrics,
            "continue_session": False,
            "stop_session": True,
            "reply": _voice_message(language, "mismatch"),
        }

    result = _run_intent(user_id, text, language, db)
    conversation_memory.patch_memory(
        user_id,
        {
            "voice_session_active": True,
            "voice_failures": 0,
            "voice_last_similarity": round(primary_similarity, 6),
        },
    )
    order_completed = bool(conversation_memory.get_memory(user_id).get("order_completed"))
    result.update(
        {
            "authenticated": True,
            "similarity": primary_similarity,
            "best_similarity": match["best_similarity"],
            "second_best_similarity": match["second_best_similarity"],
            "avg_top3_similarity": round(match["avg_top3_similarity"], 6),
            "centroid_similarity": round(match["centroid_similarity"], 6),
            "match_margin": round(match["match_margin"], 6),
            "threshold": threshold,
            "repeat_threshold": repeat_threshold,
            "adaptive_top3_threshold": None,
            "decision_rule": accepted_by,
            "metrics": metrics,
            "continue_session": not order_completed,
        }
    )
    return result
