from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from data.repositories.finance_repo import FinanceRepository


class FinanceService:
    def __init__(self, db: Session) -> None:
        self.db = db  # <-- Make sure self.db is saved here!
        self.repo = FinanceRepository(db)
        self.repo.ensure_tables()

    def list_invoices(self, customer_id: int | None = None):
        return self.repo.list_invoices(customer_id)

    def get_invoice(self, invoice_id: int):
        return self.repo.get_invoice(invoice_id)

    def create_invoice(self, payload: dict[str, Any]) -> Any:
        items = payload.pop("items", []) or []
        if not items:
            raise ValueError("En az bir kalem gerekli")
        if not payload.get("invoice_no"):
            payload["invoice_no"] = f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        for k in ("issue_date", "due_date"):
            if isinstance(payload.get(k), str):
                payload[k] = date.fromisoformat(payload[k][:10])
        payload.setdefault("currency", "TRY")
        payload.setdefault("status", "PENDING")
        payload["amount"] = Decimal("0")
        return self.repo.create_invoice(payload, items)

    def list_transactions(self, customer_id: int | None = None):
        return self.repo.list_transactions(customer_id)

    def create_collection(self, payload: dict[str, Any]):
        data = {
            "type": "COLLECTION",
            "customer_id": payload["customer_id"],
            "invoice_id": payload.get("invoice_id"),
            "amount": Decimal(str(payload["amount"])),
            "currency": payload.get("currency") or "TRY",
            "payment_method": payload.get("payment_method") or "CASH",
            "description": payload.get("description"),
            "transaction_date": datetime.now(),
        }
        return self.repo.create_transaction(data)

    def list_products(self):
        return self.repo.list_products()

    def create_product(self, payload: dict[str, Any]):
        return self.repo.create_product(
            {
                "name": payload["name"],
                "description": payload.get("description"),
                "price": Decimal(str(payload["price"])),
                "currency": payload.get("currency") or "TRY",
                "vat_rate": int(payload.get("vat_rate") or 20),
                "image_url": payload.get("image_url"),
            }
        )

    def balances(self):
        return self.repo.customer_balances()

    def ensure_catalog_table(self):
        """Ensures the catalog_prices table exists."""
        try:
            self.db.execute(
                text("""
                    CREATE TABLE IF NOT EXISTS catalog_prices (
                        price_key VARCHAR(100) PRIMARY KEY,
                        price_value DECIMAL(12, 2) NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            )
            self.db.commit()
        except Exception:
            self.db.rollback()

    def get_catalog_prices(self) -> dict:
        """Fetches all saved catalog prices from the database."""
        self.ensure_catalog_table()
        try:
            rows = self.db.execute(text("SELECT price_key, price_value FROM catalog_prices")).mappings().all()
            return {row["price_key"]: float(row["price_value"]) for row in rows}
        except Exception as e:
            print(f"Error fetching catalog prices: {e}")
            return {}

    def save_catalog_prices(self, form_data: dict):
        """Saves or updates submitted catalog prices into the database."""
        self.ensure_catalog_table()
        for key, value in form_data.items():
            if any(key.startswith(prefix) for prefix in ["metro_", "wifi_", "p2p_", "kabin_", "ip_"]):
                if value != "" and value is not None:
                    try:
                        numeric_value = float(value)
                        self.db.execute(
                            text("""
                                INSERT INTO catalog_prices (price_key, price_value, updated_at) 
                                VALUES (:k, :v, CURRENT_TIMESTAMP)
                                ON CONFLICT (price_key) DO UPDATE SET price_value = :v, updated_at = CURRENT_TIMESTAMP
                            """),
                            {"k": key, "v": numeric_value}
                        )
                    except (ValueError, TypeError):
                        continue
        self.db.commit()