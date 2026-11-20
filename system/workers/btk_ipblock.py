"""BTK IP block log generation + automation (1st & 16th of month)."""

from __future__ import annotations

import gzip
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from data.config.db import get_app_engine  # noqa: E402
from system.services.btk_format import (  # noqa: E402
    clean_btk_value,
    encode_iso8859_9,
    format_date_btk,
    now_stamp,
)
from system.services.btk_lock import acquire_lock, release_lock  # noqa: E402
from system.services.btk_log_service import BtkLogService  # noqa: E402

OPERATOR = os.getenv("BTK_OPERATOR_NAME", "INTERFIBER")


def generate_ip_block_log(operator_name: str = OPERATOR) -> dict[str, Any]:
    with get_app_engine().connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM ip_blocks ORDER BY allocation_start_date ASC, id ASC")
        ).mappings().all()

    lines: list[str] = []
    for b in rows:
        end = (
            ""
            if int(b.get("service_type") or 0) == 17
            else format_date_btk(b.get("allocation_end_date") or datetime.now())
        )
        lines.append(
            "|".join(
                [
                    clean_btk_value(b.get("operator") or operator_name),
                    str(b.get("ip_start") or ""),
                    str(b.get("ip_end") or ""),
                    str(b.get("service_type") if b.get("service_type") is not None else "0"),
                    str(b.get("nat_application") if b.get("nat_application") is not None else "0"),
                    format_date_btk(b.get("allocation_start_date")),
                    end,
                    str(b.get("ip_block_type") or "S"),
                    clean_btk_value(b.get("usage_location")),
                ]
            )
        )
    content = "".join(f"{ln}\n" for ln in lines)
    encoded = encode_iso8859_9(content)
    gz = gzip.compress(encoded)
    file_name = f"{operator_name.upper()}_IPBLOK_{now_stamp()}_001.log.gz"
    return {
        "success": True,
        "content": gz,
        "fileName": file_name,
        "recordCount": len(lines),
    }


def automate_btk_ip_block_log() -> dict[str, Any]:
    lock = "btk_ip_block_log_lock"
    if not acquire_lock(lock):
        raise RuntimeError("IP block lock alınamadı")
    try:
        gen = generate_ip_block_log()
        save = BtkLogService().save_log(
            gen["content"],
            gen["fileName"],
            "ip_block",
            record_count=gen["recordCount"],
            already_gzip=True,
        )
        return {**save, "recordCount": gen["recordCount"], "message": "IP blok log kaydedildi"}
    finally:
        release_lock(lock)


def should_run_today(now: datetime | None = None) -> bool:
    n = now or datetime.now()
    return n.day in (1, 16)


def main() -> None:
    if os.getenv("BTK_IPBLOCK_FORCE") != "1" and not should_run_today():
        print(f"[btk_ipblock] Bugün ({datetime.now().day}) çalışma günü değil (1/16).")
        return
    result = automate_btk_ip_block_log()
    print("[btk_ipblock]", result.get("message"), result.get("fileName"), result.get("recordCount"))


if __name__ == "__main__":
    main()
