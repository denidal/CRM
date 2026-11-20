from __future__ import annotations

from typing import Any, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from data.config.db import get_db
from data.models.user import User, UserRole
from system.auth.jwt import decode_token

security = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> dict[str, Any] | None:
    token = None
    if creds:
        token = creds.credentials
    if not token:
        token = request.cookies.get("auth_token")
    if not token:
        token = request.headers.get("x-auth-token")
    if not token:
        return None
    try:
        payload = decode_token(token)
    except Exception:  # noqa: BLE001
        return None
    user = db.get(User, payload.get("id"))
    if not user or not user.is_active:
        return None
    role_code = payload.get("role_code")
    if user.role_id and not role_code:
        role = db.get(UserRole, user.role_id)
        role_code = role.role_code if role else None
    return {
        "id": user.id,
        "username": user.username,
        "role_id": user.role_id,
        "role_code": role_code,
        "musteri_id": user.musteri_id,
    }


def require_auth(user: dict | None = Depends(get_current_user)) -> dict:
    if not user:
        raise HTTPException(status_code=401, detail="Oturum gerekli")
    return user
