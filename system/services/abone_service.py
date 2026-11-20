"""Abone (ISS) provisioning.

POP zorunluluğu KALDIRILDI.
Eski CreateAboneModal adım 1'de POP zorunluydu; burada hizmet/sözleşme
öncelikli, POP ve RADIUS isteğe bağlı olarak service_sale'e bağlanır.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from data.repositories.customer_repo import CustomerRepository
from data.repositories.iss_repo import IssRepository
from data.repositories.pop_repo import PopRepository
from data.repositories.service_repo import ServiceSaleRepository
from system.domain.abone_flow import AboneCreateRequest, validate_abone_request
from system.services.service_sale_service import ServiceSaleService


class AboneService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.customers = CustomerRepository(db)
        self.services = ServiceSaleService(db)
        self.service_repo = ServiceSaleRepository(db)
        self.iss = IssRepository(db)
        self.pops = PopRepository(db)

    def create_abone(self, payload: dict[str, Any]) -> dict[str, Any]:
        req = AboneCreateRequest(
            customer_id=int(payload["customer_id"]),
            hizmet_tipi=str(payload.get("hizmet_tipi") or ""),
            paket=str(payload.get("paket") or payload.get("paket_adi") or ""),
            fiyat=Decimal(str(payload.get("fiyat") or 0)),
            para_birimi=str(payload.get("para_birimi") or "TL"),
            hat_no=payload.get("hat_no"),
            abone_baslangic=_parse_date(payload.get("abone_baslangic")),
            pop_id=_optional_int(payload.get("pop_id")),
            radius_username=(payload.get("radius_username") or None) or None,
            skip_validation=bool(payload.get("skip_validation")),
            service_type=str(payload.get("service_type") or "internet"),
        )

        errors = validate_abone_request(req)
        # Explicit: do NOT require pop_id
        if errors and not req.skip_validation:
            raise ValueError("; ".join(errors))

        customer = self.customers.get(req.customer_id)
        if not customer:
            raise ValueError("Müşteri bulunamadı")

        hat_no = req.hat_no or self._generate_hat_no(req.customer_id)
        abone_baslangic = req.abone_baslangic or date.today()

        # 1) Create ServiceSale under customer (POP optional)
        sale = self.services.add_service(
            req.customer_id,
            {
                "service_type": req.service_type,
                "status": "active",
                "paket_adi": req.paket,
                "internet_hiz": req.paket,
                "fiyat": req.fiyat,
                "para_birimi": req.para_birimi,
                "hizmet_tipi": req.hizmet_tipi,
                "hat_no": hat_no,
                "pop_id": req.pop_id,  # may be None
                "radius_username": req.radius_username,  # may be None
                "abone_baslangic": abone_baslangic,
                "sozlesme_baslangic_tarihi": abone_baslangic,
                "contract_durum": "onaylandı",
            },
        )

        # Optional late attach (same effect; kept for clarity / API symmetry)
        if req.pop_id:
            self.services.attach_pop(sale.id, req.pop_id)
        if req.radius_username:
            self.services.attach_radius(sale.id, req.radius_username)

        pop_bilgi = None
        if req.pop_id:
            pop = self.pops.get(req.pop_id)
            if pop:
                pop_bilgi = f"{pop.pop_kodu} - {pop.pop_adi}"

        # 2) BTK abone rehber row — ISS_POP_BILGISI optional
        abone_row = self.iss.create(
            {
                "OPERATOR_KOD": os.getenv("OPERATOR_KOD", "810"),
                "MUSTERI_ID": customer.id,
                "HAT_NO": hat_no,
                "HAT_DURUM": "A",
                "HIZMET_TIPI": req.hizmet_tipi,
                "MUSTERI_TIPI": customer.musteri_tipi,
                "ABONE_BASLANGIC": abone_baslangic,
                "ABONE_ADI": customer.yetkili_adi,
                "ABONE_SOYADI": customer.yetkili_soyadi,
                "ABONE_TC_KIMLIK_NO": customer.tc_kimlik_no,
                "ABONE_UNVAN": customer.firma_unvan or customer.otel_adi,
                "ABONE_VERGI_NUMARASI": customer.vergi_no,
                "ABONE_UYRUK": customer.abone_uyruk or "TUR",
                "ABONE_TARIFE": req.paket,
                "ISS_HIZ_PROFILI": req.paket,
                "ISS_KULLANICI_ADI": req.radius_username,
                "ISS_POP_BILGISI": pop_bilgi,  # None allowed
                "MUSTERI_HAREKET_KODU": "1",
                "MUSTERI_HAREKET_ACIKLAMA": "Yeni Abonelik",
                "MUSTERI_HAREKET_ZAMANI": datetime.now(),
                "service_sale_id": sale.id,
            }
        )

        return {
            "service_sale": sale,
            "abone": abone_row,
            "hat_no": hat_no,
            "pop_attached": bool(req.pop_id),
            "radius_attached": bool(req.radius_username),
        }

    def _generate_hat_no(self, customer_id: int) -> str:
        existing = self.iss.existing_hat_nos() | self.service_repo.existing_hat_nos()
        prefix = str(customer_id)
        for i in range(1, 100):
            candidate = f"{prefix}{i:02d}"
            if candidate not in existing:
                return candidate
        raise ValueError("Bu müşteri için kullanılabilir hat numarası kalmadı (max 99)")


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
