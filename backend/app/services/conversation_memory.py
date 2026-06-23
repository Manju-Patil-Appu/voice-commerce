import json
from typing import Any

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None

from app.core.config import settings

_MEMORY: dict[int, dict[str, Any]] = {}


def _default_memory() -> dict[str, Any]:
    return {
        "last_intent": None,
        "last_entities": {},
        "last_products_shown": [],
        "last_5_messages": [],
    }


def _get_redis_client():
    if not settings.REDIS_URL:
        return None
    if redis is None:
        return None
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _save_memory(user_id: int, mem: dict[str, Any]) -> None:
    client = _get_redis_client()
    if client:
        client.set(f"mem:{user_id}", json.dumps(mem, ensure_ascii=False))
    else:
        _MEMORY[user_id] = mem


def get_memory(user_id: int) -> dict[str, Any]:
    client = _get_redis_client()
    if client:
        raw = client.get(f"mem:{user_id}")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                return _default_memory()
        return _default_memory()

    return _MEMORY.get(user_id, _default_memory())


def update_memory(user_id: int, intent_data: dict, execution_result: dict) -> dict[str, Any]:
    mem = get_memory(user_id)

    mem["last_intent"] = intent_data.get("intent")
    mem["last_entities"] = intent_data.get("entities", {}) or {}

    if "items" in execution_result:
        mem["last_products_shown"] = execution_result.get("items", [])

    messages = mem.get("last_5_messages", [])
    user_text = intent_data.get("text")
    reply_text = intent_data.get("reply")
    if user_text:
        messages.append({"role": "user", "text": user_text})
    if reply_text:
        messages.append({"role": "assistant", "text": reply_text})
    mem["last_5_messages"] = messages[-5:]

    _save_memory(user_id, mem)

    return mem


def patch_memory(user_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    mem = get_memory(user_id)
    mem.update(updates or {})
    _save_memory(user_id, mem)
    return mem


def clear_memory(user_id: int) -> None:
    client = _get_redis_client()
    if client:
        client.delete(f"mem:{user_id}")
        return
    if user_id in _MEMORY:
        del _MEMORY[user_id]
