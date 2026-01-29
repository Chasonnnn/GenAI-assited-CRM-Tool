"""Tests for CSV import auto-match enhancements (TDD)."""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient


def make_csv(rows: list[dict[str, str]]) -> bytes:
    if not rows:
        return b""
    headers = list(rows[0].keys())
    lines = [",".join(headers)]
    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))
    return "\n".join(lines).encode("utf-8")


def test_fuzzy_matches_email_typo():
    from app.services import import_detection_service as detection

    suggestions = detection.analyze_columns(
        ["emal"],
        [["test@example.com"]],
        allowed_fields=detection.AVAILABLE_IMPORT_FIELDS,
    )

    assert suggestions[0].suggested_field == "email"
    assert "similar" in suggestions[0].reason.lower()


def test_keyword_match_not_overridden_by_fuzzy():
    """Verify that exact/keyword matches take priority over fuzzy."""
    from app.services import import_detection_service as detection

    # "phone_num" matches via keyword pattern, not fuzzy
    suggestions = detection.analyze_columns(
        ["phone_num"],
        [["555-0101"]],
        allowed_fields=detection.AVAILABLE_IMPORT_FIELDS,
    )

    assert suggestions[0].suggested_field == "phone"
    # Should be keyword match (semantic), not fuzzy match (similar)
    assert "semantic" in suggestions[0].reason.lower() or "exact" in suggestions[0].reason.lower()
    assert "similar" not in suggestions[0].reason.lower()


