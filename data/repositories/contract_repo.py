from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from data.models.contract import HotspotContract, InterfiberContract, InternetContract


class ContractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_internet(self, customer_id: int | None = None):
        stmt = select(InternetContract).order_by(InternetContract.id.desc())
        if customer_id:
            stmt = stmt.where(InternetContract.customer_id == customer_id)
        return list(self.db.scalars(stmt).all())

    def list_hotspot(self, customer_id: int | None = None):
        stmt = select(HotspotContract).order_by(HotspotContract.id.desc())
        if customer_id:
            stmt = stmt.where(HotspotContract.customer_id == customer_id)
        return list(self.db.scalars(stmt).all())

    def list_interfiber(self, customer_id: int | None = None):
        stmt = select(InterfiberContract).order_by(InterfiberContract.id.desc())
        if customer_id:
            stmt = stmt.where(InterfiberContract.customer_id == customer_id)
        return list(self.db.scalars(stmt).all())
