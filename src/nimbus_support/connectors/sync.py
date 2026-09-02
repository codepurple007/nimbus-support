from __future__ import annotations

from pathlib import Path

from nimbus_support.config import Settings, get_settings
from nimbus_support.connectors.google import GoogleDriveConnector, GoogleSheetsConnector
from nimbus_support.connectors.local import LocalFolderConnector


def sync_connectors(settings: Settings | None = None) -> list[Path]:
    """Pull Drive/Sheets analogs into the help center. Safe to run with no Google keys."""
    settings = settings or get_settings()
    dest = settings.help_center_dir / "connected"
    written: list[Path] = []
    root = settings.connectors_dir
    written.extend(LocalFolderConnector(root / "drive", name="drive").sync(dest))
    written.extend(LocalFolderConnector(root / "sheets", name="sheets").sync(dest))

    drive = GoogleDriveConnector(
        folder_id=settings.google_drive_folder_id,
        access_token=settings.google_access_token,
        service_account_file=settings.google_service_account_file,
    )
    if drive.enabled:
        written.extend(drive.sync(dest))

    sheets = GoogleSheetsConnector(
        spreadsheet_id=settings.google_sheets_id,
        range_name=settings.google_sheets_range,
        access_token=settings.google_access_token,
        service_account_file=settings.google_service_account_file,
    )
    if sheets.enabled:
        written.extend(sheets.sync(dest))
    return written