@pytest.mark.asyncio
async def test_template_auto_apply_overrides_detection(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    from app.db.models import ImportTemplate

    template = ImportTemplate(
        organization_id=test_org.id,
        name="Auto Template",
        description="",
        is_default=False,
        encoding="auto",
        delimiter=",",
        has_header=True,
        column_mappings=[
            {
                "csv_column": "email",
                "surrogate_field": None,
                "transformation": None,
                "action": "ignore",
                "custom_field_key": None,
            },
            {
                "csv_column": "full_name",
                "surrogate_field": "full_name",
                "transformation": None,
                "action": "map",
                "custom_field_key": None,
            },
        ],
        transformations=None,
        unknown_column_behavior="metadata",
        created_by_user_id=test_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    csv_data = make_csv([{"email": "alpha@example.com", "full_name": "Alpha"}])

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text

    data = preview.json()
    assert data["auto_applied_template"]["id"] == str(template.id)
    assert data["template_unknown_column_behavior"] == "metadata"

    email_suggestion = next(
        item for item in data["column_suggestions"] if item["csv_column"].lower() == "email"
    )
    assert email_suggestion["suggested_field"] is None
    assert email_suggestion["default_action"] == "ignore"


@pytest.mark.asyncio
async def test_template_auto_apply_can_be_disabled(
    authed_client: AsyncClient,
    db,
    test_org,
    test_user,
):
    from app.db.models import ImportTemplate

    template = ImportTemplate(
        organization_id=test_org.id,
        name="Auto Template Off",
        description="",
        is_default=False,
        encoding="auto",
        delimiter=",",
        has_header=True,
        column_mappings=[
            {
                "csv_column": "email",
                "surrogate_field": None,
                "transformation": None,
                "action": "ignore",
                "custom_field_key": None,
            },
        ],
        transformations=None,
        unknown_column_behavior="metadata",
        created_by_user_id=test_user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    csv_data = make_csv([{"email": "alpha@example.com"}])

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced?apply_template=false",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text

    data = preview.json()
    assert data["auto_applied_template"] is None
    assert data["template_unknown_column_behavior"] is None

    email_suggestion = next(
        item for item in data["column_suggestions"] if item["csv_column"].lower() == "email"
    )
    assert email_suggestion["suggested_field"] == "email"


@pytest.mark.asyncio
async def test_ai_auto_triggered_for_unmatched_columns(
    authed_client: AsyncClient,
    monkeypatch,
    db,
    test_org,
):
    from app.services import import_ai_mapper_service
    from app.services.import_detection_service import ColumnSuggestion, ConfidenceLevel

    monkeypatch.setattr(import_ai_mapper_service, "is_ai_available", lambda *_: True)

    async def fake_ai_suggest_mappings(*args, **kwargs):
        if "unmatched_columns" in kwargs:
            unmatched = kwargs["unmatched_columns"]
        else:
            unmatched = args[2]
        suggestions = []
        for col in unmatched:
            if isinstance(col, ColumnSuggestion):
                name = col.csv_column
                samples = col.sample_values
            else:
                name = str(col)
                samples = []
            suggestions.append(
                ColumnSuggestion(
                    csv_column=name,
                    suggested_field="source",
                    confidence=0.9,
                    confidence_level=ConfidenceLevel.HIGH,
                    transformation=None,
                    sample_values=samples,
                    reason="AI suggestion",
                )
            )
        return suggestions

    monkeypatch.setattr(import_ai_mapper_service, "ai_suggest_mappings", fake_ai_suggest_mappings)

    csv_data = make_csv([{"Mystery Column": "foo"}])

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced?enable_ai=true",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text

    data = preview.json()
    assert data["ai_auto_triggered"] is True
    assert "Mystery Column" in data["ai_mapped_columns"]

    mystery = next(
        item for item in data["column_suggestions"] if item["csv_column"] == "Mystery Column"
    )
    assert mystery["suggested_field"] == "source"


@pytest.mark.asyncio
async def test_preview_import_ai_not_auto_triggered_by_default(
    authed_client: AsyncClient,
    monkeypatch,
    db,
    test_org,
):
    from app.services import import_ai_mapper_service

    called = {"ai": False}

    monkeypatch.setattr(import_ai_mapper_service, "is_ai_available", lambda *_: True)

    async def fake_ai_suggest_mappings(*_args, **_kwargs):
        called["ai"] = True
        return []

    monkeypatch.setattr(import_ai_mapper_service, "ai_suggest_mappings", fake_ai_suggest_mappings)

    csv_data = make_csv([{"Mystery Column": "foo"}])

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text

    data = preview.json()
    assert data["ai_auto_triggered"] is False
    assert data["ai_mapped_columns"] == []
    assert called["ai"] is False


@pytest.mark.asyncio
async def test_learning_applies_to_csv_imports(
    authed_client: AsyncClient,
):
    csv_data = make_csv(
        [
            {
                "Agency Name": "Agency One",
                "full_name": "Alpha",
                "email": "alpha@example.com",
            }
        ]
    )

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200, preview.text
    import_id = preview.json()["import_id"]

    submit = await authed_client.post(
        f"/surrogates/import/{import_id}/submit",
        json={
            "column_mappings": [
                {"csv_column": "Agency Name", "surrogate_field": "source", "action": "map"},
                {"csv_column": "full_name", "surrogate_field": "full_name", "action": "map"},
                {"csv_column": "email", "surrogate_field": "email", "action": "map"},
            ]
        },
    )
    assert submit.status_code == 200, submit.text

    # Approve the import to trigger correction learning
    approve = await authed_client.post(f"/surrogates/import/{import_id}/approve")
    assert approve.status_code == 200, approve.text

    # Cancel the approved import so duplicate-file guard doesn't block re-preview
    cancel = await authed_client.delete(f"/surrogates/import/{import_id}")
    assert cancel.status_code == 200, cancel.text

    preview_again = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("preview.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview_again.status_code == 200, preview_again.text

    agency_suggestion = next(
        item
        for item in preview_again.json()["column_suggestions"]
        if item["csv_column"] == "Agency Name"
    )
    assert agency_suggestion["suggested_field"] == "source"
    assert agency_suggestion["reason"].lower().startswith("learned")


@pytest.mark.asyncio
async def test_learning_applies_to_meta_form_mappings(
    authed_client: AsyncClient,
    db,
    test_org,
):
    from app.db.models import MetaForm, MetaFormVersion

    form = MetaForm(
        organization_id=test_org.id,
        page_id="page_1",
        form_external_id="form_1",
        form_name="Test Form",
    )
    db.add(form)
    db.flush()

    version = MetaFormVersion(
        form_id=form.id,
        version_number=1,
        field_schema=[
            {"key": "agency_name", "label": "Agency Name", "type": "text"},
            {"key": "full_name", "label": "Full Name", "type": "text"},
            {"key": "email", "label": "Email", "type": "text"},
        ],
        schema_hash="x" * 64,
    )
    db.add(version)
    db.flush()

    form.current_version_id = version.id
    db.commit()

    preview = await authed_client.get(f"/integrations/meta/forms/{form.id}/mapping")
    assert preview.status_code == 200, preview.text

    update = await authed_client.put(
        f"/integrations/meta/forms/{form.id}/mapping",
        json={
            "column_mappings": [
                {
                    "csv_column": "agency_name",
                    "surrogate_field": "source",
                    "action": "map",
                },
                {
                    "csv_column": "full_name",
                    "surrogate_field": "full_name",
                    "action": "map",
                },
                {
                    "csv_column": "email",
                    "surrogate_field": "email",
                    "action": "map",
                },
            ],
            "unknown_column_behavior": "metadata",
        },
    )
    assert update.status_code == 200, update.text

    preview_again = await authed_client.get(f"/integrations/meta/forms/{form.id}/mapping")
    assert preview_again.status_code == 200, preview_again.text

    agency_suggestion = next(
        item
        for item in preview_again.json()["column_suggestions"]
        if item["csv_column"] == "agency_name"
    )
    assert agency_suggestion["suggested_field"] == "source"
    assert agency_suggestion["reason"].lower().startswith("learned")
