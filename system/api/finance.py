from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from data.config.db import get_db
from system.services.finance_service import FinanceService

router = APIRouter(prefix="/finance")


class InvoiceItemIn(BaseModel):
    product_id: Optional[int] = None
    product_name: str
    quantity: float = 1
    unit_price: float
    vat_rate: int = 20
    discount_rate: float = 0


class InvoiceIn(BaseModel):
    customer_id: int
    invoice_no: Optional[str] = None
    issue_date: date
    due_date: date
    currency: str = "TRY"
    status: str = "PENDING"
    description: Optional[str] = None
    items: list[InvoiceItemIn] = Field(default_factory=list)


class CollectionIn(BaseModel):
    customer_id: int
    amount: float
    currency: str = "TRY"
    payment_method: str = "CASH"
    invoice_id: Optional[int] = None
    description: Optional[str] = None


class ProductIn(BaseModel):
    name: str
    price: float
    currency: str = "TRY"
    vat_rate: int = 20
    description: Optional[str] = None


def _inv_dict(inv) -> dict[str, Any]:
    return {
        "id": inv.id,
        "customer_id": inv.customer_id,
        "invoice_no": inv.invoice_no,
        "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "amount": float(inv.amount),
        "currency": inv.currency,
        "status": inv.status,
        "description": inv.description,
        "items": [
            {
                "id": it.id,
                "product_name": it.product_name,
                "quantity": float(it.quantity),
                "unit_price": float(it.unit_price),
                "vat_rate": it.vat_rate,
                "total_price": float(it.total_price),
            }
            for it in (inv.items or [])
        ],
    }


@router.get("/invoices")
def invoices(customer_id: int | None = None, db: Session = Depends(get_db)):
    rows = FinanceService(db).list_invoices(customer_id)
    return {"success": True, "data": [_inv_dict(r) for r in rows]}


@router.post("/invoices")
def create_invoice(body: InvoiceIn, db: Session = Depends(get_db)):
    try:
        inv = FinanceService(db).create_invoice(body.model_dump())
        return {"success": True, "invoice": _inv_dict(inv)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/transactions")
def transactions(customer_id: int | None = None, db: Session = Depends(get_db)):
    rows = FinanceService(db).list_transactions(customer_id)
    return {
        "success": True,
        "data": [
            {
                "id": t.id,
                "type": t.type,
                "customer_id": t.customer_id,
                "amount": float(t.amount),
                "currency": t.currency,
                "payment_method": t.payment_method,
                "description": t.description,
            }
            for t in rows
        ],
    }


@router.post("/collections")
def create_collection(body: CollectionIn, db: Session = Depends(get_db)):
    tx = FinanceService(db).create_collection(body.model_dump())
    return {"success": True, "id": tx.id}


@router.get("/products")
def products(db: Session = Depends(get_db)):
    rows = FinanceService(db).list_products()
    return {
        "success": True,
        "data": [
            {
                "id": p.id,
                "name": p.name,
                "price": float(p.price),
                "currency": p.currency,
                "vat_rate": p.vat_rate,
                "description": p.description,
            }
            for p in rows
        ],
    }


@router.post("/products")
def create_product(body: ProductIn, db: Session = Depends(get_db)):
    p = FinanceService(db).create_product(body.model_dump())
    return {"success": True, "id": p.id}


@router.get("/balances")
def balances(db: Session = Depends(get_db)):
    return {"success": True, "data": FinanceService(db).balances()}
