from __future__ import annotations

import importlib.util
from pathlib import Path


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260529_2355_seed_pre_questionaire_form_template.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("migration_20260529_2355", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pre_questionaire_template_schema_matches_requested_short_form():
    from app.schemas.forms import FormSchema

    migration = _load_migration_module()

    assert migration.TEMPLATE_NAME == "pre-questionaire"

    schema = migration._schema()
    FormSchema.model_validate(schema)
    fields = schema["pages"][0]["fields"]

    assert schema["pages"][0]["title"] == "Pre-questionnaire"
    assert schema["public_eyebrow"] == "Pre-questionnaire"
    assert schema["public_title"] == "EWI pre-questionnaire"
    assert schema["public_subtitle"] == migration.TEMPLATE_DESCRIPTION
    assert (
        migration.TEMPLATE_DESCRIPTION
        == "Answer a few quick questions so our team can review basic eligibility and follow up."
    )
    assert [field["key"] for field in fields] == [
        "email",
        "full_name",
        "phone",
        "state",
        "date_of_birth",
        "age_21_to_36",
        "us_citizen_or_pr",
        "journey_timing_preference",
        "race",
        "has_raised_child",
        "nicotine_or_tobacco_use",
        "height_ft",
        "weight_lb",
        "num_deliveries",
        "num_csections",
    ]

    by_key = {field["key"]: field for field in fields}
    yes_no = [{"label": "Yes", "value": "Yes"}, {"label": "No", "value": "No"}]

    assert by_key["age_21_to_36"]["label"] == (
        "Are you currently between the ages of 21 and 36?"
    )
    assert by_key["age_21_to_36"]["options"] == yes_no
    assert by_key["journey_timing_preference"]["options"] == [
        {"label": "0-3 months", "value": "months_0_3"},
        {"label": "3-6 months", "value": "months_3_6"},
        {"label": "Still deciding", "value": "still_deciding"},
    ]
    assert by_key["nicotine_or_tobacco_use"]["label"] == (
        "Do you use nicotine/tobacco products of any kind "
        "(cigarettes, cigars, vape devices, hookahs, marijuana, etc.)?"
    )
    assert by_key["nicotine_or_tobacco_use"]["sensitivity"] == "sensitive_health"
    assert by_key["height_ft"]["type"] == "number"
    assert by_key["num_deliveries"]["sensitivity"] == "sensitive_reproductive"
    assert by_key["num_csections"]["label"] == "How many C-sections have you had?"
    assert all(field.get("sensitivity") for field in fields)


def test_pre_questionaire_template_mappings_sync_supported_surrogate_fields_only():
    from app.services.form_submission_service import SURROGATE_FIELD_TYPES

    migration = _load_migration_module()

    mappings = migration._settings()["mappings"]

    assert migration._settings()["purpose"] == "lead_capture"
    assert mappings == [
        {"field_key": "email", "surrogate_field": "email"},
        {"field_key": "full_name", "surrogate_field": "full_name"},
        {"field_key": "phone", "surrogate_field": "phone"},
        {"field_key": "state", "surrogate_field": "state"},
        {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
        {"field_key": "age_21_to_36", "surrogate_field": "is_age_eligible"},
        {"field_key": "us_citizen_or_pr", "surrogate_field": "is_citizen_or_pr"},
        {"field_key": "journey_timing_preference", "surrogate_field": "journey_timing_preference"},
        {"field_key": "race", "surrogate_field": "race"},
        {"field_key": "has_raised_child", "surrogate_field": "has_child"},
        {"field_key": "height_ft", "surrogate_field": "height_ft"},
        {"field_key": "weight_lb", "surrogate_field": "weight_lb"},
        {"field_key": "num_deliveries", "surrogate_field": "num_deliveries"},
        {"field_key": "num_csections", "surrogate_field": "num_csections"},
    ]
    assert all(mapping["surrogate_field"] in SURROGATE_FIELD_TYPES for mapping in mappings)
    assert all(mapping["field_key"] != "nicotine_or_tobacco_use" for mapping in mappings)
