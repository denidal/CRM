from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from data.config.db import get_db
from system.services.radius_service import RadiusService

router = APIRouter()


class AttachRadiusBody(BaseModel):
    service_id: int
    radius_username: Optional[str] = None
    pop_id: Optional[int] = None


@router.get("/radius-users")
def list_radius_users(
    search: str = "",
    q: str = "",
    username: str | None = None,
    limit: int = Query(100, le=10000),
    unassigned: bool = False,
    db: Session = Depends(get_db),
):
    svc = RadiusService(db)
    if username:
        row = svc.get(username)
        return {"success": True, "data": [row] if row else []}
    term = search or q
    return {"success": True, "data": svc.search(q=term, limit=limit, unassigned_only=unassigned)}


@router.post("/radius-users/attach")
def attach_radius(body: AttachRadiusBody, db: Session = Depends(get_db)):
    try:
        sale = RadiusService(db).attach_to_service(body.service_id, body.radius_username, body.pop_id)
        return {"success": True, "service": sale}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/radius-attachments")
def list_attachments(customer_id: int | None = None, db: Session = Depends(get_db)):
    return {"success": True, "data": RadiusService(db).list_service_attachments(customer_id)}
