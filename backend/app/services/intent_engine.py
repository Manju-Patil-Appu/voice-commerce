import re
from typing import Any

SUPPORTED_INTENTS = {
    "search_product",
    "filter_size",
    "filter_brand",
    "filter_price",
    "add_to_cart",
    "remove_from_cart",
    "view_cart",
    "checkout",
    "select_payment_otp",
    "select_payment_wallet",
    "verify_otp",
    "greeting",
    "fallback",
}

BRANDS = ["nike", "adidas", "puma", "reebok", "skechers", "bata", "woodland", "campus"]
COLORS = ["black", "white", "blue", "red", "gray", "grey", "green", "brown", "navy"]
CATEGORY_HINTS = {
    "running": "Running Shoes",
    "casual": "Casual Shoes",
    "sports": "Sports Shoes",
    "formal": "Formal Shoes",
    "sneakers": "Sneakers",
    "sandals": "Sandals",
    "runn": "Running Shoes",
    "sport": "Sports Shoes",
    
}


def _reply(intent: str, language: str) -> str:
    lang = (language or "en").lower()

    if lang.startswith("hi"):
        mapping = {
            "greeting": "Namaste, main footwear shopping mein help kar sakta hoon.",
            "search_product": "Theek hai, matching products dikha raha hoon.",
            "filter_size": "Theek hai, aapke size ke options dikha raha hoon.",
            "filter_brand": "Theek hai, selected brand ke options dikha raha hoon.",
            "filter_price": "Theek hai, budget ke andar options dikha raha hoon.",
            "add_to_cart": "Item cart mein add kar diya hai.",
            "remove_from_cart": "Item cart se hata diya hai.",
            "view_cart": "Yeh aapka cart hai.",
            "checkout": "Theek hai, checkout start kar raha hoon.",
            "select_payment_otp": "Theek hai, OTP bhej raha hoon. OTP manually enter kijiye.",
            "select_payment_wallet": "Theek hai, wallet payment process kar raha hoon.",
            "verify_otp": "OTP verify kar raha hoon.",
            "fallback": "Sorry, please dubara boliye.",
        }
        return mapping.get(intent, mapping["fallback"])

    if lang.startswith("kn"):
        mapping = {
            "greeting": "Namaskara, nanu footwear shopping alli help maduttene.",
            "search_product": "Sari, matching products torisuttene.",
            "filter_size": "Sari, nimma size options torisuttene.",
            "filter_brand": "Sari, selected brand options torisuttene.",
            "filter_price": "Sari, nimma budget olage options torisuttene.",
            "add_to_cart": "Item cart ge seriside.",
            "remove_from_cart": "Item cart inda tegedide.",
            "view_cart": "Idu nimma cart.",
            "checkout": "Sari, checkout start maduttene.",
            "select_payment_otp": "Sari, OTP kaluhisuttene. OTP manually hakki.",
            "select_payment_wallet": "Sari, wallet payment process maduttene.",
            "verify_otp": "OTP verify maduttene.",
            "fallback": "Kshamisi, dayavittu matte heli.",
        }
        return mapping.get(intent, mapping["fallback"])

    mapping = {
        "greeting": "Hi, I can help with footwear shopping.",
        "search_product": "Sure, here are matching products.",
        "filter_size": "Got it, showing your size options.",
        "filter_brand": "Got it, showing that brand.",
        "filter_price": "Got it, showing options in your budget.",
        "add_to_cart": "Item added to cart.",
        "remove_from_cart": "Item removed from cart.",
        "view_cart": "Here is your cart.",
        "checkout": "Proceeding to checkout.",
        "select_payment_otp": "Okay, sending OTP. Please enter OTP manually.",
        "select_payment_wallet": "Okay, processing wallet payment.",
        "verify_otp": "Verifying OTP.",
        "fallback": "Sorry, please say that again.",
    }
    return mapping.get(intent, mapping["fallback"])


def _extract_entities(text: str) -> dict[str, Any]:
    entities: dict[str, Any] = {}
    lowered = text.lower()

    # Prefer explicit size phrases: "size 10", "number 9"
    explicit_size = re.search(r"(?:size|saiz|saj|sai|number|no)\s*(\d{1,2})", lowered)
    if explicit_size:
        size_val = int(explicit_size.group(1))
        if 4 <= size_val <= 12:
            entities["size"] = size_val
    else:
        # Fallback: pick first standalone realistic footwear size
        for m in re.finditer(r"\b(\d{1,2})\b", lowered):
            size_val = int(m.group(1))
            if 4 <= size_val <= 12:
                entities["size"] = size_val
                break

    for brand in BRANDS:
        if brand in lowered:
            entities["brand"] = brand.title()
            break

    for color in COLORS:
        if color in lowered:
            entities["color"] = "gray" if color == "grey" else color
            break

    for hint, category in CATEGORY_HINTS.items():
        if hint in lowered:
            entities["category"] = category
            break

    under = re.search(r"(?:under|below|less than|<)\s*(\d+)", lowered)
    over = re.search(r"(?:above|over|more than|>)\s*(\d+)", lowered)
    between = re.search(r"(\d{3,6})\s*(?:-|to)\s*(\d{3,6})", lowered)
    if between:
        entities["price_range"] = f"{between.group(1)}-{between.group(2)}"
    elif under:
        entities["price_range"] = f"<{under.group(1)}"
    elif over:
        entities["price_range"] = f">{over.group(1)}"

    otp_match = re.search(r"\b(\d{6})\b", lowered)
    if otp_match:
        entities["otp"] = int(otp_match.group(1))

    name_match = re.search(
        r"(?:search(?: for)?|add)\s+([a-z0-9\s\-]{3,40}?)(?:\s+to\s+cart|\s+cart|\s+shoes|\s*$)",
        lowered,
    )
    if name_match:
        entities["name"] = name_match.group(1).strip()

    return entities


