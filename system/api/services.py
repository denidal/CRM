from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from data.config.db import get_db
from system.services.abone_service import AboneService
from system.services.service_sale_service import ServiceSaleService

router = APIRouter()


class AddServiceBody(BaseModel):
    customer_id: int
    service_type: str
    fiyat: Optional[float] = None
    tutar: Optional[float] = None
    para_birimi: str = "TL"
    internet_hiz: Optional[str] = None
    paket_adi: Optional[str] = None
    sozlesme_suresi: Optional[str] = None
    sozlesme_tarihi: Optional[str] = None
    sozlesme_baslangic_tarihi: Optional[str] = None
    sozlesme_bitis_tarihi: Optional[str] = None
    sozlesme_no: Optional[str] = None
    pop_id: Optional[int] = None
    radius_username: Optional[str] = None
    hat_no: Optional[str] = None
    hizmet_tipi: Optional[str] = None


class AttachBody(BaseModel):
    pop_id: Optional[int] = None
    radius_username: Optional[str] = None


class AboneBody(BaseModel):
    customer_id: int
    hizmet_tipi: str
    paket: str
    fiyat: float
    para_birimi: str = "TL"
    hat_no: Optional[str] = None
    abone_baslangic: Optional[str] = None
    pop_id: Optional[int] = Field(
        default=None, description="Opsiyonel — zorunlu değil"
    )
    radius_username: Optional[str] = Field(
        default=None, description="Opsiyonel — zorunlu değil"
    )
    skip_validation: bool = False
    service_type: str = "internet"


def _sale_dict(s) -> dict[str, Any]:
    return {
        "id": s.id,
        "customer_id": s.customer_id,
        "service_type": s.service_type,
        "status": s.status,
        "pop_id": s.pop_id,
        "pop_kodu": s.pop_kodu,
        "radius_username": s.radius_username,
        "hat_no": s.hat_no,
        "paket_adi": s.paket_adi,
        "internet_hiz": s.internet_hiz,
        "fiyat": float(s.fiyat) if s.fiyat is not None else None,
        "para_birimi": s.para_birimi,
        "sozlesme_no": s.sozlesme_no,
        "sozlesme_bitis_tarihi": (
            s.sozlesme_bitis_tarihi.isoformat() if s.sozlesme_bitis_tarihi else None
        ),
        "hizmet_tipi": s.hizmet_tipi,
    }


@router.post("/services")
def add_service(body: AddServiceBody, db: Session = Depends(get_db)):
    try:
        sale = ServiceSaleService(db).add_service(body.customer_id, body.model_dump())
        return {"success": True, "message": "Hizmet eklendi", "service": _sale_dict(sale)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.patch("/services/{service_id}")
def update_service(service_id: int, body: AddServiceBody, db: Session = Depends(get_db)):
    try:
        sale = ServiceSaleService(db).update_service(service_id, body.model_dump(exclude_unset=True))
        return {"success": True, "service": _sale_dict(sale)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/services/{service_id}/attach")
def attach_tech(service_id: int, body: AttachBody, db: Session = Depends(get_db)):
    svc = ServiceSaleService(db)
    try:
        fields = body.model_dump(exclude_unset=True)
        if "pop_id" in fields:
            svc.attach_pop(service_id, body.pop_id)
        if "radius_username" in fields:
            svc.attach_radius(service_id, body.radius_username)
        sale = svc.get(service_id)
        if not sale:
            raise ValueError("Hizmet bulunamadı")
        return {"success": True, "service": _sale_dict(sale)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.delete("/services/{service_id}")
def remove_service(service_id: int, hard: bool = False, db: Session = Depends(get_db)):
    ok = ServiceSaleService(db).remove(service_id, hard=hard)
    if not ok:
        raise HTTPException(404, "Hizmet bulunamadı")
    return {"success": True, "message": "Hizmet kaldırıldı"}


@router.post("/abone")
def create_abone(body: AboneBody, db: Session = Depends(get_db)):
    """Create abone + service_sale. POP is optional (not required)."""
    try:
        result = AboneService(db).create_abone(body.model_dump())
        return {
            "success": True,
            "hat_no": result["hat_no"],
            "pop_attached": result["pop_attached"],
            "radius_attached": result["radius_attached"],
            "service": _sale_dict(result["service_sale"]),
            "abone_id": result["abone"].id,
        }
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
