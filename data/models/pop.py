"""POP — infrastructure resource; never parent of Customer."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.config.db import Base

if TYPE_CHECKING:
    from data.models.service_sale import ServiceSale


class Pop(Base):
    __tablename__ = "pops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pop_kodu: Mapped[str] = mapped_column(String(50), nullable=False)
    pop_adi: Mapped[str] = mapped_column(String(255), nullable=False)
    lokasyon: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    adres: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    il: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ilce: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    pop_tipi: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ip_blok: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    kapasite: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    durum: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="aktif")
    aciklama: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    service_sales: Mapped[list[ServiceSale]] = relationship(
        "ServiceSale", back_populates="pop", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Pop id={self.id} kod={self.pop_kodu!r}>"
