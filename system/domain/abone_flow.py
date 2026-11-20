"""Abone provisioning flow — hizmet first; POP optional.

Old Next.js CreateAboneModal forced: POP → RADIUS → contract.
New flow: service/contract first; POP and RADIUS may be attached later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


HIZMET_TIPLERI = {
    "44": "ISS – Kurumsal İnternet",
    "45": "ISS – Bireysel İnternet",
    "34": "Metro Ethernet / Sabit İnternet",
    "40": "RF / Radyo Link Hizmeti",
}


@dataclass
class AboneCreateRequest:
    customer_id: int
    hizmet_tipi: str
    paket: str
    fiyat: Decimal
    para_birimi: str = "TL"
    hat_no: Optional[str] = None
    abone_baslangic: Optional[date] = None
    # Optional technical attachments — NOT required
    pop_id: Optional[int] = None
    radius_username: Optional[str] = None
    skip_validation: bool = False
    service_type: str = "internet"


def validate_abone_request(req: AboneCreateRequest) -> list[str]:
    """Validate commercial abone fields. POP is intentionally not required."""
    errors: list[str] = []
    if not req.customer_id:
        errors.append("customer_id zorunludur")
    if not req.hizmet_tipi or req.hizmet_tipi not in HIZMET_TIPLERI:
        errors.append("Geçerli bir hizmet tipi seçin")
    if not req.paket:
        errors.append("Paket seçimi zorunludur")
    if req.fiyat is None or req.fiyat <= 0:
        errors.append("Fiyat 0'dan büyük olmalıdır")
    # POP / RADIUS: optional — no errors if missing
    return errors
