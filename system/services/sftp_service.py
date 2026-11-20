"""SFTP service facade used by BTK pipeline."""

from system.services.file_transfer import UploadResult, upload_sftp


class SftpService:
    def upload(self, local_path: str, remote_name: str, file_type: str = "oturum") -> UploadResult:
        return upload_sftp(local_path, remote_name, file_type)  # type: ignore[arg-type]
