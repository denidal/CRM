"""RADIUS DB queries (rm_users) + service_sale attachments in app DB."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.config.db import get_radius_engine
from data.models.radius import RadiusUserView
from data.models.service_sale import ServiceSale


class RadiusRepository:
    def search(self, q: str = "", limit: int = 100, unassigned_only: bool = False) -> list[RadiusUserView]:
        sql = (
            "SELECT username, staticipcm, staticipcpe, email, company, hat_no, srvid "
            "FROM rm_users"
        )
        params: dict[str, Any] = {"limit": int(limit)}
        clauses: list[str] = []
        if q.strip():
            clauses.append(
                "(username LIKE :q OR company LIKE :q OR email LIKE :q OR hat_no LIKE :q)"
            )
            params["q"] = f"%{q.strip()}%"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY username LIMIT :limit"
        with get_radius_engine().connect() as conn:
            rows = conn.execute(text(sql), params).mappings().all()
        users = [RadiusUserView(**{k: r.get(k) for k in RadiusUserView.__dataclass_fields__}) for r in rows]
        if unassigned_only:
            assigned = self.assigned_usernames()
            users = [u for u in users if u.username not in assigned]
        return users

    def get(self, username: str) -> RadiusUserView | None:
        with get_radius_engine().connect() as conn:
            row = conn.execute(
                text(
                    "SELECT username, staticipcm, staticipcpe, email, company, hat_no, srvid "
                    "FROM rm_users WHERE username = :u LIMIT 1"
                ),
                {"u": username},
            ).mappings().first()
        return RadiusUserView(**dict(row)) if row else None

    def assigned_usernames(self) -> set[str]:
        """Usernames currently linked on service_sales."""
        from sqlalchemy import select

        from data.config.db import SessionLocal

        db = SessionLocal()
        try:
            rows = db.scalars(
                select(ServiceSale.radius_username).where(
                    ServiceSale.radius_username.is_not(None)
                )
            ).all()
            return {str(r) for r in rows if r}
        finally:
            db.close()

    def attach_to_service(
        self, db: Session, service_id: int, username: str | None, pop_id: int | None = None
    ) -> ServiceSale | None:
        sale = db.get(ServiceSale, service_id)
        if not sale:
            return None
        sale.radius_username = username
        if pop_id is not None:
            sale.pop_id = pop_id
        db.commit()
        db.refresh(sale)
        return sale
