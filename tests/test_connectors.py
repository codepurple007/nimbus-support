from nimbus_support.config import PROJECT_ROOT
from nimbus_support.connectors.google import GoogleDriveConnector, GoogleSheetsConnector
from nimbus_support.connectors.local import LocalFolderConnector
from nimbus_support.connectors.sync import sync_connectors
from nimbus_support.connectors.urls import ingest_url
from nimbus_support.kb.chunking import load_help_center


def test_local_drive_folder_copies_markdown(tmp_path) -> None:
    source = PROJECT_ROOT / "data" / "connectors" / "drive"
    dest = tmp_path / "connected"
    written = LocalFolderConnector(source, name="drive").sync(dest)
    names = {path.name for path in written}
    assert "extended-warranty.md" in names
    assert (dest / "extended-warranty.md").read_text(encoding="utf-8").startswith("#")


def test_sync_connectors_lands_in_connected_dir(tmp_path, monkeypatch) -> None:
    from nimbus_support.config import Settings

    help_center = tmp_path / "help-center"
    help_center.mkdir()
    (help_center / "password-reset.md").write_text("# Password\nReset it.\n")
    monkeypatch.setenv("HELP_CENTER_DIR", str(help_center))
    monkeypatch.setenv("CONNECTORS_DIR", str(PROJECT_ROOT / "data" / "connectors"))
    settings = Settings()
    written = sync_connectors(settings)
    slugs = {path.stem for path in written}
    assert "extended-warranty" in slugs
    assert "sku-prices" in slugs
    loaded = load_help_center(help_center)
    assert {article.slug for article in loaded} >= {"password-reset", "extended-warranty", "sku-prices"}


def test_url_ingest_rejects_localhost(tmp_path) -> None:
    try:
        ingest_url("https://localhost/secret.md", tmp_path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "Private" in str(exc) or "https" in str(exc).lower()


def test_url_ingest_rejects_http(tmp_path) -> None:
    try:
        ingest_url("http://example.com/doc.md", tmp_path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "https" in str(exc).lower()


def test_google_drive_disabled_without_ids(tmp_path) -> None:
    connector = GoogleDriveConnector(folder_id="")
    assert connector.enabled is False
    assert connector.sync(tmp_path) == []


def test_google_drive_downloads_with_fake_fetch(tmp_path) -> None:
    files = {
        "https://www.googleapis.com/drive/v3/files?": (
            b'{"files":[{"id":"1","name":"warranty.md","mimeType":"text/markdown"}]}'
        ),
        "https://www.googleapis.com/drive/v3/files/1?alt=media": b"# Warranty\n24 months.\n",
    }

    def fetch(url: str, headers: dict[str, str]) -> bytes:
        for prefix, body in files.items():
            if url.startswith(prefix) or prefix in url:
                return body
        raise AssertionError(url)

    connector = GoogleDriveConnector(
        folder_id="folder",
        access_token="tok",
        fetch=fetch,
    )
    written = connector.sync(tmp_path)
    assert written[0].name == "warranty.md"
    assert "24 months" in written[0].read_text(encoding="utf-8")


def test_google_sheets_writes_csv(tmp_path) -> None:
    def fetch(url: str, headers: dict[str, str]) -> bytes:
        return b'{"values":[["sku","price"],["NIM-HUB-EW","29"]]}'

    connector = GoogleSheetsConnector(
        spreadsheet_id="sheet",
        access_token="tok",
        fetch=fetch,
    )
    written = connector.sync(tmp_path)
    assert written[0].name == "google-sheet.csv"
    assert "NIM-HUB-EW" in written[0].read_text(encoding="utf-8")
