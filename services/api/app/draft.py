from __future__ import annotations

import json
import os
import re

import httpx

from app.detect import SENSOR_META
from app.explain import MODEL, XAI_URL, configured

DRAFT_MODEL = os.environ.get("XAI_DRAFT_MODEL", MODEL)
DRAFT_TIMEOUT_SECONDS = 25.0
SENSOR_NAMES = {name for name, _ in SENSOR_META.values()}

# Connectives and inspection verbs a reorder may add. Nouns and actions must come from the
# manual, a saved fix, or the evidence, so the model cannot introduce a part or a repair.
ALLOWED_WORDS = {
    "only", "first", "then", "both", "confirm", "check", "before", "after", "once",
    "when", "until", "unless", "high", "wear", "reading", "cheap", "step", "next",
    "same", "this", "that", "these", "those", "with", "from", "without", "still",
    "also", "agree", "rise", "above", "below", "baseline", "engine", "sensor", "value",
    "trend", "compare", "measure", "schedule", "book", "defer", "hold", "wing", "on-wing",
    "evidence", "direction", "signature", "manual", "section", "reviewed", "costly",
    "expensive", "quick", "inspect", "inspection", "read", "show", "keep", "move",
    "last", "while", "together", "point", "worth", "confirmed", "elevated", "drop",
    "come", "cheaper", "cheapest", "avoid", "need", "rule", "cost", "order", "early", "earlier",
}

_CACHE: dict[str, dict[str, object]] = {}


class DraftRejected(ValueError):
    pass


def draft_procedure(case: dict[str, object]) -> dict[str, object]:
    manual = case["manual"]
    assert isinstance(manual, dict)
    manual_steps = [str(step) for step in manual["steps"]]
    fallback = {
        "steps": [
            {"source": index + 1, "text": step, "sensors": [], "moved": False}
            for index, step in enumerate(manual_steps)
        ],
        "reason": None,
        "provider": "template",
        "model": None,
    }
    if not configured():
        return {**fallback, "trace": "No model key. The manual order stays; reorder it by hand."}
    key = _cache_key(case, manual_steps)
    cached = _CACHE.get(key)
    if cached:
        return cached
    feedback: str | None = None
    rejections: list[str] = []
    for _attempt in range(2):
        try:
            raw = _complete(case, manual_steps, feedback)
            result = validate_draft(raw, case, manual_steps)
        except DraftRejected as error:
            print(f"draft rejected: {error}")
            rejections.append(str(error))
            feedback = str(error)
            continue
        except httpx.HTTPStatusError as error:
            print(f"draft failed status={error.response.status_code}")
            return {**fallback, "trace": "The model call failed. The manual order stays."}
        except httpx.TimeoutException:
            print("draft failed timeout")
            return {**fallback, "trace": "The model timed out. The manual order stays."}
        except (httpx.HTTPError, ValueError) as error:
            print(f"draft failed {type(error).__name__}")
            return {**fallback, "trace": "The model call failed. The manual order stays."}
        checks = f"{len(manual_steps)} steps trace to manual {manual['id']}. Sensors only from the evidence. No new parts or actions."
        prefix = f"Rejected once: {rejections[0]} " if rejections else ""
        payload = {
            **result,
            "provider": "xai",
            "model": DRAFT_MODEL,
            "trace": f"{prefix}Checked: {checks}",
        }
        _CACHE[key] = payload
        if len(_CACHE) > 64:
            _CACHE.pop(next(iter(_CACHE)))
        return payload
    return {**fallback, "trace": f"Both drafts failed the check ({rejections[-1]}). The manual order stays."}


def validate_draft(raw: str, case: dict[str, object], manual_steps: list[str]) -> dict[str, object]:
    try:
        body = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as error:
        raise DraftRejected("The draft was not JSON.") from error
    steps = body.get("steps") if isinstance(body, dict) else None
    if not isinstance(steps, list):
        raise DraftRejected("The draft had no steps.")
    if len(steps) != len(manual_steps):
        raise DraftRejected(f"The draft had {len(steps)} steps; the manual has {len(manual_steps)}.")

    evidence_names = _evidence_names(case)
    vocabulary = _vocabulary(case, manual_steps)
    seen: set[int] = set()
    cleaned: list[dict[str, object]] = []
    for position, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise DraftRejected("A step was not an object.")
        source = step.get("source")
        text = str(step.get("text", "")).strip()
        if not isinstance(source, int) or not 1 <= source <= len(manual_steps):
            raise DraftRejected(f"Step {position} does not cite a manual step.")
        if source in seen:
            raise DraftRejected(f"Manual step {source} was used twice.")
        seen.add(source)
        if not text or len(text) > 220:
            raise DraftRejected(f"Step {position} is empty or too long.")
        _check_text(text, evidence_names, vocabulary, f"Step {position}")
        sensors = [str(name) for name in step.get("sensors", []) if isinstance(name, str)]
        stray = [name for name in sensors if name not in evidence_names]
        if stray:
            raise DraftRejected(f"Step {position} cites {', '.join(stray)}, which is not in the evidence.")
        cleaned.append({"source": source, "text": text, "sensors": sensors, "moved": source != position})

    reason = body.get("reason") if isinstance(body, dict) else None
    checked_reason: str | None = None
    if isinstance(reason, str) and reason.strip():
        try:
            _check_text(reason.strip()[:240], evidence_names, vocabulary, "The reason")
            checked_reason = reason.strip()[:240]
        except DraftRejected:
            checked_reason = None
    return {"steps": cleaned, "reason": checked_reason}


