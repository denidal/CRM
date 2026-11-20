"""Standalone BTK log worker process.

Schedules (TR, matching old Next.js worker):
  - Oturum:          every hour at :05
  - Abone hareket:   daily 00:15
  - Abone rehber:    daily 01:00
  - IP blok:         monthly day 1 & 16 at 02:00

Usage:
  python -m system.workers.btk_log_worker
  python -m system.workers.btk_log_worker --once oturum
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("btk-worker")


def _safe(name: str, fn) -> None:
    try:
        result = fn()
        log.info("%s OK: %s records=%s", name, result.get("fileName"), result.get("recordCount"))
    except Exception as exc:  # noqa: BLE001
        log.error("%s FAIL: %s", name, exc)


def run_once(job: str) -> None:
    from system.services.btk_log_service import BtkLogService
    from system.workers.btk_ipblock import automate_btk_ip_block_log

    svc = BtkLogService()
    mapping = {
        "oturum": svc.automate_oturum,
        "abone_hareket": svc.automate_abone_hareket,
        "abone_rehber": svc.automate_abone_rehber,
        "ip_block": automate_btk_ip_block_log,
    }
    if job not in mapping:
        raise SystemExit(f"Bilinmeyen job: {job}. Seçenekler: {', '.join(mapping)}")
    _safe(job, mapping[job])


def run_loop() -> None:
    import schedule

    from system.services.btk_log_service import BtkLogService
    from system.workers.btk_ipblock import automate_btk_ip_block_log, should_run_today

    svc = BtkLogService()

    schedule.every().hour.at(":05").do(lambda: _safe("oturum", svc.automate_oturum))
    schedule.every().day.at("00:15").do(lambda: _safe("abone_hareket", svc.automate_abone_hareket))
    schedule.every().day.at("01:00").do(lambda: _safe("abone_rehber", svc.automate_abone_rehber))

    def ip_job() -> None:
        if should_run_today():
            _safe("ip_block", automate_btk_ip_block_log)
        else:
            log.info("ip_block: bugün atlandı")

    schedule.every().day.at("02:00").do(ip_job)

    log.info("BTK worker başladı (oturum@:05, hareket@00:15, rehber@01:00, ipblok@02:00 1/16)")
    while True:
        schedule.run_pending()
        time.sleep(20)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", choices=["oturum", "abone_hareket", "abone_rehber", "ip_block"])
    args = parser.parse_args(argv)
    if args.once:
        run_once(args.once)
    else:
        run_loop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
