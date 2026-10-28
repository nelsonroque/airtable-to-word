"""Small read-only client for the Airtable Web API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator
from urllib.parse import quote

import requests


class AirtableError(RuntimeError):
    """A friendly wrapper around Airtable API errors."""


@dataclass(frozen=True)
class AirtableClient:
    token: str
    base_id: str
    timeout: int = 30

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            response = requests.get(
                url, headers=self.headers, params=params, timeout=self.timeout
            )
        except requests.RequestException as exc:
            raise AirtableError(f"Could not reach Airtable: {exc}") from exc

        if not response.ok:
            try:
                detail = response.json().get("error", response.text)
            except ValueError:
                detail = response.text
            if isinstance(detail, dict):
                detail = detail.get("message") or detail.get("type") or str(detail)
            raise AirtableError(f"Airtable returned {response.status_code}: {detail}")
        return response.json()

    def get_schema(self) -> list[dict[str, Any]]:
        url = f"https://api.airtable.com/v0/meta/bases/{quote(self.base_id)}/tables"
        return self._get(url).get("tables", [])

    def get_record(self, table_id: str, record_id: str) -> dict[str, Any]:
        table = quote(table_id, safe="")
        record = quote(record_id, safe="")
        url = f"https://api.airtable.com/v0/{quote(self.base_id)}/{table}/{record}"
        return self._get(url)

    def iter_records(
        self, table_id: str, *, page_size: int = 100, limit: int | None = None
    ) -> Iterator[dict[str, Any]]:
        table = quote(table_id, safe="")
        url = f"https://api.airtable.com/v0/{quote(self.base_id)}/{table}"
        offset: str | None = None
        yielded = 0
        while True:
            params: dict[str, Any] = {"pageSize": min(page_size, 100)}
            if offset:
                params["offset"] = offset
            payload = self._get(url, params)
            for record in payload.get("records", []):
                yield record
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            offset = payload.get("offset")
            if not offset:
                return


def find_table(tables: list[dict[str, Any]], identifier: str) -> dict[str, Any] | None:
    wanted = identifier.casefold()
    return next(
        (
            table
            for table in tables
            if table.get("id") == identifier
            or str(table.get("name", "")).casefold() == wanted
        ),
        None,
    )

