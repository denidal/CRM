from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from system.services.btk_log_service import BtkLogService
from system.workers.btk_ipblock import automate_btk_ip_block_log, generate_ip_block_log

router = APIRouter(prefix="/btk")


@router.get("/operations")
def list_ops(limit: int = Query(50, le=500)):
    return {"success": True, "data": BtkLogService().list_operations(limit)}


@router.post("/run/{job}")
def run_job(job: str):
    svc = BtkLogService()
    try:
        if job == "oturum":
            return {"success": True, **svc.automate_oturum()}
        if job == "abone_hareket":
            return {"success": True, **svc.automate_abone_hareket()}
        if job == "abone_rehber":
            return {"success": True, **svc.automate_abone_rehber()}
        if job == "ip_block":
            return {"success": True, **automate_btk_ip_block_log()}
        raise HTTPException(400, f"Bilinmeyen job: {job}")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(500, str(exc)) from exc


@router.get("/preview/ip-block")
def preview_ip_block():
    gen = generate_ip_block_log()
    return {"success": True, "fileName": gen["fileName"], "recordCount": gen["recordCount"]}
