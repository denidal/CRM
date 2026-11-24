"""ServiceSale — N commercial/technical services under one Customer."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.config.db import Base

if TYPE_CHECKING:
    from data.models.customer import Customer
    from data.models.pop import Pop


SERVICE_STATUSES: list[tuple[str, str]] = [
    ("teklif", "Teklif"),
    ("kurulum", "Kurulum"),
    ("upgrade_downgrade", "Upgrade / Downgrade"),
    ("handover", "Handover"),
    ("acc_mnger_onay", "Acc Mnger Onay"),
    ("faturalanan", "Faturalanan (Aktif)"),
    ("iptal", "İptal"),
    ("deaktif", "Deaktif"),
]

COMMITMENT_OPTIONS: list[tuple[str, str]] = [
    ("taahhutsuz", "Taahhütsüz (Tarife Fiyatı)"),
    ("12_ay", "12 Ay Taahhütlü"),
    ("24_ay", "24 Ay Taahhütlü"),
]


class ServiceLocation(Base):
    __tablename__ = "service_locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    address_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    lokasyon_kodu: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    lokasyon_adi: Mapped[str] = mapped_column(String(255), nullable=False)
    il: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ilce: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    acik_adres: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    services: Mapped[list[ServiceSale]] = relationship("ServiceSale", back_populates="location")


class ServiceStatusLog(Base):
    __tablename__ = "service_status_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_sale_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("service_sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    old_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_status: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False, index=True
    )

    service_sale: Mapped[ServiceSale] = relationship("ServiceSale", back_populates="status_logs")


class ServiceSale(Base):
    __tablename__ = "service_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    location_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("service_locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )

    service_type: Mapped[str] = mapped_column(String(30), nullable=False)  # internet|hotspot|interfiber|p2p
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="teklif")

    # Technical — optional, attached to the service
    pop_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pops.id", ondelete="SET NULL"), nullable=True, index=True
    )
    radius_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hat_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Network Parameters
    switch_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vlan_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    port_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ip_ownership: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    assigned_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Commercial / contract snapshot
    paket_adi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    internet_hiz: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    taahhut_suresi: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, default="taahhutsuz"
    )  # taahhutsuz | 12_ay | 24_ay
    catalog_price_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fiyat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    para_birimi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="TL")
    sozlesme_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sozlesme_suresi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sozlesme_baslangic_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sozlesme_bitis_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    orijinal_sozlesme_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # BTK / ISS abone fields (optional at create)
    hizmet_tipi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    abone_baslangic: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    abone_bitis: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_durum: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default="teklif"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Legacy bridge
    legacy_table: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    legacy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="service_sales")
    location: Mapped[Optional[ServiceLocation]] = relationship(
        "ServiceLocation", back_populates="services"
    )
    pop: Mapped[Optional[Pop]] = relationship("Pop", back_populates="service_sales")
    status_logs: Mapped[list[ServiceStatusLog]] = relationship(
        "ServiceStatusLog",
        back_populates="service_sale",
        cascade="all, delete-orphan",
        order_by="ServiceStatusLog.changed_at.desc()",
    )

    @property
    def pop_kodu(self) -> str | None:
        return self.pop.pop_kodu if self.pop else None

    @property
    def pop_adi(self) -> str | None:
        return self.pop.pop_adi if self.pop else None

    @property
    def lokasyon_kodu(self) -> str | None:
        return self.location.lokasyon_kodu if self.location else None

    @property
    def lokasyon_adi(self) -> str | None:
        return self.location.lokasyon_adi if self.location else None