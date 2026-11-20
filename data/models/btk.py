"""BTK / ISS abone rehber and log operation tables."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from data.config.db import Base


class BtkAboneRehber(Base):
    """Maps to existing `btk_abone_rehber` — ISS abone kayıtları."""

    __tablename__ = "btk_abone_rehber"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    OPERATOR_KOD: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    MUSTERI_ID: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    HAT_NO: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    HAT_DURUM: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    HAT_DURUM_KODU: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    HAT_ACIKLAMA: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    MUSTERI_HAREKET_KODU: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    MUSTERI_HAREKET_ACIKLAMA: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    MUSTERI_HAREKET_ZAMANI: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    HIZMET_TIPI: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    MUSTERI_TIPI: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ABONE_BASLANGIC: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ABONE_BITIS: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    ABONE_ADI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_SOYADI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_TC_KIMLIK_NO: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    ABONE_PASAPORT_NO: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ABONE_UNVAN: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ABONE_VERGI_NUMARASI: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ABONE_MERSIS_NUMARASI: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ABONE_CINSIYET: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ABONE_UYRUK: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    ABONE_BABA_ADI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_ANA_ADI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_ANNE_KIZLIK_SOYADI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_DOGUM_YERI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_DOGUM_TARIHI: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    ABONE_MESLEK: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ABONE_TARIFE: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    STATIK_IP: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ISS_HIZ_PROFILI: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ISS_KULLANICI_ADI: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ISS_POP_BILGISI: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Link to unified service_sales row when present
    service_sale_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)


class BtkLogOperation(Base):
    __tablename__ = "btk_log_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
