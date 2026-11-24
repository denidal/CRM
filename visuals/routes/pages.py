from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from data.config.db import get_db
from data.models.ip_block import IpBlock
from data.models.service_sale import ServiceSale
from data.repositories.iss_repo import IssRepository
from data.repositories.pop_repo import PopRepository
from system.domain.abone_flow import HIZMET_TIPLERI
from system.services.abone_service import AboneService
from system.services.customer_service import CustomerService
from system.services.service_sale_service import ServiceSaleService
from visuals.helpers import (
    hotspot_paketleri,
    internet_hizleri,
    is_ready_status,
    money,
    remaining_days,
    sale_dict,
    sozlesme_sureleri,
)

COMPANY_NAME = os.getenv("COMPANY_NAME") or os.getenv("BTK_OPERATOR_NAME") or "CRM"

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
router = APIRouter()

MUSTERI_TIPLERI = [
    ("G-SAHIS", "Şahıs"),
    ("G-SIRKET", "Ofis / şahıs işletmesi"),
    ("T-SIRKET", "Kurumsal internet"),
    ("T-KAMU", "Kamu"),
]


def _customer_name_map(db: Session) -> dict[int, str]:
    return {c.id: c.otel_adi for c in CustomerService(db).list_customers(durum=None)}


def _customer_code_map(db: Session) -> dict[int, str]:
    return {
        c.id: (c.musteri_no or f"MST{c.id:03d}")
        for c in CustomerService(db).list_customers(durum=None)
    }


def _all_sales(db: Session) -> list[ServiceSale]:
    stmt = select(ServiceSale).options(selectinload(ServiceSale.pop)).order_by(ServiceSale.id.desc())
    return list(db.scalars(stmt).all())


def _enrich_rows(
    sales: list[ServiceSale],
    names: dict[int, str],
    codes: dict[int, str] | None = None,
) -> list[dict]:
    rows = []
    for s in sales:
        d = sale_dict(s)
        d["customer_name"] = names.get(s.customer_id, f"#{s.customer_id}")
        if codes is not None:
            d["musteri_no"] = codes.get(s.customer_id, f"MST{s.customer_id:03d}")
        rows.append(d)
    return rows


def _is_offer(row: dict) -> bool:
    durum = (row.get("contract_durum") or row.get("status") or "").strip().casefold()
    return durum in {
        "tekliflendirildi",
        "teklif",
        "pending",
        "onay_bekliyor",
        "onay bekliyor",
    }


def _usd_try_rate() -> float:
    try:
        return float(os.getenv("USD_TRY_RATE", "40"))
    except ValueError:
        return 40.0


def _to_try(fiyat, para_birimi: str | None, rate: float) -> float:
    if fiyat is None:
        return 0.0
    amount = float(fiyat)
    cur = (para_birimi or "TL").strip().upper()
    if cur in {"USD", "$", "US$"}:
        return amount * rate
    return amount


def _dashboard_home(db: Session) -> tuple[dict, list[dict], list[dict]]:
    names = _customer_name_map(db)
    codes = _customer_code_map(db)
    customers = [
        c
        for c in CustomerService(db).list_customers(durum=None)
        if (c.durum or "").casefold() not in {"arsiv", "archived"}
    ]
    sales = [s for s in _all_sales(db) if (s.status or "active") not in {"cancelled", "archived"}]
    rows = _enrich_rows(sales, names, codes)
    rate = _usd_try_rate()

    by_type: dict[str, dict] = {}
    for s in sales:
        t = s.service_type or "other"
        bucket = by_type.setdefault(t, {"count": 0, "revenue": 0.0})
        bucket["count"] += 1
        bucket["revenue"] += _to_try(s.fiyat, s.para_birimi, rate)

    internet = [s for s in sales if s.service_type == "internet"]
    hotspot = [s for s in sales if s.service_type == "hotspot"]
    total_revenue = sum(b["revenue"] for b in by_type.values())

    service_breakdown = [
        {
            "type": t,
            "count": b["count"],
            "revenue_label": money(b["revenue"], "₺"),
        }
        for t, b in sorted(by_type.items())
    ]

    urgent = [
        r
        for r in rows
        if r["days_left"] is not None and 0 <= r["days_left"] < 60 and not _is_offer(r)
    ]
    urgent.sort(key=lambda r: (r["days_left"] is None, r["days_left"]))

    offers = [r for r in rows if _is_offer(r)]
    offers.sort(key=lambda r: r.get("id") or 0, reverse=True)

    stats = {
        "customer_count": len(customers),
        "internet_count": len(internet),
        "hotspot_count": len(hotspot),
        "total_revenue_label": money(total_revenue, "₺"),
        "service_breakdown": service_breakdown,
        "company_name": COMPANY_NAME,
    }
    return stats, urgent[:40], offers[:40]


