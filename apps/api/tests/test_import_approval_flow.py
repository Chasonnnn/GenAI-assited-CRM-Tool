"""Contract tests for CSV import approval workflow."""

import io
import pytest
from httpx import AsyncClient


def make_csv(rows: list[dict]) -> bytes:
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))
    return "\n".join(lines).encode("utf-8")


@pytest.mark.asyncio
async def test_import_submit_and_approval_flow(authed_client: AsyncClient, db, test_org, test_user):
    from app.services import surrogate_service
    from app.schemas.surrogate import SurrogateCreate
    from app.db.enums import SurrogateSource

    rows = [
        {"full_name": "Alpha", "email": "alpha@example.com"},
        {"full_name": "Beta", "email": "beta@example.com"},
    ]

    # Seed a duplicate in DB
    surrogate_service.create_surrogate(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        data=SurrogateCreate(
            full_name="Existing Alpha",
            email="alpha@example.com",
            source=SurrogateSource.IMPORT,
        ),
    )
    csv_data = make_csv(rows)

    preview = await authed_client.post(
        "/surrogates/import/preview",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    preview_data = preview.json()
    import_id = preview_data["import_id"]

    submit = await authed_client.post(
        f"/surrogates/import/{import_id}/submit",
        json={
            "column_mappings": [
                {"csv_column": "full_name", "surrogate_field": "full_name"},
                {"csv_column": "email", "surrogate_field": "email"},
            ]
        },
    )
    assert submit.status_code == 200, submit.text
    submit_data = submit.json()
    assert submit_data["status"] == "awaiting_approval"
    assert "deduplication_stats" in submit_data
    assert submit_data["deduplication_stats"]["total"] == 2
    assert submit_data["deduplication_stats"]["new_records"] == 1
    assert len(submit_data["deduplication_stats"]["duplicates"]) == 1

    pending = await authed_client.get("/surrogates/import/pending")
    assert pending.status_code == 200, pending.text
    pending_item = next(item for item in pending.json() if item["id"] == import_id)
    assert pending_item["column_mapping_snapshot"]
    assert pending_item["deduplication_stats"]["duplicates"]

    approve = await authed_client.post(f"/surrogates/import/{import_id}/approve")
    assert approve.status_code == 200, approve.text
    assert approve.json()["status"] in {"approved", "processing"}


@pytest.mark.asyncio
async def test_import_reject_requires_reason(authed_client: AsyncClient):
    rows = [{"full_name": "Gamma", "email": "gamma@example.com"}]
    csv_data = make_csv(rows)

    preview = await authed_client.post(
        "/surrogates/import/preview",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    import_id = preview.json()["import_id"]

    submit = await authed_client.post(f"/surrogates/import/{import_id}/submit")
    assert submit.status_code == 200, submit.text

    reject = await authed_client.post(
        f"/surrogates/import/{import_id}/reject",
        json={"reason": "Invalid mapping"},
    )
    assert reject.status_code == 200, reject.text
    assert reject.json()["status"] == "rejected"
    assert reject.json()["rejection_reason"] == "Invalid mapping"
