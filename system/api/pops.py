from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from data.config.db import get_db
from data.repositories.pop_repo import PopRepository

router = APIRouter()


class PopBody(BaseModel):
    pop_kodu: str
    pop_adi: str
    lokasyon: Optional[str] = None
    adres: Optional[str] = None
    il: Optional[str] = None
    ilce: Optional[str] = None
    pop_tipi: Optional[str] = None
    ip_blok: Optional[str] = None
    kapasite: Optional[str] = None
    durum: str = "aktif"
    aciklama: Optional[str] = None


@router.get("/pops")
def list_pops(db: Session = Depends(get_db)):
    rows = PopRepository(db).list()
    return {
        "success": True,
        "data": [
            {
                "id": p.id,
                "pop_kodu": p.pop_kodu,
                "pop_adi": p.pop_adi,
                "lokasyon": p.lokasyon,
                "il": p.il,
                "ilce": p.ilce,
                "durum": p.durum,
            }
            for p in rows
        ],
    }


@router.post("/pops")
def create_pop(body: PopBody, db: Session = Depends(get_db)):
    try:
        pop = PopRepository(db).create(body.model_dump())
        return {"success": True, "data": {"id": pop.id, "pop_kodu": pop.pop_kodu}}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