@router.get("/catalog", response_class=HTMLResponse)  # (or whatever your exact path is, e.g., /finance/products)
def catalog_page(request: Request, db: Session = Depends(get_db)):
    from system.services.finance_service import FinanceService
    
    try:
        saved_prices = FinanceService(db).get_catalog_prices()
    except Exception:
        saved_prices = {}

    return templates.TemplateResponse(
        request,
        "finance/products.html",
        {
            "request": request,
            "prices": saved_prices,
            "title": "Ürün ve Fiyat Kataloğu"
        }
    )

@router.get("/", response_class=HTMLResponse)
def home(request: Request, db: Session = Depends(get_db)):
    try:
        stats, urgent, offers = _dashboard_home(db)
    except Exception:
        stats = {
            "customer_count": 0,
            "internet_count": 0,
            "hotspot_count": 0,
            "total_revenue_label": "—",
            "service_breakdown": [],
            "company_name": COMPANY_NAME,
        }
        urgent, offers = [], []
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "title": "CRM",
            "stats": stats,
            "urgent": urgent,
            "offers": offers,
            "company_name": stats.get("company_name") or COMPANY_NAME,
        },
    )


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {"title": "Giriş", "error": None})


@router.get("/customers", response_class=HTMLResponse)
def customers_list(
    request: Request,
    q: str | None = None,
    durum: str | None = None,
    db: Session = Depends(get_db),
):
    raw = CustomerService(db).list_customers(q=q, durum=None)
    rows = []
    
    for c in raw:
        if durum and (c.durum or "") != durum:
            continue
        if not durum and (c.durum or "").casefold() in {"arsiv", "archived"}:
            continue
        
        all_services = [sale_dict(s) for s in (c.service_sales or [])]
        
        # Lokasyonlar ve Altlarındaki Finans Ürünlerini Grupluyoruz
        locations = []
        for addr in (c.addresses or []):
            loc_services = [s for s in all_services if s.get("address_id") == addr.id]
            locations.append({
                "id": addr.id,
                "label": addr.label or f"Lokasyon #{addr.id}",
                "city": addr.il,
                "district": addr.ilce,
                "address_text": addr.otel_adres,
                "adres_kodu": addr.adres_kodu,
                "services": loc_services  # Ürün kataloğundan çekilen/atanan hizmetler
            })

        rows.append(
            {
                "id": c.id,
                "otel_adi": c.otel_adi,
                "firma_unvan": c.firma_unvan,
                "musteri_no": c.musteri_no,
                "irtibat_yetkili_telefon": c.irtibat_yetkili_telefon,
                "irtibat_yetkili_email": c.irtibat_yetkili_email,
                "durum": c.durum,
                "is_ready": is_ready_status(c.durum),
                "locations": locations,
            }
        )

    return templates.TemplateResponse(
        request,
        "customers/list.html",
        {
            "customers": rows,
            "q": q or "",
            "total_count": len(rows),
            "title": "Müşteriler",
        },
    )

@router.get("/servisler", response_class=HTMLResponse)
def servisler_list(
    request: Request,
    type: str | None = None,
    urgent: int = 0,
    db: Session = Depends(get_db),
):
    names = _customer_name_map(db)
    codes = _customer_code_map(db)
    rows = _enrich_rows(_all_sales(db), names, codes)
    if type:
        rows = [r for r in rows if r["service_type"] == type]
    if urgent:
        rows = [r for r in rows if r["days_left"] is not None and r["days_left"] < 60]
    return templates.TemplateResponse(
        request,
        "services/list.html",
        {
            "rows": rows,
            "type": type or "",
            "urgent": urgent,
            "title": "Servisler",
        },
    )