def extract_intent(text: str, language: str) -> dict[str, Any]:
    text = (text or "").strip()
    language = (language or "en").strip().lower()

    if not text:
        return {
            "intent": "fallback",
            "entities": {},
            "confidence": 0.0,
            "reply": _reply("fallback", language),
        }

    lowered = text.lower()
    entities = _extract_entities(text)
    intent = "fallback"
    confidence = 0.55

    if re.search(r"\b(hello|hi|hey|namaste|namaskara)\b", lowered):
        intent = "greeting"
        confidence = 0.95
    elif "otp" in entities:
        intent = "verify_otp"
        confidence = 0.95
    elif any(w in lowered for w in ["wallet", "upi", "gpay", "phonepe", "paytm", "वॉलेट", "वलेट", "ವಾಲೆಟ್"]):
        intent = "select_payment_wallet"
        confidence = 0.92
    elif any(w in lowered for w in ["otp payment", "pay by otp", "manual otp", "send otp", "ओटीपी", "otp भेज", "ಒಟಿಪಿ", "otp ಕಳುಹ"]):
        intent = "select_payment_otp"
        confidence = 0.92
    elif any(w in lowered for w in ["checkout", "buy now", "proceed to checkout", "payment", "pay", "bill", "kharido", "चेकआउट", "पेमेंट", "बाय", "खरीदो", "checkout करो", "ಚೆಕ್ಔಟ್", "ಪೇಮೆಂಟ್", "ಖರೀದಿ", "checkout madi", "ಮುಂದೆ checkout"]):
        intent = "checkout"
        confidence = 0.92
    elif any(w in lowered for w in ["view cart", "show cart", "my cart", "cart show", "open cart", "कार्ट", "कार्ट दिखा", "कार्ट दिखाओ", "कार्ट खोलो", "कार्ट दिखाओ भाई", "ಕಾರ್ಟ್", "ಕಾರ್ಟ್ ತೋರಿಸು", "ಕಾರ್ಟ್ ತೋರಿಸಿ", "ಕಾರ್ಟ್ ಓಪನ್"]):
        intent = "view_cart"
        confidence = 0.9
    elif any(w in lowered for w in ["remove", "delete", "hata", "tege", "drop from cart", "हटाओ", "निकालो", "ಕಾರ್ಟ್ಿಂದ ತೆಗೆಯು", "ತೆಗೆ", "ತೆಗೆದು"]):
        intent = "remove_from_cart"
        confidence = 0.9
    elif any(w in lowered for w in ["add to cart", "cart me", "cart ge", "add", "कार्ट में", "कार्ट मे", "कार्ट में डाल", "डालो", "डाल दो", "जोड़ो", "add madi", "ಕಾರ್ಟ್‌ಗೆ", "ಸೇರಿಸಿ", "ಹಾಕು", "ಕಾರ್ಟ್ ಗೆ ಸೇರಿಸಿ"]):
        intent = "add_to_cart"
        confidence = 0.9
    elif "price_range" in entities:
        intent = "filter_price"
        confidence = 0.88
    elif "brand" in entities:
        intent = "filter_brand"
        confidence = 0.88
    elif "size" in entities:
        intent = "filter_size"
        confidence = 0.88
    elif any(w in lowered for w in ["shoe", "shoes", "footwear", "sneaker", "chappal", "sandal", "जूते", "शूज", "फुटवेयर", "जूता", "ಶೂ", "ಶೂಸ್", "ಪಾದರಕ್ಷೆ", "ಚಪ್ಪಲ್"]):
        intent = "search_product"
        confidence = 0.9
    elif language.startswith(("hi", "kn")) and len(lowered.split()) <= 4:
        # short utterance in hi/kn is often an initial product search
        intent = "search_product"
        confidence = 0.7

    if intent not in SUPPORTED_INTENTS:
        intent = "fallback"
        confidence = 0.5

    return {
        "intent": intent,
        "entities": entities,
        "confidence": float(confidence),
        "reply": _reply(intent, language),
    }


