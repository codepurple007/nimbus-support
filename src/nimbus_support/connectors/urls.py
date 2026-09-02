from __future__ import annotations

import ipaddress
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from nimbus_support.kb.chunking import slugify

_ALLOWED_SUFFIX = {".md", ".csv", ".pdf", ".txt", ""}
_HTML = re.compile(r"<[^>]+>")


def ingest_url(url: str, dest: Path) -> Path:
    """Admin-only: fetch a public https page into the help center."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("Only https URLs are ingested.")
    _reject_private_host(parsed.hostname)
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in _ALLOWED_SUFFIX:
        raise ValueError("URL must point to .md, .csv, .pdf, .txt, or HTML.")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "nimbus-support/0.2"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = response.read()
            content_type = response.headers.get_content_type()
    except urllib.error.URLError as exc:
        raise ValueError(f"Could not fetch URL: {exc}") from exc

    name = Path(parsed.path).name or slugify(parsed.hostname)
    if suffix in {".pdf", ".csv"}:
        target = dest / name
        dest.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return target

    text = data.decode("utf-8", errors="replace")
    if content_type == "text/html" or (b"<html" in data[:200].lower()):
        text = _html_to_markdown(text)
        name = Path(name).with_suffix(".md").name
    elif suffix == ".txt":
        name = Path(name).with_suffix(".md").name
    elif not suffix:
        name = slugify(name or parsed.hostname) + ".md"
    target = dest / name
    dest.mkdir(parents=True, exist_ok=True)
    target.write_text(text.strip() + "\n", encoding="utf-8")
    return target


def _reject_private_host(hostname: str) -> None:
    host = hostname.lower().rstrip(".")
    if host in {"localhost", "metadata.google.internal"} or host.endswith(".local"):
        raise ValueError("Private hosts are not allowed.")
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve host: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise ValueError("Private hosts are not allowed.")


def _html_to_markdown(html: str) -> str:
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = _HTML.sub("", title_match.group(1)).strip() if title_match else "Imported page"
    body = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    body = re.sub(r"(?is)<style.*?>.*?</style>", " ", body)
    body = _HTML.sub(" ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return f"# {title}\n\n{body[:8000]}"