from datetime import date

@router.get("/servisler/new", response_class=HTMLResponse)
def servis_new_form(
    request: Request,
    customer_id: int | None = None,
    location_id: int | None = None,
    db: Session = Depends(get_db),
):
    from data.models.service_sale import COMMITMENT_OPTIONS, SERVICE_STATUSES
    from system.services.finance_service import FinanceService

    svc_sales = ServiceSaleService(db)
    try:
        fin = FinanceService(db)
        products = fin.list_products() or []
        raw_prices = fin.get_catalog_prices() or {}
        saved_prices = {
            str(k): (float(v) if v is not None else None)
            for k, v in raw_prices.items()
        }
    except Exception as exc:
        db.rollback()
        print("CATALOG ERR:", repr(exc))
        products = []
        saved_prices = {}

    locations = svc_sales.list_locations_for_customer(customer_id) if customer_id else []
    pops = PopRepository(db).list(only_active=True)
    customers = CustomerService(db).list_customers()

    return templates.TemplateResponse(
        request,
        "services/form.html",
        {
            "customers": customers,
            "locations": locations,
            "pops": pops,
            "products": products,
            "prices": saved_prices,
            "statuses": SERVICE_STATUSES,
            "commitments": COMMITMENT_OPTIONS,
            "selected_customer_id": customer_id,
            "selected_location_id": location_id,
            "today": date.today().isoformat(),
            "error": None,
            "title": "Yeni Servis",
        },
    )
from fastapi.responses import Response

@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)

@router.post("/servisler/new")
def servis_create(
    request: Request,
    customer_id: int = Form(...),
    product_id: str = Form(""),
    location_id: str = Form(""),
    lokasyon_adi: str = Form(""),
    lokasyon_il: str = Form(""),
    lokasyon_ilce: str = Form(""),
    lokasyon_adres: str = Form(""),
    service_type: str = Form("internet"),
    taahhut_suresi: str = Form("taahhutsuz"),
    internet_hiz: str = Form(""),
    product_name: str = Form(""),
    unit_price: str = Form(...),
    quantity: str = Form("1"),
    start_date: str = Form(""),
    end_date: str = Form(""),
    durum: str = Form("teklif"),
    pop_id: str = Form(""),
    radius_username: str = Form(""),
    db: Session = Depends(get_db),
):
    from data.models.service_sale import COMMITMENT_OPTIONS, SERVICE_STATUSES
    from system.services.finance_service import FinanceService

    try:
        clean_price = (
            float(unit_price.replace(".", "").replace(",", "."))
            if isinstance(unit_price, str) and "," in unit_price
            else float(str(unit_price).replace(",", "."))
        )
        clean_qty = float(quantity or 1)
        resolved_name = (product_name or internet_hiz or "").strip()

        payload = {
            "product_id": int(product_id) if product_id.isdigit() else None,
            "location_id": int(location_id) if location_id.isdigit() else None,
            "lokasyon_adi": lokasyon_adi,
            "lokasyon_il": lokasyon_il,
            "lokasyon_ilce": lokasyon_ilce,
            "lokasyon_adres": lokasyon_adres,
            "service_type": service_type,
            "taahhut_suresi": taahhut_suresi,
            "paket_adi": resolved_name or None,
            "internet_hiz": (internet_hiz or resolved_name) or None,
            "fiyat": clean_price * clean_qty,
            "para_birimi": "TL",
            "sozlesme_baslangic_tarihi": start_date or None,
            "sozlesme_bitis_tarihi": end_date or None,
            "status": durum or "teklif",
            "contract_durum": durum or "teklif",
            "pop_id": int(pop_id) if pop_id.isdigit() else None,
            "radius_username": radius_username.strip() or None,
        }

        ServiceSaleService(db).add_service(customer_id, payload)
        return RedirectResponse("/servisler", status_code=303)
    except ValueError as exc:
        db.rollback()
        svc_sales = ServiceSaleService(db)
        try:
            fin = FinanceService(db)
            products = fin.list_products()
            saved_prices = fin.get_catalog_prices() or {}
        except Exception:
            db.rollback()
            products = []
            saved_prices = {}

        return templates.TemplateResponse(
            request,
            "services/form.html",
            {
                "customers": CustomerService(db).list_customers(),
                "locations": svc_sales.list_locations_for_customer(customer_id),
                "pops": PopRepository(db).list(only_active=True),
                "products": products,
                "prices": saved_prices,
                "statuses": SERVICE_STATUSES,
                "commitments": COMMITMENT_OPTIONS,
                "selected_customer_id": customer_id,
                "selected_location_id": int(location_id) if location_id.isdigit() else None,
                "today": date.today().isoformat(),
                "error": str(exc),
                "title": "Yeni Servis",
            },
            status_code=400,
        )
    

