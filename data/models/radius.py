"""RADIUS user is external (radius DB). Link stored on ServiceSale.radius_username."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RadiusUserView:
    """Read-only view of a RADIUS `rm_users` row (not ORM — other engine)."""

    username: str
    staticipcm: Optional[str] = None
    staticipcpe: Optional[str] = None
    email: Optional[str] = None
    company: Optional[str] = None
    hat_no: Optional[str] = None
    srvid: Optional[int] = None
