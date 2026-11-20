"""FTP/SFTP upload helpers for BTK logs."""

from __future__ import annotations

import gzip
import os
from dataclasses import dataclass
from ftplib import FTP, FTP_TLS
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text

from data.config.db import get_app_engine

FileType = Literal["oturum", "abone_rehber", "abone_hareket", "ip_block"]


@dataclass
class UploadResult:
    uploaded: bool = False
    error: str | None = None
    upload_path: str | None = None


def _settings(table: str) -> dict[str, Any] | None:
    with get_app_engine().connect() as conn:
        try:
            row = conn.execute(
                text(f"SELECT * FROM {table} WHERE enabled IN (1, TRUE) ORDER BY id DESC LIMIT 1")
            ).mappings().first()
        except Exception:
            return None
        return dict(row) if row else None


def _subdir(file_type: FileType, settings: dict[str, Any]) -> str:
    special = {
        "oturum": settings.get("oturum_directory"),
        "abone_hareket": settings.get("abone_hareket_directory"),
        "abone_rehber": settings.get("abone_rehber_directory"),
        "ip_block": settings.get("ip_block_directory"),
    }.get(file_type)
    if special:
        return str(special).rstrip("/") or "/"
    base = (settings.get("directory") or "/").rstrip("/") or "/"
    sub = {
        "oturum": "oturum",
        "abone_rehber": "abone_rehber",
        "abone_hareket": "abone_hareket",
        "ip_block": "ip_block",
    }[file_type]
    return f"/{sub}" if base == "/" else f"{base}/{sub}"


def upload_ftp(local_path: str, file_name: str, file_type: FileType, *, already_gzip: bool = False) -> UploadResult:
    settings = _settings("ftp_settings")
    if not settings:
        return UploadResult(error=None)
    result = UploadResult()
    upload_dir = _subdir(file_type, settings)
    remote_name = file_name if already_gzip or file_name.endswith(".gz") else f"{file_name}.gz"
    temp_gz: Path | None = None
    try:
        path = Path(local_path)
        if not already_gzip and not file_name.endswith(".gz"):
            temp_gz = path.with_suffix(path.suffix + ".gz.tmp")
            temp_gz.write_bytes(gzip.compress(path.read_bytes()))
            upload_path = temp_gz
        else:
            upload_path = path

        host = settings["host"]
        port = int(settings.get("port") or 21)
        user = settings.get("username") or ""
        password = settings.get("password") or ""
        secure = bool(settings.get("secure"))
        ftp: FTP = FTP_TLS() if secure else FTP()
        ftp.connect(host, port, timeout=30)
        ftp.login(user, password)
        if secure and isinstance(ftp, FTP_TLS):
            ftp.prot_p()
        # ensure dirs
        parts = [p for p in upload_dir.split("/") if p]
        cur = ""
        for part in parts:
            cur += "/" + part
            try:
                ftp.cwd(cur)
            except Exception:
                try:
                    ftp.mkd(cur)
                    ftp.cwd(cur)
                except Exception:
                    pass
        with upload_path.open("rb") as fh:
            ftp.storbinary(f"STOR {remote_name}", fh)
        ftp.quit()
        result.uploaded = True
        result.upload_path = f"{upload_dir}/{remote_name}"
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
    finally:
        if temp_gz and temp_gz.exists():
            try:
                temp_gz.unlink()
            except OSError:
                pass
    return result


def upload_sftp(local_path: str, file_name: str, file_type: FileType, *, already_gzip: bool = False) -> UploadResult:
    settings = _settings("sftp_settings")
    if not settings:
        return UploadResult()
    result = UploadResult()
    try:
        import paramiko
    except ImportError:
        return UploadResult(error="paramiko yüklü değil")

    upload_dir = _subdir(file_type, settings)
    remote_name = file_name if already_gzip or file_name.endswith(".gz") else f"{file_name}.gz"
    temp_gz: Path | None = None
    transport = None
    try:
        path = Path(local_path)
        if not already_gzip and not file_name.endswith(".gz"):
            temp_gz = path.with_suffix(path.suffix + ".gz.tmp")
            temp_gz.write_bytes(gzip.compress(path.read_bytes()))
            upload_path = temp_gz
        else:
            upload_path = path

        host = settings["host"]
        port = int(settings.get("port") or 22)
        username = settings.get("username") or ""
        transport = paramiko.Transport((host, port))
        if settings.get("private_key"):
            from io import StringIO

            pkey = paramiko.RSAKey.from_private_key(
                StringIO(settings["private_key"]),
                password=settings.get("passphrase") or None,
            )
            transport.connect(username=username, pkey=pkey)
        else:
            transport.connect(username=username, password=settings.get("password") or "")
        sftp = paramiko.SFTPClient.from_transport(transport)
        assert sftp is not None
        parts = [p for p in upload_dir.split("/") if p]
        cur = ""
        for part in parts:
            cur += "/" + part
            try:
                sftp.stat(cur)
            except OSError:
                try:
                    sftp.mkdir(cur)
                except OSError:
                    pass
        remote = f"{upload_dir}/{remote_name}"
        sftp.put(str(upload_path), remote)
        sftp.close()
        result.uploaded = True
        result.upload_path = remote
    except Exception as exc:  # noqa: BLE001
        result.error = str(exc)
    finally:
        if transport:
            try:
                transport.close()
            except Exception:  # noqa: BLE001
                pass
        if temp_gz and temp_gz.exists():
            try:
                temp_gz.unlink()
            except OSError:
                pass
    return result