@router.post("/customers/{customer_id}/archive")
def customer_archive(customer_id: int, db: Session = Depends(get_db)):
    CustomerService(db).repo.archive(customer_id)
    return RedirectResponse("/customers", status_code=303)


@router.get("/customers/new", response_class=HTMLResponse)
def customer_create_form(request: Request):
    return templates.TemplateResponse(
        request,
        "customers/create.html",
        {"title": "Yeni Müşteri", "error": None, "musteri_tipleri": MUSTERI_TIPLERI},
    )


@router.post("/customers/new")
async def customer_create_submit(request: Request, db: Session = Depends(get_db)):
    raw = await request.form()
    form = {k: (v.strip() if isinstance(v, str) else v) for k, v in raw.items()}
    try:
        addresses = []
        if form.get("addr_il") or form.get("addr_otel_adres") or form.get("addr_label"):
            addresses.append(
                {
                    "label": form.get("addr_label") or "Ana Adres",
                    "otel_adres": form.get("addr_otel_adres") or None,
                    "il": form.get("addr_il") or None,
                    "ilce": form.get("addr_ilce") or None,
                    "mahalle": form.get("addr_mahalle") or None,
                    "sokak_cadde": form.get("addr_sokak_cadde") or None,
                    "dis_kapi_no": form.get("addr_dis_kapi_no") or None,
                    "ic_kapi_no": form.get("addr_ic_kapi_no") or None,
                    "adres_kodu": form.get("addr_adres_kodu") or None,
                    "posta_kodu": form.get("addr_posta_kodu") or None,
                    "is_primary": True,
                }
            )
        c = CustomerService(db).create(form, addresses=addresses or None)
        return RedirectResponse(f"/customers/{c.id}", status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "customers/create.html",
            {
                "title": "Yeni Müşteri",
                "error": str(exc),
                "musteri_tipleri": MUSTERI_TIPLERI,
            },
            status_code=400,
        )


@router.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(request: Request, customer_id: int, db: Session = Depends(get_db)):
    svc = CustomerService(db)
    try:
        customer = svc.ensure_addresses(customer_id)
    except ValueError:
        return HTMLResponse("Müşteri bulunamadı", status_code=404)
    services = [sale_dict(s) for s in ServiceSaleService(db).list_for_customer(customer_id)]
    try:
        abone_rows = IssRepository(db).list_by_customer(customer_id)
    except Exception:
        abone_rows = []
    return templates.TemplateResponse(
        request,
        "customers/detail.html",
        {
            "customer": customer,
            "addresses": customer.addresses or [],
            "services": services,
            "abone_rows": abone_rows,
            "musteri_tipleri": MUSTERI_TIPLERI,
            "files": [
                {"name": "Vergi Levhası", "type": "vergi_levhasi"},
                {"name": "İmza Sirküleri", "type": "imza_sirkuleri"},
                {"name": "Ticaret Sicil Gazetesi", "type": "ticaret_sicil"},
                {"name": "Yetkili Kimlik Fotokopisi", "type": "yetkili_kimlik"},
            ],
            "title": customer.otel_adi,
        },
    )


@router.post("/customers/{customer_id}/update")
async def customer_update(request: Request, customer_id: int, db: Session = Depends(get_db)):
    form = dict(await request.form())
    try:
        CustomerService(db).update(customer_id, form)
        return RedirectResponse(f"/customers/{customer_id}", status_code=303)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)


