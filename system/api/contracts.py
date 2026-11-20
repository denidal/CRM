from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from data.config.db import get_db
from data.repositories.contract_repo import ContractRepository

router = APIRouter()


@router.get("/internet-contracts")
def internet_contracts(customer_id: int | None = None, db: Session = Depends(get_db)):
    rows = ContractRepository(db).list_internet(customer_id)
    return {"success": True, "data": [{"id": r.id, "otel_adi": r.otel_adi, "fiyat": r.fiyat, "internet_hiz": r.internet_hiz, "durum": r.durum, "customer_id": r.customer_id} for r in rows]}


@router.get("/hotspot-contracts")
def hotspot_contracts(customer_id: int | None = None, db: Session = Depends(get_db)):
    rows = ContractRepository(db).list_hotspot(customer_id)
    return {"success": True, "data": [{"id": r.id, "musteri_adi": r.musteri_adi, "tutar": r.tutar, "paket_adi": r.paket_adi, "durum": r.durum, "customer_id": r.customer_id} for r in rows]}
