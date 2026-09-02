from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from typing import Callable

from nimbus_support.pii import redact
from nimbus_support.tickets import Ticket

Poster = Callable[[str, dict, dict[str, str]], dict]


def sink_from_settings(settings) -> ZendeskSink | None:
    sink = ZendeskSink(
        subdomain=getattr(settings, "zendesk_subdomain", "") or "",
        email=getattr(settings, "zendesk_email", "") or "",
        api_token=getattr(settings, "zendesk_api_token", "") or "",
    )
    return sink if sink.enabled else None


def _default_poster(url: str, body: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read().decode("utf-8")
    return json.loads(raw) if raw else {}


class ZendeskSink:
    """Optional Zendesk Tickets API. Local JSON still stores the ticket if this fails."""

    def __init__(
        self,
        *,
        subdomain: str,
        email: str,
        api_token: str,
        poster: Poster | None = None,
    ) -> None:
        self.subdomain = subdomain.strip()
        self.email = email.strip()
        self.api_token = api_token.strip()
        self._poster = poster or _default_poster

    @property
    def enabled(self) -> bool:
        return bool(self.subdomain and self.email and self.api_token)

    def publish(self, ticket: Ticket) -> str | None:
        if not self.enabled:
            return None
        token = base64.b64encode(f"{self.email}/token:{self.api_token}".encode()).decode()
        payload = {
            "ticket": {
                "subject": f"[{ticket.id}] {ticket.route}: {ticket.query[:80]}",
                "comment": {
                    "body": redact(
                        f"{ticket.summary}\n\nCustomer:\n{ticket.query}\n\n"
                        f"Route: {ticket.route}\nNimbus id: {ticket.id}"
                    )
                },
                "tags": ["nimbus-agent", ticket.route],
            }
        }
        url = f"https://{self.subdomain}.zendesk.com/api/v2/tickets.json"
        try:
            data = self._poster(
                url,
                payload,
                {
                    "Authorization": f"Basic {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return None
        remote = (data.get("ticket") or {}).get("id")
        return str(remote) if remote is not None else None
