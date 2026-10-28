from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app import app


def test_index_sorts_all_records_before_flask_pagination():
    schema = [
        {
            "id": "tbl1",
            "name": "Projects",
            "primaryFieldId": "fldTitle",
            "fields": [
                {"id": "fldTitle", "name": "Title", "type": "singleLineText"}
            ],
        }
    ]
    beginning = datetime(2025, 1, 1, tzinfo=timezone.utc)
    records = [
        {
            "id": f"rec{number:03d}",
            "createdTime": (beginning + timedelta(days=number)).isoformat(),
            "fields": {"Title": f"Project {number:03d}"},
        }
        for number in range(205)
    ]

    with patch("app.get_tables", return_value=schema), patch("app.get_client") as client:
        client.return_value.iter_records.side_effect = lambda *args, **kwargs: iter(records)
        browser = app.test_client()

        newest_page = browser.get("/?table=tbl1")
        oldest_page = browser.get("/?table=tbl1&page=3")

    assert newest_page.status_code == 200
    assert b"Project 204" in newest_page.data
    assert b"Project 000" not in newest_page.data
    assert b"page 1 of 3" in newest_page.data
    assert b"Project 000" in oldest_page.data
    assert b"page 3 of 3" in oldest_page.data
