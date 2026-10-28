from __future__ import annotations

import os
import math
from functools import lru_cache

from dotenv import load_dotenv
from flask import Flask, render_template, request, send_file

from airtable_client import AirtableClient, AirtableError, find_table
from word_export import build_document, format_value, safe_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "local-airtable-word-app")


def get_client() -> AirtableClient:
    token = os.getenv("AIRTABLE_TOKEN", "").strip()
    base_id = os.getenv("AIRTABLE_BASE_ID", "").strip()
    if not token or not base_id:
        raise AirtableError("Add AIRTABLE_TOKEN and AIRTABLE_BASE_ID to your .env file first.")
    return AirtableClient(token=token, base_id=base_id)


@lru_cache(maxsize=4)
def cached_schema(base_id: str, token_marker: str) -> list[dict]:
    # The full token is deliberately not stored in the cache key.
    del token_marker
    return get_client().get_schema()


def get_tables() -> list[dict]:
    client = get_client()
    return cached_schema(client.base_id, client.token[-6:])


def primary_field_for(table: dict) -> dict | None:
    primary_id = table.get("primaryFieldId")
    return next(
        (field for field in table.get("fields", []) if field.get("id") == primary_id),
        table.get("fields", [None])[0] if table.get("fields") else None,
    )


def record_cards(table: dict, records: list[dict]) -> list[dict]:
    """Create clear labels and short field previews for the record picker."""
    primary = primary_field_for(table)
    primary_name = primary.get("name") if primary else None
    field_types = {
        field.get("name"): field.get("type", "") for field in table.get("fields", [])
    }
    cards = []
    for record in records:
        values = record.get("fields", {})
        title = format_value(values.get(primary_name), field_types.get(primary_name, ""))
        preview = []
        for field in table.get("fields", []):
            name = field.get("name")
            if not name or name == primary_name or name not in values:
                continue
            value = format_value(values.get(name), field.get("type", ""))
            value = " ".join(value.split())
            if not value:
                continue
            preview.append({"label": name, "value": value[:140] + ("…" if len(value) > 140 else "")})
            if len(preview) == 4:
                break
        cards.append(
            {
                "id": record.get("id", ""),
                "title": title or "(untitled record)",
                "title_field": primary_name or "Primary field",
                "preview": preview,
            }
        )
    return cards


def sort_records_by_created_time(records: list[dict]) -> list[dict]:
    """Show newest Airtable records first; missing timestamps sort last."""
    return sorted(records, key=lambda record: record.get("createdTime", ""), reverse=True)


@app.get("/")
def index():
    selected = request.args.get("table", os.getenv("AIRTABLE_DEFAULT_TABLE", ""))
    query = request.args.get("q", "").strip().casefold()
    try:
        page = max(1, int(request.args.get("page", "1")))
    except ValueError:
        page = 1
    page_size = 100
    tables: list[dict] = []
    records: list[dict] = []
    cards: list[dict] = []
    total_records = 0
    total_pages = 1
    table = None
    error = None
    try:
        tables = get_tables()
        if selected:
            table = find_table(tables, selected)
        elif tables:
            table = tables[0]
        if table:
            # Airtable's first API page is not guaranteed to contain the newest
            # records, so collect every cursor page before sorting and slicing.
            records = list(get_client().iter_records(table["id"]))
            records = sort_records_by_created_time(records)
            if query:
                records = [
                    item
                    for item in records
                    if query in str(item.get("fields", {})).casefold()
                    or query in item.get("id", "").casefold()
                ]
            total_records = len(records)
            total_pages = max(1, math.ceil(total_records / page_size))
            page = min(page, total_pages)
            start = (page - 1) * page_size
            cards = record_cards(table, records[start : start + page_size])
    except AirtableError as exc:
        error = str(exc)
    return render_template(
        "index.html", tables=tables, table=table, records=records, cards=cards, error=error,
        selected=selected, query=request.args.get("q", ""), page=page,
        total_pages=total_pages, total_records=total_records
    )


@app.post("/download")
def download():
    table_identifier = request.form.get("table_id", "").strip()
    record_id = request.form.get("record_id", "").strip()
    try:
        tables = get_tables()
        table = find_table(tables, table_identifier)
        if not table:
            raise AirtableError("The selected table was not found in the base schema.")
        if not record_id:
            raise AirtableError("Enter or select an Airtable record ID.")
        record = get_client().get_record(table["id"], record_id)
        document = build_document(table, record)
        primary_field = primary_field_for(table)
        label = record_id
        if primary_field:
            label = str(record.get("fields", {}).get(primary_field.get("name"), record_id))
        filename = f"{safe_filename(table.get('name', 'table'))}-{safe_filename(label)}.docx"
        return send_file(
            document,
            as_attachment=True,
            download_name=filename,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except AirtableError as exc:
        return render_template("error.html", message=str(exc)), 400


@app.post("/refresh-schema")
def refresh_schema():
    cached_schema.cache_clear()
    return ("", 303, {"Location": "/"})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
