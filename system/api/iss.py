from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data.config.db import get_db
from data.repositories.iss_repo import IssRepository

router = APIRouter()


@router.get("/iss-aboneler")
def list_iss(musteri_id: int | None = None, db: Session = Depends(get_db)):
    if not musteri_id:
        return {"success": True, "data": []}
    rows = IssRepository(db).list_by_customer(musteri_id)
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "HAT_NO": r.HAT_NO,
                "HAT_DURUM": r.HAT_DURUM,
                "HIZMET_TIPI": r.HIZMET_TIPI,
                "ISS_POP_BILGISI": r.ISS_POP_BILGISI,
                "ISS_KULLANICI_ADI": r.ISS_KULLANICI_ADI,
                "ABONE_TARIFE": r.ABONE_TARIFE,
                "service_sale_id": r.service_sale_id,
            }
            for r in rows
        ],
    }