def _check_text(text: str, evidence_names: set[str], vocabulary: set[str], label: str) -> None:
    for number in re.findall(r"(?<![A-Za-z0-9.])\d+(?:\.\d+)?", text):
        if number not in vocabulary:
            raise DraftRejected(f"{label} adds the number {number}, which is not in the manual.")
    for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", text):
        if token in SENSOR_NAMES and token not in evidence_names:
            raise DraftRejected(f"{label} names {token}, which did not move on this engine.")
        if token in SENSOR_NAMES or len(token) < 4:
            continue
        word = _normal(token)
        if word not in vocabulary:
            raise DraftRejected(f"{label} adds '{token}', which is not in the manual or the evidence.")


def _vocabulary(case: dict[str, object], manual_steps: list[str]) -> set[str]:
    manual = case["manual"]
    assert isinstance(manual, dict)
    sources = [*manual_steps, str(manual.get("title", ""))]
    shop = case.get("shopMemory")
    if isinstance(shop, dict):
        sources.extend(str(step) for step in shop.get("steps", []))
    for sensor in case.get("evidence", []) or []:
        if isinstance(sensor, dict):
            sources.append(str(sensor.get("description", "")))
    words = {_normal(token) for text in sources for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", text)}
    numbers = {number for text in sources for number in re.findall(r"\d+(?:\.\d+)?", text)}
    numbers.add(str(manual.get("id", "")))
    return words | numbers | {_normal(word) for word in ALLOWED_WORDS}


def _evidence_names(case: dict[str, object]) -> set[str]:
    return {
        str(sensor.get("name"))
        for sensor in case.get("evidence", []) or []
        if isinstance(sensor, dict) and sensor.get("direction") in {"high", "low"}
    }


def _normal(token: str) -> str:
    word = token.lower()
    changed = True
    while changed:
        changed = False
        for suffix in ("ing", "ed", "es", "s"):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[: -len(suffix)]
                changed = True
                break
    return word


def _complete(case: dict[str, object], manual_steps: list[str], feedback: str | None) -> str:
    key = os.environ.get("XAI_API_KEY", "").strip()
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": _user_prompt(case, manual_steps)},
    ]
    if feedback:
        messages.append({"role": "user", "content": f"The server rejected your last draft: {feedback} Try again under the same rules."})
    response = httpx.post(
        XAI_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": DRAFT_MODEL,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": messages,
        },
        timeout=DRAFT_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    choices = response.json().get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("empty completion")
    message = choices[0].get("message", {})
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        raise ValueError("missing content")
    return content


def _user_prompt(case: dict[str, object], manual_steps: list[str]) -> str:
    manual = case["manual"]
    assert isinstance(manual, dict)
    numbered = "\n".join(f"{index}. {step}" for index, step in enumerate(manual_steps, start=1))
    evidence = "\n".join(
        f"- {sensor['name']} ({sensor['description']}) {sensor['direction']}, {sensor['zScore']} sigma"
        for sensor in case.get("evidence", []) or []
        if isinstance(sensor, dict) and sensor.get("direction") in {"high", "low"}
    )
    shop = case.get("shopMemory")
    shop_text = "None."
    if isinstance(shop, dict):
        shop_steps = "; ".join(str(step) for step in shop.get("steps", []))
        shop_text = f"Engine {shop.get('unitId')}, resolved {shop.get('resolved')}: {shop_steps}"
    return (
        f"Manual section {manual['id']} {manual['title']}:\n{numbered}\n\n"
        f"Evidence on this engine:\n{evidence or '- none'}\n\n"
        f"Reviewed fix on a matching engine: {shop_text}"
    )


def _cache_key(case: dict[str, object], manual_steps: list[str]) -> str:
    shop = case.get("shopMemory")
    shop_id = shop.get("unitId") if isinstance(shop, dict) else "none"
    return f"{case.get('unitId')}:{case.get('cycle')}:{shop_id}:{'|'.join(manual_steps)}"


def _strip_fences(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(line for line in cleaned.splitlines() if not line.startswith("```"))
    return cleaned.strip()


_SYSTEM = (
    "You reorder a maintenance procedure so the cheapest check that the evidence supports comes first. "
    "Use every manual step exactly once. Put the most expensive step last and make it conditional, "
    "for example 'only if the earlier readings confirm wear'. You may reword a step only to change its "
    "order or condition. Do not add parts, tools, repairs, causes, numbers, or sensors that are not in "
    "the evidence. Write the reason with words from the manual and the evidence only, for example "
    "'The coolant bleed check is cheap and can confirm wear before a borescope.' Return JSON only: "
    '{"steps": [{"source": <manual step number>, "text": "<step>", "sensors": ["<sensor name>"]}], '
    '"reason": "<one sentence>"}'
)
