"""Customer — top-level entity (identity / contact / tax).

Addresses: prefer Customer → N CustomerAddress.
Legacy flat address columns kept for DB/BTK compatibility and sync from primary address.
POP / RADIUS / hat live on ServiceSale, not here.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.config.db import Base

if TYPE_CHECKING:
    from data.models.customer_address import CustomerAddress
    from data.models.service_sale import ServiceSale


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    musteri_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    otel_adi: Mapped[str] = mapped_column(String(255), nullable=False)
    firma_unvan: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Legacy single-address mirror of primary CustomerAddress (do not treat as POP)
    otel_adres: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    il: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ilce: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mahalle: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    sokak_cadde: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    dis_kapi_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ic_kapi_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    adres_kodu: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    posta_kodu: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    irtibat_yetkili_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    irtibat_yetkili_telefon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    abone_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tesis_telefon: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    yetkili_kisi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    yetkili_adi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    yetkili_soyadi: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    tc_kimlik_no: Mapped[Optional[str]] = mapped_column(String(11), nullable=True)
    kimlik_seri_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    musteri_tipi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    abone_uyruk: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    abone_kimlik_tipi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    abone_kimlik_aidiyeti: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    vergi_dairesi: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    vergi_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Legacy — ignored by UI; technical fields belong on ServiceSale
    pop_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    radius_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    durum: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="aktif")
    hotspot_aktif: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interfiber_aktif: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    service_sales: Mapped[list["ServiceSale"]] = relationship(
        "ServiceSale",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    addresses: Mapped[list["CustomerAddress"]] = relationship(
        "CustomerAddress",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="CustomerAddress.id",
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} otel_adi={self.otel_adi!r}>"
