from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

ALGORITHM = "HS256"


def _secret() -> str:
    return os.getenv("JWT_SECRET", "change-me")


def create_access_token(payload: dict[str, Any], hours: int | None = None) -> str:
    expire_hours = hours or int(os.getenv("JWT_EXPIRE_HOURS", "24"))
    data = dict(payload)
    data["exp"] = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    return jwt.encode(data, _secret(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
