"""CustomerAddress — N site addresses under one Customer (not POP)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.config.db import Base

if TYPE_CHECKING:
    from data.models.customer import Customer


class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )

    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Tesis / Şube adı
    otel_adres: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    il: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ilce: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    mahalle: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    sokak_cadde: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    dis_kapi_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ic_kapi_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    adres_kodu: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    posta_kodu: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=True
    )

    customer: Mapped["Customer"] = relationship("Customer", back_populates="addresses")

    def __repr__(self) -> str:
        return f"<CustomerAddress id={self.id} customer_id={self.customer_id}>"
