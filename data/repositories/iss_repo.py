from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.btk import BtkAboneRehber


class IssRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_customer(self, musteri_id: int) -> list[BtkAboneRehber]:
        stmt = (
            select(BtkAboneRehber)
            .where(BtkAboneRehber.MUSTERI_ID == musteri_id)
            .order_by(BtkAboneRehber.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def list_all(self, *, limit: int = 200) -> list[BtkAboneRehber]:
        stmt = select(BtkAboneRehber).order_by(BtkAboneRehber.id.desc()).limit(limit)
        return list(self.db.scalars(stmt).all())

    def get_by_hat_no(self, hat_no: str) -> BtkAboneRehber | None:
        stmt = select(BtkAboneRehber).where(BtkAboneRehber.HAT_NO == hat_no)
        return self.db.scalars(stmt).first()

    def existing_hat_nos(self) -> set[str]:
        rows = self.db.scalars(
            select(BtkAboneRehber.HAT_NO).where(BtkAboneRehber.HAT_NO.is_not(None))
        ).all()
        return {str(h) for h in rows if h}

    def create(self, data: dict[str, Any]) -> BtkAboneRehber:
        row = BtkAboneRehber(**data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
