from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.pop import Pop


class PopRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list(self, *, only_active: bool = False) -> list[Pop]:
        stmt = select(Pop).order_by(Pop.pop_kodu.asc())
        if only_active:
            stmt = stmt.where(Pop.durum == "aktif")
        return list(self.db.scalars(stmt).all())

    def get(self, pop_id: int) -> Pop | None:
        return self.db.get(Pop, pop_id)

    def create(self, data: dict[str, Any]) -> Pop:
        if not data.get("pop_kodu") or not data.get("pop_adi"):
            raise ValueError("pop_kodu ve pop_adi zorunludur")
        pop = Pop(**data)
        self.db.add(pop)
        self.db.commit()
        self.db.refresh(pop)
        return pop

    def update(self, pop_id: int, data: dict[str, Any]) -> Pop | None:
        pop = self.get(pop_id)
        if not pop:
            return None
        for key, value in data.items():
            if hasattr(pop, key) and key != "id":
                setattr(pop, key, value)
        self.db.commit()
        self.db.refresh(pop)
        return pop
