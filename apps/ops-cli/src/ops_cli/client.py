from __future__ import annotations

import json
import re
from typing import Any

import httpx


class APIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def recoverable(self) -> bool:
        return self.status_code is None or self.status_code >= 500


class Client:
    def __init__(self, base_url: str, token: str, transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {token}"} if token else {},
            follow_redirects=False,
            timeout=20,
            transport=transport,
        )

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise APIError("network request failed") from exc
        if response.is_redirect:
            raise APIError("server redirect refused")
        if response.status_code >= 400:
            suffix = ""
            if response.status_code == 422:
                try:
                    details = response.json().get("detail")
                    fields = []
                    for item in details if isinstance(details, list) else []:
                        if not isinstance(item, dict) or not isinstance(item.get("loc"), list):
                            continue
                        path = ".".join(str(part) for part in item["loc"])
                        if re.fullmatch(r"[a-zA-Z0-9_.]{1,160}", path):
                            fields.append(path)
                    if fields:
                        suffix = ": invalid fields " + ", ".join(fields[:10])
                except ValueError, AttributeError:
                    pass
            raise APIError(
                f"server returned HTTP {response.status_code}{suffix}",
                status_code=response.status_code,
            )
        if response.status_code == 204 or not response.content:
            return None
        try:
            return response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise APIError("server returned an invalid response") from exc


def resolve_org(client: Client, value: str) -> dict:
    offset = 0
    matches: list[dict] = []
    while True:
        page = client.request(
            "GET", "/platform/cli/orgs", params={"search": value, "limit": 100, "offset": offset}
        )
        items = page.get("items", [])
        matches.extend(
            item for item in items if item.get("id") == value or item.get("slug") == value
        )
        offset += len(items)
        if not items or offset >= page.get("total", 0):
            break
    unique = {item["id"]: item for item in matches}
    if len(unique) != 1:
        raise APIError(f"organization {value!r} was not found exactly")
    return next(iter(unique.values()))
