from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from data.models.customer import Customer
from data.models.customer_address import CustomerAddress
from data.repositories.customer_repo import CustomerRepository

ADDRESS_FIELDS = {
    "label",
    "otel_adres",
    "il",
    "ilce",
    "mahalle",
    "sokak_cadde",
    "dis_kapi_no",
    "ic_kapi_no",
    "adres_kodu",
    "posta_kodu",
    "is_primary",
}


def _format_phone(value: str | None) -> str | None:
    if not value:
        return value
    cleaned = re.sub(r"\D", "", value)
    if cleaned and not cleaned.startswith("0") and len(cleaned) == 10:
        cleaned = "0" + cleaned
    return cleaned[:11] if cleaned else value


def _format_email(value: str | None) -> str | None:
    return value.lower().strip() if value else value


def _title_case(value: str | None) -> str | None:
    if not value:
        return value
    return " ".join(w[:1].upper() + w[1:].lower() for w in value.split())


class CustomerService:
    IDENTITY_FIELDS = {
        "musteri_no",
        "otel_adi",
        "firma_unvan",
        "otel_adres",
        "il",
        "ilce",
        "mahalle",
        "sokak_cadde",
        "dis_kapi_no",
        "ic_kapi_no",
        "adres_kodu",
        "posta_kodu",
        "irtibat_yetkili_email",
        "irtibat_yetkili_telefon",
        "abone_email",
        "tesis_telefon",
        "yetkili_kisi",
        "yetkili_adi",
        "yetkili_soyadi",
        "tc_kimlik_no",
        "kimlik_seri_no",
        "musteri_tipi",
        "abone_uyruk",
        "abone_kimlik_tipi",
        "abone_kimlik_aidiyeti",
        "vergi_dairesi",
        "vergi_no",
        "durum",
    }

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = CustomerRepository(db)

    def list_customers(self, q: str | None = None, durum: str | None = "aktif") -> list[Customer]:
        return self.repo.list(q=q, durum=durum)

    def get(self, customer_id: int) -> Customer | None:
        return self.repo.get(customer_id)

    def _normalize(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = {k: v for k, v in payload.items() if k in self.IDENTITY_FIELDS}
        if "otel_adi" in data:
            data["otel_adi"] = _title_case(data["otel_adi"])
        if "firma_unvan" in data:
            data["firma_unvan"] = _title_case(data["firma_unvan"])
        for name_field in ("yetkili_adi", "yetkili_soyadi", "yetkili_kisi"):
            if name_field in data:
                data[name_field] = _title_case(data[name_field])
        for phone in ("irtibat_yetkili_telefon", "tesis_telefon"):
            if phone in data:
                data[phone] = _format_phone(data[phone])
        for email in ("irtibat_yetkili_email", "abone_email"):
            if email in data:
                data[email] = _format_email(data[email])
        if "tc_kimlik_no" in data and data["tc_kimlik_no"]:
            data["tc_kimlik_no"] = re.sub(r"\D", "", str(data["tc_kimlik_no"]))[:11]
        if "vergi_no" in data and data["vergi_no"]:
            data["vergi_no"] = re.sub(r"\D", "", str(data["vergi_no"]))
        return data

    def _normalize_address(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = {k: v for k, v in payload.items() if k in ADDRESS_FIELDS}
        if "label" in data and data["label"]:
            data["label"] = _title_case(str(data["label"]))
        if "is_primary" in data:
            data["is_primary"] = bool(data["is_primary"])
        return data

    def _sync_primary_flat(self, customer_id: int) -> None:
        """Keep legacy Customer.* address columns equal to primary address."""
        customer = self.repo.get(customer_id)
        if not customer:
            return
        primary = next((a for a in (customer.addresses or []) if a.is_primary), None)
        if primary is None and customer.addresses:
            primary = customer.addresses[0]
        if not primary:
            return
        self.repo.update(
            customer_id,
            {
                "otel_adres": primary.otel_adres,
                "il": primary.il,
                "ilce": primary.ilce,
                "mahalle": primary.mahalle,
                "sokak_cadde": primary.sokak_cadde,
                "dis_kapi_no": primary.dis_kapi_no,
                "ic_kapi_no": primary.ic_kapi_no,
                "adres_kodu": primary.adres_kodu,
                "posta_kodu": primary.posta_kodu,
            },
        )

    def _ensure_primary_from_flat(self, customer: Customer) -> None:
        """If customer has flat address but no address rows, seed one primary address."""
        if customer.addresses:
            return
        has_any = any(
            [
                customer.otel_adres,
                customer.il,
                customer.ilce,
                customer.mahalle,
                customer.sokak_cadde,
                customer.adres_kodu,
            ]
        )
        if not has_any:
            return
        self.repo.add_address(
            customer.id,
            {
                "label": "Ana Adres",
                "otel_adres": customer.otel_adres,
                "il": customer.il,
                "ilce": customer.ilce,
                "mahalle": customer.mahalle,
                "sokak_cadde": customer.sokak_cadde,
                "dis_kapi_no": customer.dis_kapi_no,
                "ic_kapi_no": customer.ic_kapi_no,
                "adres_kodu": customer.adres_kodu,
                "posta_kodu": customer.posta_kodu,
                "is_primary": True,
            },
        )

    def create(self, payload: dict[str, Any], addresses: list[dict[str, Any]] | None = None) -> Customer:
        data = self._normalize(payload)
        if not (data.get("otel_adi") or "").strip():
            raise ValueError("Müşteri adı (otel_adi) zorunludur")
        data.setdefault("durum", "aktif")
        customer = self.repo.create(data)

        addr_list = list(addresses or [])
        # Seed from flat fields if no explicit addresses provided
        if not addr_list and any(data.get(k) for k in ("otel_adres", "il", "ilce", "adres_kodu")):
            addr_list = [
                {
                    "label": "Ana Adres",
                    "otel_adres": data.get("otel_adres"),
                    "il": data.get("il"),
                    "ilce": data.get("ilce"),
                    "mahalle": data.get("mahalle"),
                    "sokak_cadde": data.get("sokak_cadde"),
                    "dis_kapi_no": data.get("dis_kapi_no"),
                    "ic_kapi_no": data.get("ic_kapi_no"),
                    "adres_kodu": data.get("adres_kodu"),
                    "posta_kodu": data.get("posta_kodu"),
                    "is_primary": True,
                }
            ]
        for i, raw in enumerate(addr_list):
            a = self._normalize_address(raw)
            if i == 0 and "is_primary" not in a:
                a["is_primary"] = True
            self.repo.add_address(customer.id, a)
        if addr_list:
            self._sync_primary_flat(customer.id)
        return self.repo.get(customer.id) or customer

    def update(self, customer_id: int, payload: dict[str, Any]) -> Customer:
        data = self._normalize(payload)
        customer = self.repo.update(customer_id, data)
        if not customer:
            raise ValueError("Müşteri bulunamadı")
        return customer

    def add_address(self, customer_id: int, payload: dict[str, Any]) -> CustomerAddress:
        if not self.repo.get(customer_id, include_services=False):
            raise ValueError("Müşteri bulunamadı")
        addr = self.repo.add_address(customer_id, self._normalize_address(payload))
        if addr.is_primary:
            self._sync_primary_flat(customer_id)
        return addr

    def update_address(self, address_id: int, payload: dict[str, Any]) -> CustomerAddress:
        addr = self.repo.update_address(address_id, self._normalize_address(payload))
        if not addr:
            raise ValueError("Adres bulunamadı")
        if addr.is_primary:
            self._sync_primary_flat(addr.customer_id)
        return addr

    def delete_address(self, address_id: int) -> None:
        addr = self.db.get(CustomerAddress, address_id)
        if not addr:
            raise ValueError("Adres bulunamadı")
        customer_id = addr.customer_id
        self.repo.delete_address(address_id)
        remaining = self.repo.get(customer_id)
        if remaining and remaining.addresses and not any(a.is_primary for a in remaining.addresses):
            remaining.addresses[0].is_primary = True
            self.db.commit()
            self._sync_primary_flat(customer_id)

    def ensure_addresses(self, customer_id: int) -> Customer:
        customer = self.repo.get(customer_id)
        if not customer:
            raise ValueError("Müşteri bulunamadı")
        self._ensure_primary_from_flat(customer)
        return self.repo.get(customer_id) or customer
    def get_customer_with_locations_and_services(self, customer_id: int) -> Customer | None:
        """
        Müşteriyi, altındaki lokasyonları (addresses) ve her lokasyona 
        bağlı ürün/hizmet satışlarını ilişkisel olarak getirir.
        """
        customer = self.repo.get(customer_id)
        if not customer:
            return None
        self._ensure_primary_from_flat(customer)
        return self.repo.get(customer_id)