"""BTK log generate / save / automate (oturum, abone hareket, abone rehber)."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import text

from data.config.db import get_app_engine, get_radius_engine
from system.services.btk_format import (
    HAREKET_ACIKLAMALARI_BTK,
    clean_btk_value,
    encode_iso8859_9,
    format_date_btk,
    now_stamp,
)
from system.services.btk_lock import acquire_lock, release_lock
from system.services.file_transfer import upload_ftp, upload_sftp

FileType = Literal["oturum", "abone_rehber", "abone_hareket", "ip_block"]
LOGS_DIR = Path(os.getenv("BTK_LOGS_DIR", Path.cwd() / "uploads" / "btk_logs"))
OPERATOR = os.getenv("BTK_OPERATOR_NAME", "INTERFIBER")
OPERATOR_KOD = os.getenv("OPERATOR_KOD", "810")

# Abone hareket / rehber kolon sırası (BTK pipe format)
ABONE_FIELDS = [
    "OPERATOR_KOD", "MUSTERI_ID", "HAT_NO", "HAT_DURUM", "HAT_DURUM_KODU", "HAT_ACIKLAMA",
    "MUSTERI_HAREKET_KODU", "MUSTERI_HAREKET_ACIKLAMA", "MUSTERI_HAREKET_ZAMANI",
    "HIZMET_TIPI", "MUSTERI_TIPI", "ABONE_BASLANGIC", "ABONE_BITIS",
    "ABONE_ADI", "ABONE_SOYADI", "ABONE_TC_KIMLIK_NO", "ABONE_PASAPORT_NO",
    "ABONE_UNVAN", "ABONE_VERGI_NUMARASI", "ABONE_MERSIS_NUMARASI",
    "ABONE_CINSIYET", "ABONE_UYRUK", "ABONE_BABA_ADI", "ABONE_ANA_ADI",
    "ABONE_ANNE_KIZLIK_SOYADI", "ABONE_DOGUM_YERI", "ABONE_DOGUM_TARIHI",
    "ABONE_MESLEK", "ABONE_TARIFE",
    "ABONE_KIMLIK_CILT_NO", "ABONE_KIMLIK_KUTUK_NO", "ABONE_KIMLIK_SAYFA_NO",
    "ABONE_KIMLIK_IL", "ABONE_KIMLIK_ILCE", "ABONE_KIMLIK_MAHALLE_KOY",
    "ABONE_KIMLIK_TIPI", "ABONE_KIMLIK_SERI_NO", "ABONE_KIMLIK_VERILDIGI_YER",
    "ABONE_KIMLIK_VERILDIGI_TARIH", "ABONE_KIMLIK_AIDIYETI",
    "ABONE_ADRES_TESIS_IL", "ABONE_ADRES_TESIS_ILCE", "ABONE_ADRES_TESIS_MAHALLE",
    "ABONE_ADRES_TESIS_CADDE", "ABONE_ADRES_TESIS_DIS_KAPI", "ABONE_ADRES_TESIS_IC_KAPI",
    "ABONE_ADRES_TESIS_POSTA_KODU", "ABONE_ADRES_TESIS_ADRES_KODU",
    "STATIK_IP", "ISS_HIZ_PROFILI", "ISS_KULLANICI_ADI", "ISS_POP_BILGISI",
]


def _ensure_ops_table(conn) -> None:
    from data.config.db import init_schema, is_postgres

    if is_postgres():
        init_schema()
        return
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS btk_log_operations (
              id INT AUTO_INCREMENT PRIMARY KEY,
              log_type VARCHAR(30) NOT NULL,
              file_name VARCHAR(255) NOT NULL,
              file_path VARCHAR(500),
              record_count INT DEFAULT 0,
              local_saved TINYINT(1) DEFAULT 0,
              ftp_uploaded TINYINT(1) DEFAULT 0,
              ftp_error TEXT,
              ftp_upload_path VARCHAR(500),
              sftp_uploaded TINYINT(1) DEFAULT 0,
              sftp_error TEXT,
              sftp_upload_path VARCHAR(500),
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              created_by VARCHAR(100) DEFAULT 'system',
              INDEX idx_log_type (log_type),
              INDEX idx_created_at (created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
    )


class BtkLogService:
    def generate_oturum(self, hours: int = 1) -> dict[str, Any]:
        q = text(
            """
            SELECT id, acctuniqueid, kullaniciAdi, ipAdres, oturumBaslamaTarihi,
                   oturumLogTarihi, uploadByte, downloadByte, baglantiKesimMesaj,
                   oturumDurum, baglantiPVC
            FROM oturum_log
            WHERE (
              (oturumBaslamaTarihi >= DATE_SUB(NOW(), INTERVAL :h HOUR) AND oturumBaslamaTarihi < NOW())
              OR (oturumLogTarihi >= DATE_SUB(NOW(), INTERVAL :h HOUR) AND oturumLogTarihi < NOW())
            )
            ORDER BY oturumBaslamaTarihi ASC, oturumLogTarihi ASC
            """
        )
        with get_radius_engine().connect() as conn:
            rows = conn.execute(q, {"h": hours}).mappings().all()
        lines: list[str] = []
        for r in rows:
            stop_msg = (
                clean_btk_value(r.get("baglantiKesimMesaj"))
                if r.get("oturumDurum") == "session_stop"
                else ""
            )
            lines.append(
                "|".join(
                    [
                        clean_btk_value(r.get("kullaniciAdi")),
                        clean_btk_value(r.get("ipAdres")),
                        format_date_btk(r.get("oturumBaslamaTarihi")),
                        format_date_btk(r.get("oturumLogTarihi") or r.get("oturumBaslamaTarihi")),
                        str(r.get("uploadByte") or 0),
                        str(r.get("downloadByte") or 0),
                        stop_msg,
                        str(r.get("oturumDurum") or "session_start"),
                        clean_btk_value(r.get("baglantiPVC")),
                        clean_btk_value(r.get("acctuniqueid")),
                    ]
                )
            )
        content = "".join(f"{ln}\n" for ln in lines)
        file_name = f"{OPERATOR}_METRO_OTURUM_{now_stamp()}_01.log"
        return {"success": True, "content": content, "fileName": file_name, "recordCount": len(lines)}

    def _abone_line(self, row: dict[str, Any]) -> str:
        vals: list[str] = []
        for key in ABONE_FIELDS:
            if key == "MUSTERI_HAREKET_ACIKLAMA":
                try:
                    kod = int(row.get("MUSTERI_HAREKET_KODU") or 0)
                except (TypeError, ValueError):
                    kod = 0
                vals.append(clean_btk_value(HAREKET_ACIKLAMALARI_BTK.get(kod, "")))
            elif key in {"MUSTERI_HAREKET_ZAMANI", "ABONE_BASLANGIC", "ABONE_BITIS", "ABONE_DOGUM_TARIHI", "ABONE_KIMLIK_VERILDIGI_TARIH"}:
                vals.append(format_date_btk(row.get(key)))
            elif key == "OPERATOR_KOD":
                vals.append(clean_btk_value(row.get(key) or OPERATOR_KOD))
            else:
                vals.append(clean_btk_value(row.get(key)))
        return "|".join(vals)

    def generate_abone_hareket(self, days: int = 1) -> dict[str, Any]:
        q = text(
            """
            SELECT * FROM btk_abone_hareket
            WHERE MUSTERI_HAREKET_ZAMANI >= DATE_SUB(NOW(), INTERVAL :d DAY)
            ORDER BY MUSTERI_HAREKET_ZAMANI ASC
            """
        )
        with get_app_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(q, {"d": days}).mappings().all()]
        lines = [self._abone_line(r) for r in rows]
        content = "".join(f"{ln}\n" for ln in lines)
        file_name = f"{OPERATOR}_ABONE_HAREKET_{now_stamp()}_01.log"
        return {"success": True, "content": content, "fileName": file_name, "recordCount": len(lines)}

    def generate_abone_rehber(self) -> dict[str, Any]:
        q = text("SELECT * FROM btk_abone_rehber ORDER BY id ASC")
        with get_app_engine().connect() as conn:
            rows = [dict(r) for r in conn.execute(q).mappings().all()]
        lines = [self._abone_line(r) for r in rows]
        content = "".join(f"{ln}\n" for ln in lines)
        file_name = f"{OPERATOR}_ABONE_REHBER_{now_stamp()}_01.log"
        return {"success": True, "content": content, "fileName": file_name, "recordCount": len(lines)}

    def save_log(
        self,
        file_content: str | bytes,
        file_name: str,
        file_type: FileType,
        *,
        record_count: int | None = None,
        already_gzip: bool = False,
    ) -> dict[str, Any]:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        clean_name = "".join(c for c in file_name if c not in '<>:"/\\|?*').strip()
        path = LOGS_DIR / clean_name
        if path.exists():
            stem, ext = path.stem, path.suffix
            path = LOGS_DIR / f"{stem}_{now_stamp()}{ext}"
            clean_name = path.name

        if isinstance(file_content, str):
            data = encode_iso8859_9(file_content)
        else:
            data = file_content
        path.write_bytes(data)

        ftp = upload_ftp(str(path), clean_name, file_type, already_gzip=already_gzip)
        sftp = upload_sftp(str(path), clean_name, file_type, already_gzip=already_gzip)

        if record_count is None:
            if isinstance(file_content, str):
                record_count = len([ln for ln in file_content.splitlines() if ln.strip()])
            else:
                record_count = 0

        op_id = None
        with get_app_engine().begin() as conn:
            _ensure_ops_table(conn)
            res = conn.execute(
                text(
                    """
                    INSERT INTO btk_log_operations
                    (log_type, file_name, file_path, record_count, local_saved,
                     ftp_uploaded, ftp_error, ftp_upload_path,
                     sftp_uploaded, sftp_error, sftp_upload_path, created_by)
                    VALUES
                    (:t, :fn, :fp, :rc, 1, :fu, :fe, :fup, :su, :se, :sup, 'system')
                    """
                ),
                {
                    "t": file_type,
                    "fn": clean_name,
                    "fp": str(path),
                    "rc": record_count,
                    "fu": 1 if ftp.uploaded else 0,
                    "fe": ftp.error,
                    "fup": ftp.upload_path,
                    "su": 1 if sftp.uploaded else 0,
                    "se": sftp.error,
                    "sup": sftp.upload_path,
                },
            )
            op_id = res.lastrowid

        return {
            "success": True,
            "fileName": clean_name,
            "filePath": str(path),
            "ftpUploaded": ftp.uploaded,
            "ftpError": ftp.error,
            "ftpUploadPath": ftp.upload_path,
            "sftpUploaded": sftp.uploaded,
            "sftpError": sftp.error,
            "sftpUploadPath": sftp.upload_path,
            "logOperationId": op_id,
            "recordCount": record_count,
        }

    def _automate(self, lock: str, generate_fn, file_type: FileType) -> dict[str, Any]:
        if not acquire_lock(lock):
            raise RuntimeError(f"Lock alınamadı: {lock}")
        try:
            gen = generate_fn()
            save = self.save_log(gen["content"], gen["fileName"], file_type, record_count=gen["recordCount"])
            parts = []
            if save["ftpUploaded"]:
                parts.append("FTP")
            if save["sftpUploaded"]:
                parts.append("SFTP")
            msg = "Log kaydedildi"
            if parts:
                msg += " + " + ",".join(parts)
            return {**save, "message": msg, "recordCount": gen["recordCount"]}
        finally:
            release_lock(lock)

    def automate_oturum(self) -> dict[str, Any]:
        return self._automate("btk_oturum_log_lock", lambda: self.generate_oturum(1), "oturum")

    def automate_abone_hareket(self) -> dict[str, Any]:
        return self._automate(
            "btk_abone_hareket_log_lock", lambda: self.generate_abone_hareket(1), "abone_hareket"
        )

    def automate_abone_rehber(self) -> dict[str, Any]:
        return self._automate(
            "btk_abone_rehber_log_lock", self.generate_abone_rehber, "abone_rehber"
        )

    def list_operations(self, limit: int = 50) -> list[dict[str, Any]]:
        with get_app_engine().connect() as conn:
            try:
                rows = conn.execute(
                    text(
                        "SELECT * FROM btk_log_operations ORDER BY id DESC LIMIT :n"
                    ),
                    {"n": limit},
                ).mappings().all()
            except Exception:
                return []
            return [dict(r) for r in rows]
