from __future__ import annotations

import hashlib
import hmac
import os
import time

from fastapi import Header, HTTPException

from app.store import member_from_token, open_member, shop_id

DEFAULT_PASSPHRASE = "sample-shop"
SHOP_NAME = os.environ.get("SHOP_NAME", "Sample fleet")
_HITS: dict[int, list[float]] = {}


def shop_passphrase() -> str:
    return os.environ.get("SHOP_PASSPHRASE", DEFAULT_PASSPHRASE)


def passphrase_hint() -> str | None:
    if os.environ.get("SHOP_PASSPHRASE_HINT") == "1":
        return shop_passphrase()
    return None


def sign_in(name: str, passphrase: str) -> dict[str, object]:
    expected = hashlib.sha256(shop_passphrase().encode()).hexdigest()
    given = hashlib.sha256(passphrase.encode()).hexdigest()
    if not hmac.compare_digest(given, expected):
        raise ValueError("That shop passphrase is wrong.")
    member = open_member(name)
    return {
        "shop": os.environ.get("SHOP_NAME", SHOP_NAME),
        "shopId": shop_id(),
        "name": member["name"],
        "token": member["token"],
    }


def require_member(authorization: str | None = Header(default=None)) -> dict[str, object]:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sign in to the shop.")
    member = member_from_token(authorization.removeprefix("Bearer ").strip())
    if member is None:
        raise HTTPException(status_code=401, detail="Sign in to the shop.")
    return member


def allow_summary(member_id: int) -> bool:
    now = time.monotonic()
    hits = [stamp for stamp in _HITS.get(member_id, []) if now - stamp < 3600]
    recent = [stamp for stamp in hits if now - stamp < 60]
    if len(recent) >= 30 or len(hits) >= 200:
        _HITS[member_id] = hits
        return False
    hits.append(now)
    _HITS[member_id] = hits
    return True
