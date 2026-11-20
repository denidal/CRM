from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from data.models.service_sale import ServiceSale
from data.repositories.customer_repo import CustomerRepository
from data.repositories.service_repo import ServiceSaleRepository
from system.domain.service_hierarchy import (
    assert_service_under_customer,
    normalize_service_type,
)


class ServiceSaleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ServiceSaleRepository(db)
        self.customers = CustomerRepository(db)

    def list_for_customer(self, customer_id: int) -> list[ServiceSale]:
        return self.repo.list_by_customer(customer_id)

    def get(self, service_id: int) -> ServiceSale | None:
        return self.repo.get(service_id)

    def add_service(self, customer_id: int, payload: dict[str, Any]) -> ServiceSale:
        assert_service_under_customer(customer_id)
        if not self.customers.get(customer_id, include_services=False):
            raise ValueError("Müşteri bulunamadı")

        service_type = normalize_service_type(payload.get("service_type", ""))
        data: dict[str, Any] = {
            "customer_id": customer_id,
            "service_type": service_type,
            "status": payload.get("status") or "active",
            "paket_adi": payload.get("paket_adi"),
            "internet_hiz": payload.get("internet_hiz"),
            "fiyat": _to_decimal(payload.get("fiyat") or payload.get("tutar")),
            "para_birimi": payload.get("para_birimi") or "TL",
            "sozlesme_no": payload.get("sozlesme_no") or payload.get("sozlesme_numarasi"),
            "sozlesme_suresi": payload.get("sozlesme_suresi"),
            "sozlesme_baslangic_tarihi": _to_date(
                payload.get("sozlesme_baslangic_tarihi") or payload.get("sozlesme_tarihi")
            ),
            "sozlesme_bitis_tarihi": _to_date(payload.get("sozlesme_bitis_tarihi")),
            "contract_durum": payload.get("contract_durum") or payload.get("durum") or "onaylandı",
            # Technical — optional
            "pop_id": payload.get("pop_id"),
            "radius_username": payload.get("radius_username"),
            "hat_no": payload.get("hat_no"),
            "hizmet_tipi": payload.get("hizmet_tipi"),
            "abone_baslangic": _to_date(payload.get("abone_baslangic")),
            "abone_bitis": _to_date(payload.get("abone_bitis")),
        }

        if service_type == "hotspot" and not data["sozlesme_bitis_tarihi"]:
            start = data["sozlesme_baslangic_tarihi"] or date.today()
            years = 3
            if data.get("sozlesme_suresi") and "1" in str(data["sozlesme_suresi"]):
                years = 1
            data["sozlesme_baslangic_tarihi"] = start
            data["sozlesme_bitis_tarihi"] = start + timedelta(days=365 * years)

        return self.repo.create(data)

    def update_service(self, service_id: int, payload: dict[str, Any]) -> ServiceSale:
        allowed = {
            "status",
            "service_type",
            "paket_adi",
            "internet_hiz",
            "fiyat",
            "para_birimi",
            "sozlesme_no",
            "sozlesme_suresi",
            "sozlesme_baslangic_tarihi",
            "sozlesme_bitis_tarihi",
            "orijinal_sozlesme_no",
            "contract_durum",
            "pop_id",
            "radius_username",
            "hat_no",
            "hizmet_tipi",
            "notes",
        }
        data = {k: v for k, v in payload.items() if k in allowed}
        if "service_type" in data and data["service_type"]:
            data["service_type"] = normalize_service_type(data["service_type"])
        if "fiyat" in data:
            data["fiyat"] = _to_decimal(data["fiyat"])
        for dk in ("sozlesme_baslangic_tarihi", "sozlesme_bitis_tarihi"):
            if dk in data:
                data[dk] = _to_date(data[dk])
        sale = self.repo.update(service_id, data)
        if not sale:
            raise ValueError("Hizmet bulunamadı")
        return sale

    def attach_pop(self, service_id: int, pop_id: int | None) -> ServiceSale:
        sale = self.repo.attach_pop(service_id, pop_id)
        if not sale:
            raise ValueError("Hizmet bulunamadı")
        return sale

    def attach_radius(self, service_id: int, username: str | None) -> ServiceSale:
        sale = self.repo.attach_radius(service_id, username)
        if not sale:
            raise ValueError("Hizmet bulunamadı")
        return sale

    def remove(self, service_id: int, *, hard: bool = False) -> bool:
        if hard:
            return self.repo.delete(service_id)
        return self.repo.soft_cancel(service_id) is not None


def _to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
