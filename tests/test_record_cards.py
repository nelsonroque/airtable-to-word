from app import primary_field_for, record_cards, sort_records_by_created_time


def test_record_cards_use_primary_field_and_add_preview():
    table = {
        "primaryFieldId": "fldTitle",
        "fields": [
            {"id": "fldStatus", "name": "Status", "type": "singleSelect"},
            {"id": "fldTitle", "name": "Project Title", "type": "singleLineText"},
            {"id": "fldOwner", "name": "Owner", "type": "singleCollaborator"},
        ],
    }
    records = [
        {
            "id": "rec123",
            "fields": {
                "Status": "Active",
                "Project Title": "Library Renovation",
                "Owner": {"name": "Ada"},
            },
        }
    ]

    cards = record_cards(table, records)

    assert cards[0]["title"] == "Library Renovation"
    assert cards[0]["title_field"] == "Project Title"
    assert cards[0]["preview"] == [
        {"label": "Status", "value": "Active"},
        {"label": "Owner", "value": "Ada"},
    ]


def test_records_are_sorted_newest_first_with_missing_dates_last():
    records = [
        {"id": "recOld", "createdTime": "2025-01-01T12:00:00.000Z"},
        {"id": "recMissing"},
        {"id": "recNew", "createdTime": "2026-10-28T12:00:00.000Z"},
    ]

    sorted_records = sort_records_by_created_time(records)

    assert [record["id"] for record in sorted_records] == [
        "recNew",
        "recOld",
        "recMissing",
    ]
