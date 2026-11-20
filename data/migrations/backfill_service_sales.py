#!/usr/bin/env python3
"""Backfill legacy contracts → service_sales (Customer 1──N ServiceSale).

Old Next.js app joined services by name:
  internet.otel_adi      ↔ customers.otel_adi
  hotspot.musteri_adi    ↔ customers.otel_adi
  interfiber.otel_adi    ↔ customers.otel_adi

This script:
  1) Ensures schema (service_sales + customer_id on legacy tables)
  2) Sets customer_id on internet / hotspot / interfiber (name + musteri_no)
  3) Inserts one ServiceSale per legacy contract (idempotent via legacy_table+legacy_id)
  4) Optionally attaches POP / RADIUS / hat from customer_* and btk_abone_rehber
  5) Links btk_abone_rehber.service_sale_id when possible

Usage (from PYTHON project root):
  python -m data.migrations.backfill_service_sales
  python -m data.migrations.backfill_service_sales --dry-run
  python -m data.migrations.backfill_service_sales --skip-enrich
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

# Allow `python data/migrations/backfill_service_sales.py` from project root
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.config.db import get_app_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def norm_name(value: Any) -> str:
    if value is None:
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def map_status(contract_durum: Any) -> str:
    d = (str(contract_durum or "")).strip().lower()
    if d in {"onaylandı", "onaylandi", "aktif", "active", "a"}:
        return "active"
    if d in {"tekliflendirildi", "teklif", "pending", "inactive"}:
        return "inactive"
    if d in {"bitti", "iptal", "kabul_edilmedi", "cancelled", "canceled", "i"}:
        return "cancelled"
    return "active" if d else "active"


def map_currency(value: Any) -> str:
    c = (str(value or "TL")).strip().upper()
    if c in {"TL", "TRY", "₺"}:
        return "TL"
    if c in {"USD", "$"}:
        return "USD"
    if c in {"EUR", "€"}:
        return "EUR"
    return c or "TL"


@dataclass
class Stats:
    customer_id_updated: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    inserted: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    skipped_existing: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    unmatched: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    enriched_pop: int = 0
    enriched_radius: int = 0
    enriched_hat: int = 0
    btk_linked: int = 0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def table_exists(conn: Connection, table: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = DATABASE() AND table_name = :t LIMIT 1"
        ),
        {"t": table},
    ).first()
    return row is not None


def column_exists(conn: Connection, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c LIMIT 1"
        ),
        {"t": table, "c": column},
    ).first()
    return row is not None


def index_exists(conn: Connection, table: str, index_name: str) -> bool:
    row = conn.execute(
        text(
            "SELECT 1 FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :i LIMIT 1"
        ),
        {"t": table, "i": index_name},
    ).first()
    return row is not None


def ensure_schema(conn: Connection, dry_run: bool) -> None:
    ddl_service_sales = """
    CREATE TABLE IF NOT EXISTS service_sales (
      id INT AUTO_INCREMENT PRIMARY KEY,
      customer_id INT NOT NULL,
      service_type VARCHAR(30) NOT NULL,
      status VARCHAR(30) NOT NULL DEFAULT 'active',
      pop_id INT NULL,
      radius_username VARCHAR(100) NULL,
      hat_no VARCHAR(50) NULL,
      paket_adi VARCHAR(255) NULL,
      internet_hiz VARCHAR(50) NULL,
      fiyat DECIMAL(15,2) NULL,
      para_birimi VARCHAR(10) NULL DEFAULT 'TL',
      sozlesme_no VARCHAR(100) NULL,
      sozlesme_suresi VARCHAR(50) NULL,
      sozlesme_baslangic_tarihi DATE NULL,
      sozlesme_bitis_tarihi DATE NULL,
      orijinal_sozlesme_no VARCHAR(100) NULL,
      hizmet_tipi VARCHAR(10) NULL,
      abone_baslangic DATE NULL,
      abone_bitis DATE NULL,
      contract_durum VARCHAR(50) NULL DEFAULT 'onaylandı',
      notes TEXT NULL,
      legacy_table VARCHAR(30) NULL,
      legacy_id INT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      INDEX idx_ss_customer (customer_id),
      INDEX idx_ss_pop (pop_id),
      INDEX idx_ss_hat (hat_no),
      INDEX idx_ss_type (service_type),
      UNIQUE KEY uq_ss_legacy (legacy_table, legacy_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    if dry_run:
        print("[dry-run] ensure service_sales + customer_id columns")
        return

    if not table_exists(conn, "service_sales"):
        conn.execute(text(ddl_service_sales))
        print("[schema] service_sales created")
    else:
        print("[schema] service_sales exists")
        if not index_exists(conn, "service_sales", "uq_ss_legacy"):
            # Unique index for idempotent backfill (ignore NULLs pairs if any)
            try:
                conn.execute(
                    text(
                        "ALTER TABLE service_sales "
                        "ADD UNIQUE KEY uq_ss_legacy (legacy_table, legacy_id)"
                    )
                )
                print("[schema] uq_ss_legacy added")
            except Exception as exc:  # noqa: BLE001
                print(f"[schema] uq_ss_legacy skip: {exc}")

    for table in ("internet", "hotspot", "interfiber"):
        if not table_exists(conn, table):
            print(f"[schema] skip missing table {table}")
            continue
        if not column_exists(conn, table, "customer_id"):
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN customer_id INT NULL"))
            print(f"[schema] {table}.customer_id added")
        idx = f"idx_{table}_customer"
        if not index_exists(conn, table, idx):
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD INDEX {idx} (customer_id)"))
            except Exception as exc:  # noqa: BLE001
                print(f"[schema] {idx} skip: {exc}")

    if table_exists(conn, "btk_abone_rehber") and not column_exists(
        conn, "btk_abone_rehber", "service_sale_id"
    ):
        conn.execute(
            text("ALTER TABLE btk_abone_rehber ADD COLUMN service_sale_id INT NULL")
        )
        try:
            conn.execute(
                text("ALTER TABLE btk_abone_rehber ADD INDEX idx_btk_ss (service_sale_id)")
            )
        except Exception:  # noqa: BLE001
            pass
        print("[schema] btk_abone_rehber.service_sale_id added")


# ---------------------------------------------------------------------------
# Customer lookup
# ---------------------------------------------------------------------------

def load_customers(conn: Connection) -> tuple[dict[str, list[dict]], dict[str, int]]:
    """Return (name→[{id, otel_adi, ...}], musteri_no→id)."""
    rows = conn.execute(
        text(
            "SELECT id, otel_adi, firma_unvan, musteri_no, pop_id, radius_username, durum "
            "FROM customers"
        )
    ).mappings().all()
    by_name: dict[str, list[dict]] = defaultdict(list)
    by_no: dict[str, int] = {}
    for r in rows:
        item = dict(r)
        key = norm_name(item.get("otel_adi"))
        if key:
            by_name[key].append(item)
        firma = norm_name(item.get("firma_unvan"))
        if firma and firma != key:
            by_name[firma].append(item)
        mno = (str(item.get("musteri_no") or "")).strip()
        if mno:
            by_no[mno] = int(item["id"])
    return by_name, by_no


def resolve_customer_id(
    *,
    name: Any,
    musteri_no: Any,
    customer_id: Any,
    by_name: dict[str, list[dict]],
    by_no: dict[str, int],
    stats: Stats,
    source: str,
) -> int | None:
    if customer_id not in (None, "", 0, "0"):
        try:
            return int(customer_id)
        except (TypeError, ValueError):
            pass

    mno = (str(musteri_no or "")).strip()
    if mno and mno in by_no:
        return by_no[mno]

    key = norm_name(name)
    if not key:
        return None
    matches = by_name.get(key) or []
    if not matches:
        return None
    if len(matches) > 1:
        stats.warnings.append(
            f"{source}: '{name}' → {len(matches)} müşteri; id={matches[0]['id']} seçildi"
        )
    return int(matches[0]["id"])


# ---------------------------------------------------------------------------
# Step 2: customer_id on legacy tables
# ---------------------------------------------------------------------------

def backfill_legacy_customer_ids(
    conn: Connection,
    by_name: dict[str, list[dict]],
    by_no: dict[str, int],
    stats: Stats,
    dry_run: bool,
) -> None:
    plans = [
        ("internet", "otel_adi", None),
        ("hotspot", "musteri_adi", "musteri_no"),
        ("interfiber", "otel_adi", None),
    ]
    for table, name_col, no_col in plans:
        if not table_exists(conn, table):
            continue
        cols = f"id, {name_col}, customer_id"
        if no_col and column_exists(conn, table, no_col):
            cols += f", {no_col}"
        rows = conn.execute(text(f"SELECT {cols} FROM {table}")).mappings().all()
        for row in rows:
            if row.get("customer_id"):
                continue
            cid = resolve_customer_id(
                name=row.get(name_col),
                musteri_no=row.get(no_col) if no_col else None,
                customer_id=None,
                by_name=by_name,
                by_no=by_no,
                stats=stats,
                source=f"{table}#{row['id']}",
            )
            if not cid:
                stats.unmatched[table] += 1
                continue
            stats.customer_id_updated[table] += 1
            if not dry_run:
                conn.execute(
                    text(f"UPDATE {table} SET customer_id = :cid WHERE id = :id"),
                    {"cid": cid, "id": row["id"]},
                )
        print(
            f"[customer_id] {table}: updated={stats.customer_id_updated[table]} "
            f"unmatched={stats.unmatched[table]}"
        )


# ---------------------------------------------------------------------------
# Step 3: insert service_sales
# ---------------------------------------------------------------------------

INSERT_SQL = text(
    """
    INSERT INTO service_sales (
      customer_id, service_type, status,
      pop_id, radius_username, hat_no,
      paket_adi, internet_hiz, fiyat, para_birimi,
      sozlesme_no, sozlesme_suresi, sozlesme_baslangic_tarihi, sozlesme_bitis_tarihi,
      orijinal_sozlesme_no, hizmet_tipi, abone_baslangic, abone_bitis,
      contract_durum, notes, legacy_table, legacy_id
    ) VALUES (
      :customer_id, :service_type, :status,
      :pop_id, :radius_username, :hat_no,
      :paket_adi, :internet_hiz, :fiyat, :para_birimi,
      :sozlesme_no, :sozlesme_suresi, :sozlesme_baslangic_tarihi, :sozlesme_bitis_tarihi,
      :orijinal_sozlesme_no, :hizmet_tipi, :abone_baslangic, :abone_bitis,
      :contract_durum, :notes, :legacy_table, :legacy_id
    )
    """
)


def existing_legacy_keys(conn: Connection) -> set[tuple[str, int]]:
    if not table_exists(conn, "service_sales"):
        return set()
    rows = conn.execute(
        text(
            "SELECT legacy_table, legacy_id FROM service_sales "
            "WHERE legacy_table IS NOT NULL AND legacy_id IS NOT NULL"
        )
    ).all()
    return {(str(t), int(i)) for t, i in rows}


def empty_sale(**kwargs: Any) -> dict[str, Any]:
    base = {
        "customer_id": None,
        "service_type": None,
        "status": "active",
        "pop_id": None,
        "radius_username": None,
        "hat_no": None,
        "paket_adi": None,
        "internet_hiz": None,
        "fiyat": None,
        "para_birimi": "TL",
        "sozlesme_no": None,
        "sozlesme_suresi": None,
        "sozlesme_baslangic_tarihi": None,
        "sozlesme_bitis_tarihi": None,
        "orijinal_sozlesme_no": None,
        "hizmet_tipi": None,
        "abone_baslangic": None,
        "abone_bitis": None,
        "contract_durum": None,
        "notes": None,
        "legacy_table": None,
        "legacy_id": None,
    }
    base.update(kwargs)
    return base


def iter_internet_rows(conn: Connection) -> Iterable[dict[str, Any]]:
    if not table_exists(conn, "internet"):
        return []
    # Select * then pick known fields — columns vary by migration history
    return [dict(r) for r in conn.execute(text("SELECT * FROM internet")).mappings().all()]


def iter_hotspot_rows(conn: Connection) -> Iterable[dict[str, Any]]:
    if not table_exists(conn, "hotspot"):
        return []
    return [dict(r) for r in conn.execute(text("SELECT * FROM hotspot")).mappings().all()]


def iter_interfiber_rows(conn: Connection) -> Iterable[dict[str, Any]]:
    if not table_exists(conn, "interfiber"):
        return []
    return [dict(r) for r in conn.execute(text("SELECT * FROM interfiber")).mappings().all()]


def build_sales_from_legacy(
    conn: Connection,
    by_name: dict[str, list[dict]],
    by_no: dict[str, int],
    stats: Stats,
) -> list[dict[str, Any]]:
    existing = existing_legacy_keys(conn)
    out: list[dict[str, Any]] = []

    for row in iter_internet_rows(conn):
        key = ("internet", int(row["id"]))
        if key in existing:
            stats.skipped_existing["internet"] += 1
            continue
        cid = resolve_customer_id(
            name=row.get("otel_adi"),
            musteri_no=None,
            customer_id=row.get("customer_id"),
            by_name=by_name,
            by_no=by_no,
            stats=stats,
            source=f"internet#{row['id']}",
        )
        if not cid:
            stats.unmatched["internet_sale"] += 1
            continue
        durum = row.get("durum")
        out.append(
            empty_sale(
                customer_id=cid,
                service_type="internet",
                status=map_status(durum),
                internet_hiz=row.get("internet_hiz"),
                paket_adi=row.get("internet_hiz"),
                fiyat=to_decimal(row.get("fiyat")),
                para_birimi=map_currency(row.get("para_birimi")),
                sozlesme_no=row.get("sozlesme_numarasi") or row.get("sozlesme_no"),
                sozlesme_baslangic_tarihi=to_date(
                    row.get("sozlesme_baslangic_tarihi") or row.get("sozlesme_tarihi")
                ),
                sozlesme_bitis_tarihi=to_date(row.get("sozlesme_bitis_tarihi")),
                contract_durum=str(durum) if durum is not None else None,
                notes=f"backfill from internet.id={row['id']} name={row.get('otel_adi')}",
                legacy_table="internet",
                legacy_id=int(row["id"]),
            )
        )

    for row in iter_hotspot_rows(conn):
        key = ("hotspot", int(row["id"]))
        if key in existing:
            stats.skipped_existing["hotspot"] += 1
            continue
        cid = resolve_customer_id(
            name=row.get("musteri_adi"),
            musteri_no=row.get("musteri_no"),
            customer_id=row.get("customer_id"),
            by_name=by_name,
            by_no=by_no,
            stats=stats,
            source=f"hotspot#{row['id']}",
        )
        if not cid:
            stats.unmatched["hotspot_sale"] += 1
            continue
        durum = row.get("durum")
        out.append(
            empty_sale(
                customer_id=cid,
                service_type="hotspot",
                status=map_status(durum),
                paket_adi=row.get("paket_adi"),
                internet_hiz=row.get("paket_adi"),
                fiyat=to_decimal(row.get("tutar") if row.get("tutar") is not None else row.get("fiyat")),
                para_birimi=map_currency(row.get("para_birimi")),
                sozlesme_no=row.get("sozlesme_no"),
                sozlesme_suresi=row.get("sozlesme_suresi"),
                sozlesme_baslangic_tarihi=to_date(row.get("sozlesme_baslangic_tarihi")),
                sozlesme_bitis_tarihi=to_date(row.get("sozlesme_bitis_tarihi")),
                orijinal_sozlesme_no=row.get("orijinal_sozlesme_no"),
                contract_durum=str(durum) if durum is not None else None,
                notes=f"backfill from hotspot.id={row['id']} name={row.get('musteri_adi')}",
                legacy_table="hotspot",
                legacy_id=int(row["id"]),
            )
        )

    for row in iter_interfiber_rows(conn):
        key = ("interfiber", int(row["id"]))
        if key in existing:
            stats.skipped_existing["interfiber"] += 1
            continue
        cid = resolve_customer_id(
            name=row.get("otel_adi"),
            musteri_no=None,
            customer_id=row.get("customer_id"),
            by_name=by_name,
            by_no=by_no,
            stats=stats,
            source=f"interfiber#{row['id']}",
        )
        if not cid:
            stats.unmatched["interfiber_sale"] += 1
            continue
        durum = row.get("durum")
        out.append(
            empty_sale(
                customer_id=cid,
                service_type="interfiber",
                status=map_status(durum),
                internet_hiz=row.get("internet_hiz"),
                paket_adi=row.get("internet_hiz"),
                fiyat=to_decimal(row.get("fiyat")),
                para_birimi=map_currency(row.get("para_birimi")),
                sozlesme_no=row.get("sozlesme_numarasi") or row.get("sozlesme_no"),
                sozlesme_baslangic_tarihi=to_date(
                    row.get("sozlesme_tarihi") or row.get("sozlesme_baslangic_tarihi")
                ),
                sozlesme_bitis_tarihi=to_date(row.get("sozlesme_bitis_tarihi")),
                contract_durum=str(durum) if durum is not None else None,
                notes=f"backfill from interfiber.id={row['id']} name={row.get('otel_adi')}",
                legacy_table="interfiber",
                legacy_id=int(row["id"]),
            )
        )

    return out


def insert_sales(conn: Connection, sales: list[dict[str, Any]], stats: Stats, dry_run: bool) -> None:
    for sale in sales:
        stats.inserted[sale["service_type"]] += 1
        if dry_run:
            continue
        conn.execute(INSERT_SQL, sale)
    total = sum(stats.inserted.values())
    print(f"[service_sales] insert candidates={total} dry_run={dry_run}")


# ---------------------------------------------------------------------------
# Step 4: enrich POP / RADIUS / hat
# ---------------------------------------------------------------------------

def load_customer_tech(conn: Connection) -> dict[int, dict[str, Any]]:
    """Best-effort technical defaults per customer (first POP / RADIUS / hat)."""
    tech: dict[int, dict[str, Any]] = defaultdict(dict)

    if table_exists(conn, "customers"):
        for r in conn.execute(
            text("SELECT id, pop_id, radius_username FROM customers")
        ).mappings():
            cid = int(r["id"])
            if r.get("pop_id"):
                tech[cid].setdefault("pop_id", int(r["pop_id"]))
            if r.get("radius_username"):
                tech[cid].setdefault("radius_username", r["radius_username"])

    if table_exists(conn, "customer_pops"):
        for r in conn.execute(
            text("SELECT customer_id, pop_id FROM customer_pops ORDER BY customer_id, pop_id")
        ).mappings():
            cid = int(r["customer_id"])
            if r.get("pop_id"):
                tech[cid].setdefault("pop_id", int(r["pop_id"]))

    if table_exists(conn, "customer_radius_users"):
        for r in conn.execute(
            text(
                "SELECT customer_id, radius_username, pop_id "
                "FROM customer_radius_users ORDER BY customer_id"
            )
        ).mappings():
            cid = int(r["customer_id"])
            if r.get("radius_username"):
                tech[cid].setdefault("radius_username", r["radius_username"])
            if r.get("pop_id"):
                tech[cid].setdefault("pop_id", int(r["pop_id"]))

    if table_exists(conn, "btk_abone_rehber"):
        for r in conn.execute(
            text(
                "SELECT MUSTERI_ID, HAT_NO, ISS_KULLANICI_ADI, HIZMET_TIPI, "
                "ABONE_BASLANGIC, ABONE_BITIS "
                "FROM btk_abone_rehber "
                "WHERE MUSTERI_ID IS NOT NULL "
                "ORDER BY MUSTERI_ID, id"
            )
        ).mappings():
            cid = int(r["MUSTERI_ID"])
            if r.get("HAT_NO"):
                tech[cid].setdefault("hat_no", str(r["HAT_NO"]))
            if r.get("ISS_KULLANICI_ADI"):
                tech[cid].setdefault("radius_username", r["ISS_KULLANICI_ADI"])
            if r.get("HIZMET_TIPI"):
                tech[cid].setdefault("hizmet_tipi", str(r["HIZMET_TIPI"]))
            if r.get("ABONE_BASLANGIC"):
                tech[cid].setdefault("abone_baslangic", to_date(r["ABONE_BASLANGIC"]))
            if r.get("ABONE_BITIS"):
                tech[cid].setdefault("abone_bitis", to_date(r["ABONE_BITIS"]))

    return tech


def enrich_service_sales(conn: Connection, stats: Stats, dry_run: bool) -> None:
    tech = load_customer_tech(conn)
    rows = conn.execute(
        text(
            "SELECT id, customer_id, pop_id, radius_username, hat_no, "
            "hizmet_tipi, abone_baslangic, abone_bitis "
            "FROM service_sales"
        )
    ).mappings().all()

    for row in rows:
        cid = int(row["customer_id"])
        t = tech.get(cid) or {}
        updates: dict[str, Any] = {"id": row["id"]}
        set_parts: list[str] = []

        if not row.get("pop_id") and t.get("pop_id"):
            set_parts.append("pop_id = :pop_id")
            updates["pop_id"] = t["pop_id"]
            stats.enriched_pop += 1
        if not row.get("radius_username") and t.get("radius_username"):
            set_parts.append("radius_username = :radius_username")
            updates["radius_username"] = t["radius_username"]
            stats.enriched_radius += 1
        if not row.get("hat_no") and t.get("hat_no"):
            set_parts.append("hat_no = :hat_no")
            updates["hat_no"] = t["hat_no"]
            stats.enriched_hat += 1
        if not row.get("hizmet_tipi") and t.get("hizmet_tipi"):
            set_parts.append("hizmet_tipi = :hizmet_tipi")
            updates["hizmet_tipi"] = t["hizmet_tipi"]
        if not row.get("abone_baslangic") and t.get("abone_baslangic"):
            set_parts.append("abone_baslangic = :abone_baslangic")
            updates["abone_baslangic"] = t["abone_baslangic"]
        if not row.get("abone_bitis") and t.get("abone_bitis"):
            set_parts.append("abone_bitis = :abone_bitis")
            updates["abone_bitis"] = t["abone_bitis"]

        if not set_parts:
            continue
        if dry_run:
            continue
        conn.execute(
            text(f"UPDATE service_sales SET {', '.join(set_parts)} WHERE id = :id"),
            updates,
        )

    print(
        f"[enrich] pop={stats.enriched_pop} radius={stats.enriched_radius} "
        f"hat={stats.enriched_hat} dry_run={dry_run}"
    )


# ---------------------------------------------------------------------------
# Step 5: link BTK abone rehber → service_sales
# ---------------------------------------------------------------------------

def link_btk_abone(conn: Connection, stats: Stats, dry_run: bool) -> None:
    if not table_exists(conn, "btk_abone_rehber"):
        print("[btk] table missing — skip")
        return
    if not column_exists(conn, "btk_abone_rehber", "service_sale_id"):
        print("[btk] service_sale_id column missing — skip")
        return

    # 1) Match by HAT_NO
    if not dry_run:
        result = conn.execute(
            text(
                """
                UPDATE btk_abone_rehber b
                JOIN service_sales s ON s.hat_no = b.HAT_NO
                SET b.service_sale_id = s.id
                WHERE b.HAT_NO IS NOT NULL
                  AND b.HAT_NO <> ''
                  AND (b.service_sale_id IS NULL OR b.service_sale_id = 0)
                """
            )
        )
        stats.btk_linked += result.rowcount or 0

    # 2) For remaining: attach to first internet service_sale of same MUSTERI_ID
    orphans = conn.execute(
        text(
            """
            SELECT b.id AS bid, b.MUSTERI_ID
            FROM btk_abone_rehber b
            WHERE b.MUSTERI_ID IS NOT NULL
              AND (b.service_sale_id IS NULL OR b.service_sale_id = 0)
            """
        )
    ).mappings().all()

    for o in orphans:
        sale = conn.execute(
            text(
                """
                SELECT id FROM service_sales
                WHERE customer_id = :cid
                ORDER BY
                  CASE service_type WHEN 'internet' THEN 0 WHEN 'interfiber' THEN 1 ELSE 2 END,
                  id ASC
                LIMIT 1
                """
            ),
            {"cid": int(o["MUSTERI_ID"])},
        ).first()
        if not sale:
            continue
        stats.btk_linked += 1
        if not dry_run:
            conn.execute(
                text(
                    "UPDATE btk_abone_rehber SET service_sale_id = :sid WHERE id = :bid"
                ),
                {"sid": int(sale[0]), "bid": int(o["bid"])},
            )

    print(f"[btk] linked≈{stats.btk_linked} dry_run={dry_run}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(dry_run: bool = False, skip_enrich: bool = False) -> Stats:
    engine: Engine = get_app_engine()
    stats = Stats()

    with engine.begin() as conn:
        print(f"=== backfill_service_sales dry_run={dry_run} ===")
        ensure_schema(conn, dry_run=dry_run)

        by_name, by_no = load_customers(conn)
        print(f"[customers] names={len(by_name)} musteri_no={len(by_no)}")

        backfill_legacy_customer_ids(conn, by_name, by_no, stats, dry_run=dry_run)

        sales = build_sales_from_legacy(conn, by_name, by_no, stats)
        insert_sales(conn, sales, stats, dry_run=dry_run)

        if not skip_enrich and (not dry_run or True):
            # In dry-run enrich only reports based on current DB state after inserts
            # (dry-run inserts are skipped, so enrich operates on existing rows).
            if not dry_run:
                enrich_service_sales(conn, stats, dry_run=False)
                link_btk_abone(conn, stats, dry_run=False)
            else:
                print("[dry-run] enrich/btk link skipped (no inserts committed)")

    print("--- summary ---")
    print("customer_id updates:", dict(stats.customer_id_updated))
    print("inserted:", dict(stats.inserted))
    print("skipped_existing:", dict(stats.skipped_existing))
    print("unmatched:", dict(stats.unmatched))
    print(
        f"enrich pop/radius/hat: {stats.enriched_pop}/{stats.enriched_radius}/{stats.enriched_hat}"
    )
    print(f"btk_linked: {stats.btk_linked}")
    if stats.warnings:
        print(f"warnings ({len(stats.warnings)}), first 20:")
        for w in stats.warnings[:20]:
            print("  -", w)
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill service_sales from legacy contracts")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Schema/data changes yapılmaz; sadece sayım",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="POP/RADIUS/hat ve BTK link adımlarını atla",
    )
    args = parser.parse_args(argv)
    run(dry_run=args.dry_run, skip_enrich=args.skip_enrich)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
