"""ServiceSale — N commercial/technical services under one Customer.

POP / RADIUS / hat_no live here (optional), not on the customer card.
"""

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


class ServiceSale(Base):
    __tablename__ = "service_sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True, index=True
    )

    service_type: Mapped[str] = mapped_column(String(30), nullable=False)  # internet|hotspot|interfiber
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")

    # Technical — optional, attached to the service
    pop_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("pops.id", ondelete="SET NULL"), nullable=True, index=True
    )
    radius_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    hat_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)

    # Network Parameters from your sheet
    switch_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vlan_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    port_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ip_ownership: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Sağlayıcı, müşteri, Interfiber
    assigned_ip: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Commercial / contract snapshot
    paket_adi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    internet_hiz: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fiyat: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    para_birimi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, default="TL")
    sozlesme_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sozlesme_suresi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sozlesme_baslangic_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sozlesme_bitis_tarihi: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    orijinal_sozlesme_no: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # BTK / ISS abone fields (optional at create)
    hizmet_tipi: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # 44,45,34,40
    abone_baslangic: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    abone_bitis: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    contract_durum: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, default="onaylandı"
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Legacy bridge: old internet/hotspot/interfiber row ids
    legacy_table: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    legacy_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    customer: Mapped[Customer] = relationship("Customer", back_populates="service_sales")
    pop: Mapped[Optional[Pop]] = relationship("Pop", back_populates="service_sales")

    @property
    def pop_kodu(self) -> str | None:
        return self.pop.pop_kodu if self.pop else None

    @property
    def pop_adi(self) -> str | None:
        return self.pop.pop_adi if self.pop else None

    def __repr__(self) -> str:
        return (
            f"<ServiceSale id={self.id} customer_id={self.customer_id} "
            f"type={self.service_type!r}>"
        )