from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from data.models.finance import (
    FinancialInvoice,
    FinancialInvoiceItem,
    FinancialTransaction,
    Product,
)


class FinanceRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def ensure_tables(self) -> None:
        from data.config.db import init_schema, is_postgres

        if is_postgres():
            init_schema()
            return
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS financial_invoices (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  customer_id INT NOT NULL,
                  invoice_no VARCHAR(50) UNIQUE NOT NULL,
                  issue_date DATE NOT NULL,
                  due_date DATE NOT NULL,
                  amount DECIMAL(15,2) NOT NULL,
                  currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
                  status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_customer (customer_id),
                  INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS financial_invoice_items (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  invoice_id INT NOT NULL,
                  product_id INT NULL,
                  product_name VARCHAR(255) NOT NULL,
                  quantity DECIMAL(10,2) NOT NULL DEFAULT 1,
                  unit_price DECIMAL(15,2) NOT NULL,
                  usd_price DECIMAL(15,2) NULL,
                  exchange_rate DECIMAL(10,4) NULL,
                  discount_rate DECIMAL(5,2) DEFAULT 0,
                  vat_rate INT NOT NULL DEFAULT 20,
                  total_price DECIMAL(15,2) NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_invoice (invoice_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS financial_transactions (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  type VARCHAR(20) NOT NULL,
                  customer_id INT NULL,
                  invoice_id INT NULL,
                  amount DECIMAL(15,2) NOT NULL,
                  currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
                  transaction_date DATETIME NULL,
                  payment_method VARCHAR(30) NULL,
                  description TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  INDEX idx_customer (customer_id),
                  INDEX idx_type (type)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        self.db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS products (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  name VARCHAR(255) NOT NULL,
                  description TEXT,
                  price DECIMAL(15,2) NOT NULL,
                  currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
                  vat_rate INT NOT NULL DEFAULT 20,
                  image_url VARCHAR(255),
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
        )
        self.db.commit()

    def list_invoices(self, customer_id: int | None = None) -> list[FinancialInvoice]:
        stmt = select(FinancialInvoice).options(selectinload(FinancialInvoice.items)).order_by(
            FinancialInvoice.id.desc()
        )
        if customer_id:
            stmt = stmt.where(FinancialInvoice.customer_id == customer_id)
        return list(self.db.scalars(stmt).all())

    def get_invoice(self, invoice_id: int) -> FinancialInvoice | None:
        stmt = (
            select(FinancialInvoice)
            .where(FinancialInvoice.id == invoice_id)
            .options(selectinload(FinancialInvoice.items))
        )
        return self.db.scalars(stmt).first()

    def create_invoice(self, data: dict[str, Any], items: list[dict[str, Any]]) -> FinancialInvoice:
        inv = FinancialInvoice(**data)
        self.db.add(inv)
        self.db.flush()
        total = Decimal("0")
        for it in items:
            qty = Decimal(str(it.get("quantity") or 1))
            unit = Decimal(str(it["unit_price"]))
            vat = int(it.get("vat_rate") or 20)
            disc = Decimal(str(it.get("discount_rate") or 0))
            line = qty * unit * (Decimal("1") - disc / Decimal("100"))
            line = line * (Decimal("1") + Decimal(vat) / Decimal("100"))
            row = FinancialInvoiceItem(
                invoice_id=inv.id,
                product_id=it.get("product_id"),
                product_name=it["product_name"],
                quantity=qty,
                unit_price=unit,
                vat_rate=vat,
                discount_rate=disc,
                total_price=line.quantize(Decimal("0.01")),
            )
            total += row.total_price
            self.db.add(row)
        inv.amount = total.quantize(Decimal("0.01"))
        self.db.commit()
        self.db.refresh(inv)
        return inv

    def list_transactions(self, customer_id: int | None = None) -> list[FinancialTransaction]:
        stmt = select(FinancialTransaction).order_by(FinancialTransaction.id.desc())
        if customer_id:
            stmt = stmt.where(FinancialTransaction.customer_id == customer_id)
        return list(self.db.scalars(stmt).all())

    def create_transaction(self, data: dict[str, Any]) -> FinancialTransaction:
        tx = FinancialTransaction(**data)
        self.db.add(tx)
        self.db.commit()
        self.db.refresh(tx)
        return tx

    def list_products(self) -> list[Product]:
        return list(self.db.scalars(select(Product).order_by(Product.product_name)).all())
    
    def create_product(self, data: dict[str, Any]) -> Product:
        p = Product(**data)
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return p

    def customer_balances(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            text(
                """
                SELECT
                  c.id AS customer_id,
                  c.otel_adi AS customer_name,
                  COALESCE(inv.total_invoiced, 0) AS total_invoiced,
                  COALESCE(trans.total_collected, 0) AS total_collected,
                  (COALESCE(inv.total_invoiced, 0) - COALESCE(trans.total_collected, 0)) AS current_balance
                FROM customers c
                LEFT JOIN (
                  SELECT customer_id, SUM(amount) AS total_invoiced
                  FROM financial_invoices GROUP BY customer_id
                ) inv ON c.id = inv.customer_id
                LEFT JOIN (
                  SELECT customer_id, SUM(amount) AS total_collected
                  FROM financial_transactions WHERE type = 'COLLECTION'
                  GROUP BY customer_id
                ) trans ON c.id = trans.customer_id
                WHERE COALESCE(inv.total_invoiced, 0) > 0
                   OR COALESCE(trans.total_collected, 0) > 0
                ORDER BY c.otel_adi
                """
            )
        ).mappings().all()
        return [dict(r) for r in rows]
