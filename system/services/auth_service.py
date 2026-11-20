from __future__ import annotations

from datetime import datetime

from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.user import User, UserRole
from system.auth.jwt import create_access_token

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def verify_password(self, plain: str, hashed: str) -> bool:
        return pwd_context.verify(plain, hashed)

    def hash_password(self, plain: str) -> str:
        return pwd_context.hash(plain)

    def login(self, username: str, password: str) -> dict:
        stmt = select(User).where(User.username == username)
        user = self.db.scalars(stmt).first()
        if not user or not user.is_active:
            raise ValueError("Geçersiz kullanıcı veya şifre")
        if not self.verify_password(password, user.password_hash):
            raise ValueError("Geçersiz kullanıcı veya şifre")

        role_code = None
        if user.role_id:
            role = self.db.get(UserRole, user.role_id)
            role_code = role.role_code if role else None

        user.last_login = datetime.now()
        self.db.commit()

        token = create_access_token(
            {
                "id": user.id,
                "username": user.username,
                "role_id": user.role_id,
                "role_code": role_code,
                "musteri_id": user.musteri_id,
            }
        )
        return {
            "token": token,
            "user": {
                "id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "role_code": role_code,
                "musteri_id": user.musteri_id,
            },
        }
