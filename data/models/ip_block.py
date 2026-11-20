"""IP blocks table used by BTK IP block logs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from data.config.db import Base


class IpBlock(Base):
    __tablename__ = "ip_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operator: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ip_start: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ip_end: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    service_type: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nat_application: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    allocation_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    allocation_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ip_block_type: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)  # D/S
    usage_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
