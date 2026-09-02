from __future__ import annotations

import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

Fetcher = Callable[[str, dict[str, str]], bytes]


def _default_fetch(url: str, headers: dict[str, str]) -> bytes:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read()


def _token_from_service_account(path: Path) -> str | None:
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
    except ImportError:
        return None
    scopes = [
        "https://www.googleapis.com/auth/drive.readonly",
        "https://www.googleapis.com/auth/spreadsheets.readonly",
    ]
    creds = service_account.Credentials.from_service_account_file(str(path), scopes=scopes)
    creds.refresh(Request())
    return creds.token


class GoogleDriveConnector:
    """Optional Drive folder sync. Same dest as the local Drive folder connector."""

    name = "google-drive"

    def __init__(
        self,
        *,
        folder_id: str,
        access_token: str = "",
        service_account_file: str = "",
        fetch: Fetcher | None = None,
    ) -> None:
        self.folder_id = folder_id.strip()
        self.access_token = access_token.strip()
        self.service_account_file = service_account_file.strip()
        self._fetch = fetch or _default_fetch

    def _bearer(self) -> str:
        if self.access_token:
            return self.access_token
        if self.service_account_file:
            token = _token_from_service_account(Path(self.service_account_file))
            if token:
                return token
        return ""

    @property
    def enabled(self) -> bool:
        return bool(self.folder_id and (self.access_token or self.service_account_file))

    def sync(self, dest: Path) -> list[Path]:
        token = self._bearer()
        if not self.folder_id or not token:
            return []
        dest.mkdir(parents=True, exist_ok=True)
        headers = {"Authorization": f"Bearer {token}"}
        query = urllib.parse.urlencode(
            {
                "q": f"'{self.folder_id}' in parents and trashed = false",
                "fields": "files(id,name,mimeType)",
                "pageSize": "50",
            }
        )
        try:
            listing = json.loads(
                self._fetch(
                    f"https://www.googleapis.com/drive/v3/files?{query}", headers
                ).decode("utf-8")
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []
        written: list[Path] = []
        for file in listing.get("files") or []:
            name = file.get("name") or file.get("id")
            mime = file.get("mimeType") or ""
            file_id = file.get("id")
            if not file_id:
                continue
            try:
                body, filename = self._download(file_id, name, mime, headers)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            target = dest / filename
            target.write_bytes(body)
            written.append(target)
        return written

    def _download(
        self, file_id: str, name: str, mime: str, headers: dict[str, str]
    ) -> tuple[bytes, str]:
        if mime == "application/vnd.google-apps.document":
            url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
                "?mimeType=text/plain"
            )
            filename = Path(name).with_suffix(".md").name
            return self._fetch(url, headers), filename
        if mime == "application/vnd.google-apps.spreadsheet":
            url = (
                f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
                "?mimeType=text/csv"
            )
            filename = Path(name).with_suffix(".csv").name
            return self._fetch(url, headers), filename
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
        return self._fetch(url, headers), Path(name).name


class GoogleSheetsConnector:
    """Optional live sheet → CSV in the help center (pricing / SKUs)."""

    name = "google-sheets"

    def __init__(
        self,
        *,
        spreadsheet_id: str,
        range_name: str = "Sheet1",
        access_token: str = "",
        service_account_file: str = "",
        fetch: Fetcher | None = None,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id.strip()
        self.range_name = range_name.strip() or "Sheet1"
        self.access_token = access_token.strip()
        self.service_account_file = service_account_file.strip()
        self._fetch = fetch or _default_fetch

    def _bearer(self) -> str:
        if self.access_token:
            return self.access_token
        if self.service_account_file:
            token = _token_from_service_account(Path(self.service_account_file))
            if token:
                return token
        return ""

    @property
    def enabled(self) -> bool:
        return bool(self.spreadsheet_id and (self.access_token or self.service_account_file))

    def sync(self, dest: Path) -> list[Path]:
        token = self._bearer()
        if not self.spreadsheet_id or not token:
            return []
        dest.mkdir(parents=True, exist_ok=True)
        encoded_range = urllib.parse.quote(self.range_name, safe="")
        url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/"
            f"{self.spreadsheet_id}/values/{encoded_range}"
        )
        try:
            payload = json.loads(
                self._fetch(url, {"Authorization": f"Bearer {token}"}).decode("utf-8")
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []
        rows = payload.get("values") or []
        if not rows:
            return []
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerows(rows)
        target = dest / "google-sheet.csv"
        target.write_text(buffer.getvalue(), encoding="utf-8")
        return [target]
