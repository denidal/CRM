"""Legacy contract tables (internet / hotspot / interfiber).

New writes go through ServiceSale; these models keep existing DB rows readable
and support gradual migration via customer_id.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from data.config.db import Base


class InternetContract(Base):
    __tablename__ = "internet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    otel_adi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fiyat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    para_birimi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    internet_hiz: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sozlesme_numarasi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    durum: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fatura_onay: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class HotspotContract(Base):
    __tablename__ = "hotspot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    musteri_adi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    musteri_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tutar: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    para_birimi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    paket_adi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sozlesme_suresi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sozlesme_baslangic_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sozlesme_bitis_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sozlesme_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    orijinal_sozlesme_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    durum: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class InterfiberContract(Base):
    __tablename__ = "interfiber"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    otel_adi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    fiyat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    para_birimi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    internet_hiz: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sozlesme_numarasi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sozlesme_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sozlesme_bitis_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    durum: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
