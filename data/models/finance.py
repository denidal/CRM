"""Finance tables — invoices, items, transactions, products."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from data.config.db import Base


class FinancialInvoice(Base):
    __tablename__ = "financial_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    invoice_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TRY")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    items: Mapped[list[FinancialInvoiceItem]] = relationship(
        "FinancialInvoiceItem", back_populates="invoice", cascade="all, delete-orphan"
    )


class FinancialInvoiceItem(Base):
    __tablename__ = "financial_invoice_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    invoice_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("financial_invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    usd_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    exchange_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    discount_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True, default=0)
    vat_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    total_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

    invoice: Mapped[FinancialInvoice] = relationship("FinancialInvoice", back_populates="items")


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # COLLECTION|PAYMENT|EXPENSE|INVOICE
    customer_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    invoice_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TRY")
    transaction_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    payment_method: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )

class Product(Base):
    __tablename__ = "products"

    @property
    def name(self) -> str:
        return self.product_name

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    billing_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "aylık" or "tek seferlik"
    speed_or_capacity_option: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    table_reference: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Existing fields kept for compatibility
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="TRY")
    vat_rate: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, server_default=func.now(), nullable=True
    )