@router.post("/customers/{customer_id}/addresses")
async def customer_add_address(request: Request, customer_id: int, db: Session = Depends(get_db)):
    form = dict(await request.form())
    form["is_primary"] = form.get("is_primary") in {"1", "true", "on", "yes"}
    try:
        CustomerService(db).add_address(customer_id, form)
        return RedirectResponse(f"/customers/{customer_id}#addresses", status_code=303)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)


@router.post("/customers/{customer_id}/addresses/{address_id}/delete")
def customer_delete_address(customer_id: int, address_id: int, db: Session = Depends(get_db)):
    try:
        CustomerService(db).delete_address(address_id)
    except ValueError as exc:
        return HTMLResponse(str(exc), status_code=400)
    return RedirectResponse(f"/customers/{customer_id}#addresses", status_code=303)


@router.get("/customers/{customer_id}/services/new", response_class=HTMLResponse)
def service_form_legacy(customer_id: int):
    return RedirectResponse(f"/servisler/new?customer_id={customer_id}", status_code=303)

@router.get("/archive", response_class=HTMLResponse)
def archive_page(request: Request, db: Session = Depends(get_db)):
    names = _customer_name_map(db)
    rows = _enrich_rows(_all_sales(db), names)
    rows = [
        r
        for r in rows
        if r.get("status") in {"cancelled", "inactive"}
        or (r["days_left"] is not None and r["days_left"] < 0)
    ]
    return templates.TemplateResponse(
        request, "archive/list.html", {"rows": rows, "title": "Arşiv"}
    )


@router.get("/system", response_class=HTMLResponse)
def system_page(request: Request):
    return templates.TemplateResponse(request, "system/index.html", {"title": "Sistem"})


@router.get("/pops", response_class=HTMLResponse)
def pops_list(request: Request, db: Session = Depends(get_db)):
    pops = PopRepository(db).list()
    return templates.TemplateResponse(
        request, "pops/list.html", {"pops": pops, "title": "POP Listesi"}
    )


@router.get("/radius", response_class=HTMLResponse)
def radius_page(
    request: Request,
    q: str = "",
    unassigned: int = 0,
    service_id: int | None = None,
    db: Session = Depends(get_db),
):
    from system.services.radius_service import RadiusService

    try:
        users = RadiusService(db).search(q=q, limit=200, unassigned_only=bool(unassigned))
        attachments = RadiusService(db).list_service_attachments()
    except Exception:
        users, attachments = [], []
    pops = PopRepository(db).list(only_active=True)
    return templates.TemplateResponse(
        request,
        "radius/list.html",
        {
            "users": users,
            "attachments": attachments,
            "pops": pops,
            "q": q,
            "unassigned": unassigned,
            "service_id": service_id,
            "title": "RADIUS",
            "error": None,
            "ok": None,
        },
    )


@router.post("/radius/attach")
def radius_attach(
    request: Request,
    service_id: int = Form(...),
    radius_username: str = Form(...),
    pop_id: str = Form(""),
    db: Session = Depends(get_db),
):
    from system.services.radius_service import RadiusService

    try:
        RadiusService(db).attach_to_service(
            service_id,
            radius_username or None,
            int(pop_id) if pop_id else None,
        )
        RadiusService(db).sync_aaa(service_id)
        return RedirectResponse("/radius?ok=1", status_code=303)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "radius/list.html",
            {
                "users": [],
                "attachments": [],
                "pops": PopRepository(db).list(only_active=True),
                "q": "",
                "unassigned": 0,
                "service_id": service_id,
                "title": "RADIUS",
                "error": str(exc),
                "ok": None,
            },
            status_code=400,
        )


@router.get("/services/{service_id}/radius", response_class=HTMLResponse)
def service_radius_form(request: Request, service_id: int, db: Session = Depends(get_db)):
    from system.services.radius_service import RadiusService

    sale = ServiceSaleService(db).get(service_id)
    if not sale:
        return HTMLResponse("Hizmet bulunamadı", status_code=404)
    try:
        users = RadiusService(db).search(limit=200, unassigned_only=True)
    except Exception:
        users = []
    return templates.TemplateResponse(
        request,
        "services/radius.html",
        {
            "sale": sale,
            "users": users,
            "pops": PopRepository(db).list(only_active=True),
            "title": f"RADIUS · Hizmet #{service_id}",
            "error": None,
        },
    )


