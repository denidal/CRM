"""Customer persistence — identity + addresses + services."""

from __future__ import annotations

from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from data.models.customer import Customer
from data.models.customer_address import CustomerAddress
from data.models.service_sale import ServiceSale


class CustomerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _opts(self, *, include_services: bool, include_addresses: bool):
        opts = []
        if include_services:
            opts.append(selectinload(Customer.service_sales).selectinload(ServiceSale.pop))
        if include_addresses:
            opts.append(selectinload(Customer.addresses))
        return opts

    def list(
        self,
        *,
        q: str | None = None,
        durum: str | None = None,
        include_services: bool = True,
        include_addresses: bool = True,
    ) -> list[Customer]:
        stmt = select(Customer).options(
            *self._opts(include_services=include_services, include_addresses=include_addresses)
        )
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(
                    Customer.otel_adi.like(like),
                    Customer.firma_unvan.like(like),
                    Customer.musteri_no.like(like),
                    Customer.yetkili_adi.like(like),
                    Customer.yetkili_soyadi.like(like),
                    Customer.irtibat_yetkili_telefon.like(like),
                    Customer.irtibat_yetkili_email.like(like),
                )
            )
        if durum:
            stmt = stmt.where(Customer.durum == durum)
        stmt = stmt.order_by(Customer.id.asc())
        return list(self.db.scalars(stmt).all())

    def get(
        self,
        customer_id: int,
        *,
        include_services: bool = True,
        include_addresses: bool = True,
    ) -> Customer | None:
        stmt = (
            select(Customer)
            .where(Customer.id == customer_id)
            .options(
                *self._opts(
                    include_services=include_services, include_addresses=include_addresses
                )
            )
        )
        return self.db.scalars(stmt).first()

    def create(self, data: dict[str, Any]) -> Customer:
        customer = Customer(**data)
        self.db.add(customer)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def update(self, customer_id: int, data: dict[str, Any]) -> Customer | None:
        customer = self.get(customer_id, include_services=False, include_addresses=False)
        if not customer:
            return None
        for key, value in data.items():
            if hasattr(customer, key) and key != "id":
                setattr(customer, key, value)
        self.db.commit()
        self.db.refresh(customer)
        return customer

    def archive(self, customer_id: int) -> Customer | None:
        return self.update(customer_id, {"durum": "arsiv"})

    def restore(self, customer_id: int) -> Customer | None:
        return self.update(customer_id, {"durum": "aktif"})

    def add_address(self, customer_id: int, data: dict[str, Any]) -> CustomerAddress:
        if data.get("is_primary"):
            self._clear_primary(customer_id)
        addr = CustomerAddress(customer_id=customer_id, **data)
        self.db.add(addr)
        self.db.commit()
        self.db.refresh(addr)
        return addr

    def update_address(self, address_id: int, data: dict[str, Any]) -> CustomerAddress | None:
        addr = self.db.get(CustomerAddress, address_id)
        if not addr:
            return None
        if data.get("is_primary"):
            self._clear_primary(addr.customer_id)
        for key, value in data.items():
            if hasattr(addr, key) and key not in {"id", "customer_id"}:
                setattr(addr, key, value)
        self.db.commit()
        self.db.refresh(addr)
        return addr

    def delete_address(self, address_id: int) -> bool:
        addr = self.db.get(CustomerAddress, address_id)
        if not addr:
            return False
        self.db.delete(addr)
        self.db.commit()
        return True

    def _clear_primary(self, customer_id: int) -> None:
        for a in self.db.scalars(
            select(CustomerAddress).where(CustomerAddress.customer_id == customer_id)
        ).all():
            a.is_primary = False
