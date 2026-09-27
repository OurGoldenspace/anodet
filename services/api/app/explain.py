from __future__ import annotations

import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

XAI_URL = "https://api.x.ai/v1/chat/completions"
MODEL = os.environ.get("XAI_MODEL", "grok-4")
TIMEOUT_SECONDS = 15.0
_CACHE: dict[str, str] = {}


def configured() -> bool:
    return bool(os.environ.get("XAI_API_KEY", "").strip())


def explain_summary(facts: dict[str, object], template: str) -> dict[str, object]:
    trace = _trace(facts)
    if not configured():
        return {"summary": template, "provider": "template", "model": None, "trace": trace}
    cache_key = _cache_key(facts, template)
    cached = _CACHE.get(cache_key)
    if cached:
        return {"summary": cached, "provider": "xai", "model": MODEL, "trace": trace}
    try:
        text = _complete(facts, template)
    except httpx.HTTPStatusError as error:
        print(f"summary failed status={error.response.status_code}")
        return {"summary": template, "provider": "template", "model": None, "trace": trace}
    except httpx.TimeoutException:
        print("summary failed timeout")
        return {"summary": template, "provider": "template", "model": None, "trace": trace}
    except (httpx.HTTPError, TimeoutError, ValueError) as error:
        print(f"summary failed {type(error).__name__}")
        return {"summary": template, "provider": "template", "model": None, "trace": trace}
    if not text:
        return {"summary": template, "provider": "template", "model": None, "trace": trace}
    _CACHE[cache_key] = text
    if len(_CACHE) > 64:
        _CACHE.pop(next(iter(_CACHE)))
    return {"summary": text, "provider": "xai", "model": MODEL, "trace": trace}


def _complete(facts: dict[str, object], template: str) -> str:
    key = os.environ.get("XAI_API_KEY", "").strip()
    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You write the summary paragraph for a maintenance case. "
                    "Use only the facts given. Two or three sentences. "
                    "Name the sensors and whether each is high or low. "
                    "Name the manual section. "
                    "If a reviewed fix from another engine is present, lead with that engine. "
                    "Do not invent steps, causes, percentages, or remaining life. "
                    "Do not output a procedure list."
                ),
            },
            {"role": "user", "content": _user_prompt(facts, template)},
        ],
    }
    response = httpx.post(
        XAI_URL,
        headers={"Authorization": f"Bearer {key}"},
        json=payload,
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("empty completion")
    message = choices[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError("missing content")
    return _clean(content)


def _user_prompt(facts: dict[str, object], template: str) -> str:
    signature = facts.get("signature")
    marks = signature if isinstance(signature, list) else []
    moved = ", ".join(
        f"{mark.get('name')} {mark.get('direction')}"
        for mark in marks
        if isinstance(mark, dict)
    )
    shop = facts.get("shop")
    shop_line = "No reviewed fix for this signature."
    if isinstance(shop, dict):
        shop_line = (
            f"Reviewed fix from Engine {shop.get('unitId')} by {shop.get('author') or 'the shop'}. "
            f"{shop.get('sharedText')} Resolved: {shop.get('resolved')}."
        )
    return (
        f"Engine {facts.get('unitId')} cycle {facts.get('cycle')} stage {facts.get('stage')}.\n"
        f"Evidence: {facts.get('whatHappened')}\n"
        f"Signature: {moved}.\n"
        f"Manual: section {facts.get('manualId')} {facts.get('manualTitle')}.\n"
        f"Shop memory: {shop_line}\n"
        f"Template you may tighten, without adding facts: {template}"
    )


def _trace(facts: dict[str, object]) -> str:
    manual_id = facts.get("manualId") or "manual"
    shop = "Read shop memory." if isinstance(facts.get("shop"), dict) else "No shop memory yet."
    return f"Read sensors. Read manual {manual_id}. {shop}"


def _cache_key(facts: dict[str, object], template: str) -> str:
    shop = facts.get("shop")
    shop_id = shop.get("unitId") if isinstance(shop, dict) else "none"
    return f"{facts.get('unitId')}:{facts.get('cycle')}:{shop_id}:{template}"


def _clean(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.startswith("```")]
        cleaned = "\n".join(lines).strip()
    if len(cleaned) > 700:
        cleaned = cleaned[:700].rsplit(" ", 1)[0]
    return cleaned
