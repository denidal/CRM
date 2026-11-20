from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from data.config.db import get_db
from system.services.auth_service import AuthService

router = APIRouter(prefix="/auth")


class LoginBody(BaseModel):
    username: str
    password: str


@router.post("/login")
def login(body: LoginBody, db: Session = Depends(get_db)):
    try:
        result = AuthService(db).login(body.username, body.password)
        return {"success": True, **result}
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout")
def logout():
    return {"success": True}
