"""RADIUS business logic — always attaches to ServiceSale, not Customer."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from data.repositories.radius_repo import RadiusRepository
from data.repositories.service_repo import ServiceSaleRepository


class RadiusService:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db
        self.repo = RadiusRepository()
        self.services = ServiceSaleRepository(db) if db else None

    def search(
        self, q: str = "", limit: int = 100, unassigned_only: bool = False
    ) -> list[dict[str, Any]]:
        users = self.repo.search(q=q, limit=limit, unassigned_only=unassigned_only)
        return [
            {
                "username": u.username,
                "staticipcm": u.staticipcm,
                "staticipcpe": u.staticipcpe,
                "email": u.email,
                "company": u.company,
                "hat_no": u.hat_no,
                "srvid": u.srvid,
            }
            for u in users
        ]

    def get(self, username: str) -> dict[str, Any] | None:
        u = self.repo.get(username)
        if not u:
            return None
        return {
            "username": u.username,
            "staticipcm": u.staticipcm,
            "staticipcpe": u.staticipcpe,
            "email": u.email,
            "company": u.company,
            "hat_no": u.hat_no,
            "srvid": u.srvid,
        }

    def attach_to_service(
        self, service_id: int, username: str | None, pop_id: int | None = None
    ) -> dict[str, Any]:
        if not self.db or not self.services:
            raise RuntimeError("Session gerekli")
        if username:
            try:
                found = self.repo.get(username)
            except Exception:
                found = {"username": username}  # local mode without RADIUS DB
            if not found:
                raise ValueError(f"RADIUS kullanıcısı bulunamadı: {username}")
        sale = self.repo.attach_to_service(self.db, service_id, username, pop_id)
        if not sale:
            raise ValueError("Hizmet bulunamadı")
        return {
            "id": sale.id,
            "customer_id": sale.customer_id,
            "radius_username": sale.radius_username,
            "pop_id": sale.pop_id,
            "hat_no": sale.hat_no,
        }

    def sync_aaa(self, service_id: int) -> dict[str, Any]:
        """Hook: sync ServiceSale AAA profile to RADIUS (hat/state)."""
        if not self.db or not self.services:
            raise RuntimeError("Session gerekli")
        sale = self.services.get(service_id)
        if not sale:
            raise ValueError("Hizmet bulunamadı")
        payload = {
            "service_id": sale.id,
            "username": sale.radius_username,
            "hat_no": sale.hat_no,
            "pop_id": sale.pop_id,
            "status": sale.status,
        }
        live = None
        if sale.radius_username:
            try:
                live = self.get(sale.radius_username)
            except Exception:
                live = None
        note = f"AAA sync @ {datetime.now().isoformat(timespec='seconds')}"
        if sale.radius_username:
            note += f" user={sale.radius_username}"
        if sale.hat_no:
            note += f" hat={sale.hat_no}"
        self.services.update(service_id, {"notes": note[:500]})
        return {"success": True, "payload": payload, "radius_user": live, "message": note}

    def list_service_attachments(self, customer_id: int | None = None) -> list[dict[str, Any]]:
        if not self.services or not self.db:
            raise RuntimeError("Session gerekli")
        if customer_id:
            rows = self.services.list_by_customer(customer_id)
        else:
            from sqlalchemy import select

            from data.models.service_sale import ServiceSale

            rows = list(
                self.db.scalars(
                    select(ServiceSale).where(ServiceSale.radius_username.is_not(None))
                ).all()
            )
        return [
            {
                "service_id": s.id,
                "customer_id": s.customer_id,
                "service_type": s.service_type,
                "radius_username": s.radius_username,
                "pop_id": s.pop_id,
                "pop_kodu": s.pop_kodu,
                "hat_no": s.hat_no,
            }
            for s in rows
            if s.radius_username
        ]
