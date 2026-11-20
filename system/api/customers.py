from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from data.config.db import get_db
from system.services.customer_service import CustomerService
from system.services.service_sale_service import ServiceSaleService

router = APIRouter()


class CustomerBody(BaseModel):
    otel_adi: str
    firma_unvan: str | None = None
    otel_adres: str | None = None
    il: str | None = None
    ilce: str | None = None
    mahalle: str | None = None
    sokak_cadde: str | None = None
    dis_kapi_no: str | None = None
    ic_kapi_no: str | None = None
    adres_kodu: str | None = None
    irtibat_yetkili_email: str | None = None
    irtibat_yetkili_telefon: str | None = None
    abone_email: str | None = None
    tesis_telefon: str | None = None
    yetkili_kisi: str | None = None
    yetkili_adi: str | None = None
    yetkili_soyadi: str | None = None
    tc_kimlik_no: str | None = None
    kimlik_seri_no: str | None = None
    musteri_tipi: str | None = None
    abone_uyruk: str | None = None
    abone_kimlik_tipi: str | None = None
    abone_kimlik_aidiyeti: str | None = None
    vergi_dairesi: str | None = None
    vergi_no: str | None = None


def _customer_dict(c) -> dict[str, Any]:
    services = getattr(c, "service_sales", []) or []
    addresses = getattr(c, "addresses", []) or []
    return {
        "id": c.id,
        "musteri_no": c.musteri_no,
        "otel_adi": c.otel_adi,
        "firma_unvan": c.firma_unvan,
        "otel_adres": c.otel_adres,
        "il": c.il,
        "ilce": c.ilce,
        "mahalle": c.mahalle,
        "sokak_cadde": c.sokak_cadde,
        "dis_kapi_no": c.dis_kapi_no,
        "ic_kapi_no": c.ic_kapi_no,
        "adres_kodu": c.adres_kodu,
        "posta_kodu": c.posta_kodu,
        "irtibat_yetkili_email": c.irtibat_yetkili_email,
        "irtibat_yetkili_telefon": c.irtibat_yetkili_telefon,
        "abone_email": c.abone_email,
        "tesis_telefon": c.tesis_telefon,
        "yetkili_kisi": c.yetkili_kisi,
        "yetkili_adi": c.yetkili_adi,
        "yetkili_soyadi": c.yetkili_soyadi,
        "tc_kimlik_no": c.tc_kimlik_no,
        "kimlik_seri_no": c.kimlik_seri_no,
        "musteri_tipi": c.musteri_tipi,
        "abone_uyruk": c.abone_uyruk,
        "abone_kimlik_tipi": c.abone_kimlik_tipi,
        "abone_kimlik_aidiyeti": c.abone_kimlik_aidiyeti,
        "vergi_dairesi": c.vergi_dairesi,
        "vergi_no": c.vergi_no,
        "durum": c.durum,
        "address_count": len(addresses),
        "addresses": [
            {
                "id": a.id,
                "label": a.label,
                "otel_adres": a.otel_adres,
                "il": a.il,
                "ilce": a.ilce,
                "mahalle": a.mahalle,
                "sokak_cadde": a.sokak_cadde,
                "dis_kapi_no": a.dis_kapi_no,
                "ic_kapi_no": a.ic_kapi_no,
                "adres_kodu": a.adres_kodu,
                "posta_kodu": a.posta_kodu,
                "is_primary": a.is_primary,
            }
            for a in addresses
        ],
        "service_count": len(services),
        "services": [
            {
                "id": s.id,
                "service_type": s.service_type,
                "status": s.status,
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
            }
            for s in services
        ],
    }


@router.get("/customers")
def list_customers(q: str | None = None, db: Session = Depends(get_db)):
    rows = CustomerService(db).list_customers(q=q)
    return {"success": True, "data": [_customer_dict(c) for c in rows]}


@router.get("/customers/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)):
    c = CustomerService(db).get(customer_id)
    if not c:
        raise HTTPException(404, "Müşteri bulunamadı")
    return {"success": True, "customer": _customer_dict(c)}


@router.post("/customers")
def create_customer(body: CustomerBody, db: Session = Depends(get_db)):
    try:
        c = CustomerService(db).create(body.model_dump())
        return {"success": True, "customer": _customer_dict(c)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.put("/customers/{customer_id}")
def update_customer(customer_id: int, body: CustomerBody, db: Session = Depends(get_db)):
    try:
        c = CustomerService(db).update(customer_id, body.model_dump())
        return {"success": True, "customer": _customer_dict(c)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/customers/{customer_id}/services")
def list_customer_services(customer_id: int, db: Session = Depends(get_db)):
    rows = ServiceSaleService(db).list_for_customer(customer_id)
    return {
        "success": True,
        "data": [
            {
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
            }
            for s in rows
        ],
    }