@router.post("/services/{service_id}/radius")
def service_radius_save(
    request: Request,
    service_id: int,
    radius_username: str = Form(""),
    pop_id: str = Form(""),
    hat_no: str = Form(""),
    db: Session = Depends(get_db),
):
    from system.services.radius_service import RadiusService

    try:
        svc = RadiusService(db)
        svc.attach_to_service(service_id, radius_username or None, int(pop_id) if pop_id else None)
        if hat_no:
            ServiceSaleService(db).update_service(service_id, {"hat_no": hat_no})
        svc.sync_aaa(service_id)
        sale = ServiceSaleService(db).get(service_id)
        return RedirectResponse(f"/customers/{sale.customer_id}", status_code=303)
    except ValueError as exc:
        sale = ServiceSaleService(db).get(service_id)
        return templates.TemplateResponse(
            request,
            "services/radius.html",
            {
                "sale": sale,
                "users": [],
                "pops": PopRepository(db).list(only_active=True),
                "title": f"RADIUS · Hizmet #{service_id}",
                "error": str(exc),
            },
            status_code=400,
        )


@router.get("/finance", response_class=HTMLResponse)
def finance_home(request: Request, db: Session = Depends(get_db)):
    from system.services.finance_service import FinanceService

    names = _customer_name_map(db)
    codes = _customer_code_map(db)
    sales_rows = _enrich_rows(_all_sales(db), names, codes)

    try:
        svc = FinanceService(db)
        balances, invoices, products = svc.balances(), svc.list_invoices()[:50], svc.list_products()
    except Exception:
        balances, invoices, products = [], [], []

    return templates.TemplateResponse(
        request,
        "finance/index.html",
        {
            "balances": balances,
            "invoices": invoices,
            "products": products,
            "sales": sales_rows,
            "title": "Finans",
        },
    )


from sqlalchemy import text
@router.post("/finance/invoices/{invoice_id}/pay")
def mark_invoice_as_paid(invoice_id: int, db: Session = Depends(get_db)):
    try:
        # 1. Fetch the invoice details to get customer_id, amount, and currency
        invoice_query = text("SELECT id, customer_id, amount, currency, description FROM financial_invoices WHERE id = :id")
        invoice = db.execute(invoice_query, {"id": invoice_id}).mappings().first()

        if invoice:
            # 2. Update the invoice status to ONAYLANDI
            db.execute(
                text("UPDATE financial_invoices SET status = :status WHERE id = :id"),
                {"status": "ONAYLANDI", "id": invoice_id}
            )

            # 3. Insert into financial_transactions with all required columns matching your table schema
            db.execute(
                text("""
                    INSERT INTO financial_transactions 
                    (type, customer_id, invoice_id, amount, currency, transaction_date, payment_method, description, created_at)
                    VALUES 
                    (:type, :customer_id, :invoice_id, :amount, :currency, NOW(), :payment_method, :description, NOW())
                """),
                {
                    "type": "INCOME",  # Adjust if your app uses 'COLLECTION' or 'TAHSILAT'
                    "customer_id": invoice["customer_id"],
                    "invoice_id": invoice["id"],
                    "amount": invoice["amount"],
                    "currency": invoice["currency"] or "TRY",
                    "payment_method": "CASH",
                    "description": f"Fatura #{invoice_id} Tahsilatı"
                }
            )
            
            db.commit()
            print(f"--- ÖDENDİ VE KASA KAYDI BAŞARILI: ID {invoice_id} ---")
            
    except Exception as e:
        db.rollback()
        print(f"Ödeme onay ve kasa kayıt hatası: {e}")
        
    return RedirectResponse(url="/finance/invoices", status_code=303)


@router.post("/finance/invoices/{invoice_id}/cancel")
def cancel_invoice(invoice_id: int, db: Session = Depends(get_db)):
    try:
        result = db.execute(
            text("UPDATE financial_invoices SET status = :status WHERE id = :id"),
            {"status": "İPTAL EDİLDİ", "id": invoice_id}
        )
        db.commit()
        print(f"--- İPTAL GÜNCELLEMESİ: {result.rowcount} satır güncellendi (ID: {invoice_id}) ---")
    except Exception as e:
        db.rollback()
        print(f"İptal hatası: {e}")
        
    return RedirectResponse(url="/finance/invoices", status_code=303)



