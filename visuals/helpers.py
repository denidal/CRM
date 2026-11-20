"""Shared UI helpers for visuals (kalan süre, paket listeleri)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def hotspot_paketleri() -> list[str]:
    return [
        f"Hotspot&5651 Loglama - {mbps}Mbps Throughput"
        for mbps in range(50, 1001, 50)
    ]


def internet_hizleri() -> list[str]:
    return [f"{mbps}/{mbps}" for mbps in range(50, 1001, 50)]


def sozlesme_sureleri() -> list[str]:
    return ["1 Yıl", "2 Yıl", "3 Yıl", "4 Yıl", "5 Yıl"]


def remaining_days(end: date | datetime | str | None, today: date | None = None) -> int | None:
    if not end:
        return None
    if isinstance(end, datetime):
        end_d = end.date()
    elif isinstance(end, date):
        end_d = end
    else:
        try:
            end_d = date.fromisoformat(str(end)[:10])
        except ValueError:
            return None
    base = today or date.today()
    return (end_d - base).days


def remaining_label(end: date | datetime | str | None) -> str:
    days = remaining_days(end)
    if days is None:
        return "—"
    if days < 0:
        return f"{abs(days)} gün geçti"
    if days == 0:
        return "Bugün bitiyor"
    return f"{days} gün kaldı"


def remaining_tone(end: date | datetime | str | None) -> str:
    days = remaining_days(end)
    if days is None:
        return "muted"
    if days < 0:
        return "danger"
    if days < 60:
        return "warn"
    return "ok"


def _norm_currency(currency: str | None) -> str:
    cur = (currency or "TL").strip().upper()
    if cur in {"TL", "TRY", "₺"}:
        return "₺"
    if cur in {"USD", "$", "US$"}:
        return "USD"
    return currency or "TL"


def money(value: Any, currency: str | None = "TL") -> str:
    if value is None or value == "":
        return "—"
    try:
        amount = float(Decimal(str(value)))
    except Exception:
        return str(value)
    cur = _norm_currency(currency)
    # Hotspot-style USD often shown without trailing zeros noise
    if cur == "USD":
        formatted = f"{amount:,.3f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if formatted.endswith(",000"):
            formatted = formatted[:-4]
        elif "," in formatted:
            formatted = formatted.rstrip("0").rstrip(",")
        return f"{formatted} USD"
    formatted = f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if formatted.endswith(",00"):
        formatted = formatted[:-3]
    elif formatted.endswith("0") and "," in formatted:
        formatted = formatted[:-1]
    if cur == "₺":
        return f"{formatted} ₺"
    return f"{formatted} {cur}"


def format_tr_date(value: date | datetime | str | None) -> str:
    if not value:
        return "—"
    if isinstance(value, datetime):
        d = value.date()
    elif isinstance(value, date):
        d = value
    else:
        try:
            d = date.fromisoformat(str(value)[:10])
        except ValueError:
            return str(value)
    return d.strftime("%d.%m.%Y")


def is_ready_status(durum: str | None) -> bool:
    if not durum:
        return False
    return durum.strip().casefold() in {"hazır", "hazir", "aktif", "ready"}


def sale_dict(s) -> dict[str, Any]:
    end = s.sozlesme_bitis_tarihi
    start = s.sozlesme_baslangic_tarihi
    return {
        "id": s.id,
        "customer_id": s.customer_id,
        "service_type": s.service_type,
        "status": s.status,
        "paket_adi": s.paket_adi,
        "internet_hiz": s.internet_hiz,
        "fiyat": s.fiyat,
        "para_birimi": s.para_birimi or "TL",
        "sozlesme_no": s.sozlesme_no,
        "sozlesme_suresi": s.sozlesme_suresi,
        "sozlesme_baslangic_tarihi": start,
        "sozlesme_bitis_tarihi": end,
        "baslangic_label": format_tr_date(start),
        "bitis_label": format_tr_date(end),
        "orijinal_sozlesme_no": s.orijinal_sozlesme_no,
        "contract_durum": s.contract_durum,
        "hat_no": s.hat_no,
        "pop_id": s.pop_id,
        "pop_kodu": s.pop_kodu,
        "pop_adi": s.pop_adi,
        "radius_username": s.radius_username,
        "days_left": remaining_days(end),
        "remaining_label": remaining_label(end),
        "remaining_tone": remaining_tone(end),
        "money": money(s.fiyat, s.para_birimi),
    }
