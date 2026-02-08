import io

import pytest
from httpx import AsyncClient

from app.core.config import settings


@pytest.mark.asyncio
async def test_preview_import_rejects_oversized_file(authed_client: AsyncClient):
    payload = b"a" * (settings.IMPORT_CSV_MAX_BYTES + 1)
    res = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("too-big.csv", io.BytesIO(payload), "text/csv")},
    )
    assert res.status_code == 413, res.text


@pytest.mark.asyncio
async def test_preview_import_rejects_too_many_rows(
    authed_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    # Keep the test fast by lowering the row cap.
    monkeypatch.setattr(settings, "IMPORT_CSV_MAX_ROWS", 5)

    lines = ["full_name,email"]
    for i in range(settings.IMPORT_CSV_MAX_ROWS + 1):
        lines.append(f"Name{i},test{i}@example.com")
    csv_data = ("\n".join(lines) + "\n").encode("utf-8")

    res = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("too-many-rows.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert res.status_code == 413, res.text