@router.get("/finance/invoices", response_class=HTMLResponse)
def finance_invoices(request: Request, db: Session = Depends(get_db)):
    from system.services.finance_service import FinanceService

    names = _customer_name_map(db)
    codes = _customer_code_map(db)
    sales_rows = _enrich_rows(_all_sales(db), names, codes)

    try:
        invoices = FinanceService(db).list_invoices()
    except Exception:
        invoices = []

    return templates.TemplateResponse(
        request,
        "finance/invoices.html",
        {
            "invoices": invoices,
            "sales": sales_rows,
            "title": "Faturalar",
        },
    )


@router.get("/finance/invoices/new", response_class=HTMLResponse)
def finance_invoice_new(request: Request, db: Session = Depends(get_db)):
    from system.services.finance_service import FinanceService

    try:
        svc = FinanceService(db)
        products = svc.list_products()
        saved_prices = svc.get_catalog_prices() # Katalog fiyatlarını çekiyoruz
    except Exception:
        products = []
        saved_prices = {}

    return templates.TemplateResponse(
        request,
        "finance/invoice_form.html",
        {
            "customers": CustomerService(db).list_customers(),
            "products": products,
            "prices": saved_prices, # Şablona aktarıyoruz
            "error": None,
            "title": "Yeni Fatura",
        },
    )

@router.post("/finance/invoices/new")
def finance_invoice_create(
    request: Request,
    customer_id: int = Form(...),
    issue_date: str = Form(...),
    due_date: str = Form(...),
    product_name: str = Form(...),
    unit_price: str = Form(...),
    quantity: str = Form("1"),
    vat_rate: str = Form("20"),
    description: str = Form(""),
    service_type: str = Form("hotspot"),
    sozlesme_suresi: str = Form("1 Yıl"),
    sozlesme_no: str = Form(""),
    contract_durum: str = Form("onaylandı"),
    db: Session = Depends(get_db),
):
    from system.services.finance_service import FinanceService

    try:
        clean_price = (
            float(unit_price.replace(".", "").replace(",", "."))
            if isinstance(unit_price, str)
            else float(unit_price)
        )
        clean_qty = float(quantity or 1)

        FinanceService(db).create_invoice(
            {
                "customer_id": customer_id,
                "issue_date": issue_date,
                "due_date": due_date,
                "description": description or None,
                "items": [
                    {
                        "product_name": product_name,
                        "unit_price": clean_price,
                        "quantity": clean_qty,
                        "vat_rate": int(vat_rate or 20),
                    }
                ],
            }
        )

        # Create matching ServiceSale so it appears on /contracts
        ServiceSaleService(db).add_service(
            customer_id,
            {
                "service_type": service_type,
                "paket_adi": product_name or None,
                "internet_hiz": product_name or None,
                "fiyat": clean_price * clean_qty,
                "para_birimi": "TL",
                "sozlesme_no": sozlesme_no or None,
                "sozlesme_suresi": sozlesme_suresi or "1 Yıl",
                "sozlesme_baslangic_tarihi": issue_date or None,
                "sozlesme_bitis_tarihi": due_date or None,
                "contract_durum": contract_durum or "onaylandı",
            },
        )

        return RedirectResponse("/finance/invoices", status_code=303)
    except ValueError as exc:
        from system.services.finance_service import FinanceService

        try:
            svc = FinanceService(db)
            products = svc.list_products()
            saved_prices = svc.get_catalog_prices()
        except Exception:
            products = []
            saved_prices = {}

        return templates.TemplateResponse(
            request,
            "finance/invoice_form.html",
            {
                "customers": CustomerService(db).list_customers(),
                "products": products,
                "prices": saved_prices,
                "error": str(exc),
                "title": "Yeni Fatura",
            },
            status_code=400,
        )

    
