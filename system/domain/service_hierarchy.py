"""Domain rule: Customer (top) → N ServiceSale (under). POP is never parent."""

from __future__ import annotations

SERVICE_TYPES = frozenset({"internet", "hotspot", "interfiber"})
SERVICE_STATUSES = frozenset({"active", "inactive", "cancelled"})


def assert_service_under_customer(customer_id: int | None) -> None:
    if not customer_id:
        raise ValueError("Hizmet müşteri altına eklenmelidir (customer_id zorunlu)")


def normalize_service_type(value: str) -> str:
    key = (value or "").strip().lower()
    if key not in SERVICE_TYPES:
        raise ValueError(f"Geçersiz service_type: {value!r}")
    return key
