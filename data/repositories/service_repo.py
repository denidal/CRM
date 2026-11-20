"""ServiceSale repository — always scoped under customer_id."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from data.models.service_sale import ServiceSale


class ServiceSaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_customer(self, customer_id: int) -> list[ServiceSale]:
        stmt = (
            select(ServiceSale)
            .where(ServiceSale.customer_id == customer_id)
            .options(selectinload(ServiceSale.pop))
            .order_by(ServiceSale.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def get(self, service_id: int) -> ServiceSale | None:
        stmt = (
            select(ServiceSale)
            .where(ServiceSale.id == service_id)
            .options(selectinload(ServiceSale.pop))
        )
        return self.db.scalars(stmt).first()

    def create(self, data: dict[str, Any]) -> ServiceSale:
        if "customer_id" not in data:
            raise ValueError("customer_id zorunludur")
        sale = ServiceSale(**data)
        self.db.add(sale)
        self.db.commit()
        self.db.refresh(sale)
        return sale

    def update(self, service_id: int, data: dict[str, Any]) -> ServiceSale | None:
        sale = self.get(service_id)
        if not sale:
            return None
        for key, value in data.items():
            if hasattr(sale, key) and key not in {"id", "customer_id"}:
                setattr(sale, key, value)
        self.db.commit()
        self.db.refresh(sale)
        return sale

    def attach_pop(self, service_id: int, pop_id: int | None) -> ServiceSale | None:
        return self.update(service_id, {"pop_id": pop_id})

    def attach_radius(self, service_id: int, username: str | None) -> ServiceSale | None:
        return self.update(service_id, {"radius_username": username})

    def soft_cancel(self, service_id: int) -> ServiceSale | None:
        return self.update(service_id, {"status": "cancelled"})

    def delete(self, service_id: int) -> bool:
        sale = self.get(service_id)
        if not sale:
            return False
        self.db.delete(sale)
        self.db.commit()
        return True

    def existing_hat_nos(self) -> set[str]:
        rows = self.db.scalars(select(ServiceSale.hat_no).where(ServiceSale.hat_no.is_not(None))).all()
        return {str(h) for h in rows if h}