@router.get("/finance/products", response_class=HTMLResponse)
def finance_catalog(request: Request, db: Session = Depends(get_db)):
    from system.services.finance_service import FinanceService
    
    try:
        saved_prices = FinanceService(db).get_catalog_prices()
    except Exception:
        saved_prices = {}

    return templates.TemplateResponse(
        request,
        "finance/products.html", # <-- Match your actual HTML file name here (e.g., products.html)
        {
            "prices": saved_prices,
            "title": "Ürün ve Fiyat Kataloğu",
            "error": None
        },
    )


@router.post("/finance/products")
def finance_product_create(
    name: str = Form(...),
    price: str = Form(...),
    currency: str = Form("TRY"),
    vat_rate: str = Form("20"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    from system.services.finance_service import FinanceService

    FinanceService(db).create_product(
        {
            "name": name,
            "price": float(price),
            "currency": currency,
            "vat_rate": int(vat_rate or 20),
            "description": description or None,
        }
    )
    return RedirectResponse("/finance/products", status_code=303)


@router.get("/finance/kasa", response_class=HTMLResponse)
def finance_kasa(request: Request, db: Session = Depends(get_db)):
    from system.services.finance_service import FinanceService

    try:
        transactions = FinanceService(db).list_transactions()[:100]
    except Exception:
        transactions = []
    return templates.TemplateResponse(
        request,
        "finance/kasa.html",
        {
            "transactions": transactions,
            "customers": CustomerService(db).list_customers(),
            "title": "Kasa / Tahsilat",
            "error": None,
        },
    )


@router.post("/finance/kasa")
def finance_collection(
    customer_id: int = Form(...),
    amount: str = Form(...),
    payment_method: str = Form("CASH"),
    description: str = Form(""),
    db: Session = Depends(get_db),
):
    from system.services.finance_service import FinanceService

    FinanceService(db).create_collection(
        {
            "customer_id": customer_id,
            "amount": float(amount),
            "payment_method": payment_method,
            "description": description or None,
        }
    )
    return RedirectResponse("/finance/kasa", status_code=303)


@router.get("/iss", response_class=HTMLResponse)
def iss_page(request: Request, view: str | None = None):
    return RedirectResponse("/btk?tab=abone" + ("&view=ozet" if view == "ozet" else ""), status_code=303)

@router.post("/finance/catalog/save")
async def save_catalog_prices(request: Request, db: Session = Depends(get_db)):
    form_data = await request.form()
    from system.services.finance_service import FinanceService
    
    try:
        FinanceService(db).save_catalog_prices(dict(form_data))
        return RedirectResponse("/finance/products", status_code=303)
    except Exception as exc:
        print(f"Kayıt hatası: {exc}")
        return RedirectResponse("/finance/products", status_code=303)

    

@router.get("/btk", response_class=HTMLResponse)
def btk_page(
    request: Request,
    tab: str | None = None,
    q: str | None = None,
    log_type: str | None = None,
    db: Session = Depends(get_db),
):
    from system.services.btk_log_service import BtkLogService

    active = (tab or "abone").strip().lower()
    if active not in {"abone", "oturum", "logs", "ipblok"}:
        active = "abone"

    try:
        operations = BtkLogService().list_operations(80)
    except Exception:
        operations = []
    if log_type:
        operations = [
            o
            for o in operations
            if (o.get("log_type") if isinstance(o, dict) else getattr(o, "log_type", None)) == log_type
        ]
    if q:
        ql = q.casefold()
        operations = [
            o
            for o in operations
            if ql
            in (
                (o.get("file_name") if isinstance(o, dict) else getattr(o, "file_name", None)) or ""
            ).casefold()
        ]

    abone_rows = []
    try:
        names = _customer_name_map(db) if '_customer_name_map' in globals() else {}
        for r in IssRepository(db).list_all(limit=200):
            abone_rows.append({
                "id": getattr(r, "id", None),
                "customer_name": names.get(getattr(r, "customer_id", None), "—"),
                "status": getattr(r, "status", "Aktif")
            })
    except Exception:
        abone_rows = []

    return templates.TemplateResponse(
        request,
        "btk/index.html",
        {
            "active_tab": active,
            "operations": operations,
            "abone_rows": abone_rows,
            "title": "BTK İşlemleri"
        }
    )