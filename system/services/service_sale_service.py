from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from data.models.service_sale import (
    SERVICE_STATUSES,
    ServiceLocation,
    ServiceSale,
    ServiceStatusLog,
)
from data.repositories.customer_repo import CustomerRepository
from data.repositories.service_repo import ServiceSaleRepository
from system.domain.service_hierarchy import (
    assert_service_under_customer,
    normalize_service_type,
)

VALID_STATUS_KEYS = {k for k, _ in SERVICE_STATUSES}


class ServiceSaleService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ServiceSaleRepository(db)
        self.customers = CustomerRepository(db)
        self.ensure_schema()

    def ensure_schema(self) -> None:
        """Yeni tablo ve sütunların PostgreSQL tarafında mevcut olmasını sağlar."""
        try:
            ServiceLocation.__table__.create(bind=self.db.get_bind(), checkfirst=True)
            ServiceStatusLog.__table__.create(bind=self.db.get_bind(), checkfirst=True)
            self.db.execute(
                text(
                    "ALTER TABLE service_sales "
                    "ADD COLUMN IF NOT EXISTS location_id INTEGER REFERENCES service_locations(id) ON DELETE SET NULL"
                )
            )
            self.db.execute(
                text(
                    "ALTER TABLE service_sales "
                    "ADD COLUMN IF NOT EXISTS taahhut_suresi VARCHAR(30) DEFAULT 'taahhutsuz'"
                )
            )
            self.db.execute(
                text(
                    "ALTER TABLE service_sales "
                    "ADD COLUMN IF NOT EXISTS catalog_price_key VARCHAR(100)"
                )
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    def list_locations_for_customer(self, customer_id: int) -> list[ServiceLocation]:
        stmt = (
            select(ServiceLocation)
            .where(ServiceLocation.customer_id == customer_id)
            .order_by(ServiceLocation.id.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_or_create_location(
        self,
        customer_id: int,
        *,
        location_id: int | None = None,
        lokasyon_adi: str | None = None,
        il: str | None = None,
        ilce: str | None = None,
        acik_adres: str | None = None,
    ) -> ServiceLocation | None:
        if location_id:
            loc = self.db.get(ServiceLocation, location_id)
            if loc and loc.customer_id == customer_id:
                return loc

        clean_name = (lokasyon_adi or "").strip()
        if not clean_name:
            return None

        # Aynı müşteride aynı isimli lokasyon varsa tekrar üretme
        existing = self.db.execute(
            select(ServiceLocation).where(
                ServiceLocation.customer_id == customer_id,
                ServiceLocation.lokasyon_adi == clean_name,
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        code = self._generate_location_code()
        loc = ServiceLocation(
            customer_id=customer_id,
            lokasyon_kodu=code,
            lokasyon_adi=clean_name,
            il=(il or "").strip() or None,
            ilce=(ilce or "").strip() or None,
            acik_adres=(acik_adres or "").strip() or None,
        )
        self.db.add(loc)
        self.db.flush()
        return loc

    def _generate_location_code(self) -> str:
        """Kısa formatta benzersiz lokasyon kodu üretir: LOC-0001, LOC-0002..."""
        existing_codes = set(
            self.db.execute(select(ServiceLocation.lokasyon_kodu)).scalars().all()
        )
        seq = len(existing_codes) + 1
        while True:
            candidate = f"LOC-{seq:04d}"
            if candidate not in existing_codes:
                return candidate
            seq += 1

    def log_status_change(
        self,
        service_sale_id: int,
        *,
        old_status: str | None,
        new_status: str,
        changed_by: str | None = None,
        note: str | None = None,
    ) -> ServiceStatusLog:
        entry = ServiceStatusLog(
            service_sale_id=service_sale_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=changed_by or "acc_mnger",
            note=note,
            changed_at=datetime.now(),
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def list_for_customer(self, customer_id: int) -> list[ServiceSale]:
        return self.repo.list_by_customer(customer_id)

    def get(self, service_id: int) -> ServiceSale | None:
        return self.repo.get(service_id)

    def add_service(self, customer_id: int, payload: dict[str, Any]) -> ServiceSale:
        assert_service_under_customer(customer_id)
        if not self.customers.get(customer_id, include_services=False):
            raise ValueError("Müşteri bulunamadı")

        # 1) Lokasyon (mevcut seçim veya yeni lokasyon -> unique lokasyon kodu)
        loc = self.get_or_create_location(
            customer_id,
            location_id=payload.get("location_id"),
            lokasyon_adi=payload.get("lokasyon_adi"),
            il=payload.get("lokasyon_il"),
            ilce=payload.get("lokasyon_ilce"),
            acik_adres=payload.get("lokasyon_adres"),
        )
        if not loc and payload.get("require_location"):
            raise ValueError("Servis için lokasyon seçilmeli veya yeni lokasyon adı girilmelidir.")

        raw_type = (payload.get("service_type") or "").strip().lower()
        service_type = "p2p" if raw_type == "p2p" else normalize_service_type(raw_type)

        # 2) Statü doğrulama (8 yeni statü + geriye dönük uyumluluk)
        chosen_status = (
            payload.get("status")
            or payload.get("contract_durum")
            or payload.get("durum")
            or "teklif"
        ).strip()

        taahhut_suresi = (payload.get("taahhut_suresi") or "taahhutsuz").strip()

        data: dict[str, Any] = {
            "customer_id": customer_id,
            "location_id": loc.id if loc else None,
            "service_type": service_type,
            "status": chosen_status,
            "paket_adi": payload.get("paket_adi"),
            "internet_hiz": payload.get("internet_hiz"),
            "taahhut_suresi": taahhut_suresi,
            "catalog_price_key": payload.get("catalog_price_key") or None,
            "fiyat": _to_decimal(payload.get("fiyat") or payload.get("tutar")),
            "para_birimi": payload.get("para_birimi") or "TL",
            "sozlesme_no": payload.get("sozlesme_no") or payload.get("sozlesme_numarasi"),
            "sozlesme_suresi": payload.get("sozlesme_suresi") or taahhut_suresi,
            "sozlesme_baslangic_tarihi": _to_date(
                payload.get("sozlesme_baslangic_tarihi") or payload.get("sozlesme_tarihi")
            ),
            "sozlesme_bitis_tarihi": _to_date(payload.get("sozlesme_bitis_tarihi")),
            "contract_durum": chosen_status,
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

        sale = self.repo.create(data)

        # 3) İlk statü logu
        self.log_status_change(
            sale.id,
            old_status=None,
            new_status=chosen_status,
            changed_by=payload.get("changed_by") or "acc_mnger",
            note="İlk sipariş girişi",
        )
        return sale

    def update_service(self, service_id: int, payload: dict[str, Any]) -> ServiceSale:
        existing = self.repo.get(service_id)
        if not existing:
            raise ValueError("Hizmet bulunamadı")

        old_status = existing.status

        allowed = {
            "status",
            "location_id",
            "service_type",
            "paket_adi",
            "internet_hiz",
            "taahhut_suresi",
            "catalog_price_key",
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
            raw_type = data["service_type"].strip().lower()
            data["service_type"] = "p2p" if raw_type == "p2p" else normalize_service_type(raw_type)
        if "fiyat" in data:
            data["fiyat"] = _to_decimal(data["fiyat"])
        for dk in ("sozlesme_baslangic_tarihi", "sozlesme_bitis_tarihi"):
            if dk in data:
                data[dk] = _to_date(data[dk])

        if "status" in data and data["status"]:
            data["contract_durum"] = data["status"]
        elif "contract_durum" in data and data["contract_durum"]:
            data["status"] = data["contract_durum"]

        sale = self.repo.update(service_id, data)
        if not sale:
            raise ValueError("Hizmet bulunamadı")

        if sale.status != old_status:
            self.log_status_change(
                sale.id,
                old_status=old_status,
                new_status=sale.status,
                changed_by=payload.get("changed_by") or "acc_mnger",
                note=payload.get("status_note"),
            )
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