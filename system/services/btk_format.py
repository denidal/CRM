"""BTK encoding / cleaning helpers (ported from lib/btk-log-automation.ts)."""

from __future__ import annotations

import unicodedata
from datetime import date, datetime
from typing import Any

HAREKET_ACIKLAMALARI_BTK = {
    1: "YENI_ABONELIK_KAYDI",
    2: "HAT_DURUM_DEGISIKLIGI",
    5: "ADRES_DEGISIKLIGI",
    7: "TARIFE_DEGISIKLIGI",
    10: "HAT_IPTAL",
    11: "MUSTERI_BILGI_DEGISIKLIGI",
    13: "NUMARA_DEGISMEDEN_NAKIL",
    15: "IP_DEGISIKLIGI",
}

_TR_MAP = str.maketrans(
    {
        "İ": "I",
        "I": "I",
        "ı": "i",
        "Ş": "S",
        "ş": "s",
        "Ğ": "G",
        "ğ": "g",
        "Ü": "U",
        "ü": "u",
        "Ö": "O",
        "ö": "o",
        "Ç": "C",
        "ç": "c",
    }
)


def turkish_to_english(text: str) -> str:
    if not text:
        return ""
    text = text.replace("İ̇", "I")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.translate(_TR_MAP)


def clean_btk_value(value: Any) -> str:
    if value is None:
        return ""
    s = turkish_to_english(str(value))
    for ch in "|;'\"\\\n\t\b\f\v`\r":
        s = s.replace(ch, "")
    return s.upper()


def format_date_btk(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")[:19])
        except ValueError:
            return ""
    return (
        f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"
        f"{dt.hour:02d}{dt.minute:02d}{dt.second:02d}"
    )


def now_stamp() -> str:
    n = datetime.now()
    return (
        f"{n.year:04d}{n.month:02d}{n.day:02d}"
        f"{n.hour:02d}{n.minute:02d}{n.second:02d}"
    )


def encode_iso8859_9(text: str) -> bytes:
    return text.encode("iso-8859-9", errors="replace")
