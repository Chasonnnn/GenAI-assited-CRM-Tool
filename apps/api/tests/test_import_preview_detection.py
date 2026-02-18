"""Contract tests for CSV import preview detection + suggestions."""

import io
import pytest
from httpx import AsyncClient

from app.core.config import settings


def make_delimited_content(
    rows: list[dict],
    delimiter: str = "\t",
    encoding: str = "utf-16",
) -> bytes:
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [delimiter.join(headers)]
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(delimiter.join(values))
    return "\n".join(lines).encode(encoding)


@pytest.mark.asyncio
async def test_preview_detects_utf16_tsv_and_suggestions(authed_client: AsyncClient):
    rows = [
        {
            "email": "test@example.com",
            "full_name": "Test User",
            "phone_number": "5551234567",
            "state": "TX",
            "date_of_birth": "07/19/1991",
            "are_you_currently_between_the_ages_of_21_and_36?": "yes",
            "do_you_use_nicotine/tobacco_products_of_any_kind_(cigarettes,_cigars,_vape_devices,_hookahs,_marijuana,_etc.)?": "no",
        }
    ]
    csv_data = make_delimited_content(rows, delimiter="\t", encoding="utf-16")

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("meta.tsv.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["detected_encoding"].startswith("utf-16")
    assert data["detected_delimiter"] == "\t"
    assert isinstance(data.get("column_suggestions"), list)

    age_suggestion = next(
        (
            s
            for s in data["column_suggestions"]
            if s.get("csv_column") == "are_you_currently_between_the_ages_of_21_and_36?"
        ),
        None,
    )
    assert age_suggestion is not None
    assert age_suggestion.get("suggested_field") == "is_age_eligible"

    smoke_suggestion = next(
        (
            s
            for s in data["column_suggestions"]
            if s.get("csv_column")
            == "do_you_use_nicotine/tobacco_products_of_any_kind_(cigarettes,_cigars,_vape_devices,_hookahs,_marijuana,_etc.)?"
        ),
        None,
    )
    assert smoke_suggestion is not None
    assert smoke_suggestion.get("suggested_field") == "is_non_smoker"
    assert smoke_suggestion.get("transformation") == "boolean_inverted"


@pytest.mark.asyncio
async def test_preview_returns_date_ambiguity_warnings(authed_client: AsyncClient):
    rows = [
        {
            "full_name": "Alpha",
            "email": "alpha@example.com",
            "date_of_birth": "01/02/2024",
        },
        {
            "full_name": "Beta",
            "email": "beta@example.com",
            "date_of_birth": "02/01/2024",
        },
    ]
    csv_data = make_delimited_content(rows, delimiter=",", encoding="utf-8")

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("ambiguous.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert "date_ambiguity_warnings" in data
    assert len(data["date_ambiguity_warnings"]) > 0


@pytest.mark.asyncio
async def test_preview_maps_created_time_variants(authed_client: AsyncClient):
    rows = [
        {
            "full_name": "Created Time User",
            "email": "created@example.com",
            "created time": "2025-01-01 08:30:00",
        }
    ]
    csv_data = make_delimited_content(rows, delimiter=",", encoding="utf-8")

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("created-time.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    created_suggestion = next(
        (s for s in data["column_suggestions"] if s.get("csv_column") == "created time"),
        None,
    )
    assert created_suggestion is not None
    assert created_suggestion.get("suggested_field") == "created_at"


@pytest.mark.asyncio
async def test_preview_maps_platform_values_to_meta_source(authed_client: AsyncClient):
    rows = [
        {
            "full_name": "Meta Lead",
            "email": "meta@example.com",
            "platform": "ig, fb",
        }
    ]
    csv_data = make_delimited_content(rows, delimiter=",", encoding="utf-8")

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("platform.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    platform_suggestion = next(
        (s for s in data["column_suggestions"] if s.get("csv_column") == "platform"),
        None,
    )
    assert platform_suggestion is not None
    assert platform_suggestion.get("suggested_field") == "source"
    assert platform_suggestion.get("transformation") == "source_meta_platform"


@pytest.mark.asyncio
async def test_preview_maps_heard_about_question_to_source(authed_client: AsyncClient):
    rows = [
        {
            "full_name": "Source Lead",
            "email": "source@example.com",
            "How did you hear about us?": "TikTok",
        }
    ]
    csv_data = make_delimited_content(rows, delimiter=",", encoding="utf-8")

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("heard-about.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    suggestion = next(
        (
            s
            for s in data["column_suggestions"]
            if s.get("csv_column") == "How did you hear about us?"
        ),
        None,
    )
    assert suggestion is not None
    assert suggestion.get("suggested_field") == "source"
    assert suggestion.get("transformation") == "source_channel_guess"


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


@pytest.mark.asyncio
async def test_preview_import_rejects_mime_extension_mismatch(
    authed_client: AsyncClient,
):
    csv_data = b"full_name,email\nTest,test@example.com\n"
    res = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "image/png")},
    )
    assert res.status_code == 400, res.text
    assert "content type" in res.text.lower()
