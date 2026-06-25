"""seed pre-questionaire platform form template

Revision ID: 20260529_2355
Revises: 20260510_1553
Create Date: 2026-05-29 23:55:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260529_2355"
down_revision: str | Sequence[str] | None = "20260510_1553"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEMPLATE_NAME = "pre-questionaire"
TEMPLATE_DESCRIPTION = (
    "Answer a few quick questions so our team can review basic eligibility and follow up."
)
COMPLIANCE_NOTICE = (
    "By submitting this form, you consent to EWI collecting and using your information "
    "for surrogate intake screening and follow-up."
)


def _options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _schema() -> dict:
    yes_no = _options(["Yes", "No"])
    journey_options = [
        {"label": "0-3 months", "value": "months_0_3"},
        {"label": "3-6 months", "value": "months_3_6"},
        {"label": "Still deciding", "value": "still_deciding"},
    ]
    race_options = _options(
        [
            "White",
            "Black or African American",
            "Hispanic or Latino",
            "Asian",
            "Native American or Alaska Native",
            "Native Hawaiian or Pacific Islander",
            "Multiracial",
            "Other",
            "Prefer not to say",
        ]
    )

    return {
        "pages": [
            {
                "title": "Pre-questionnaire",
                "fields": [
                    {
                        "key": "email",
                        "label": "Email",
                        "type": "email",
                        "required": True,
                        "sensitivity": "contact",
                    },
                    {
                        "key": "full_name",
                        "label": "Full name",
                        "type": "text",
                        "required": True,
                        "sensitivity": "identity",
                    },
                    {
                        "key": "phone",
                        "label": "Phone number",
                        "type": "phone",
                        "required": True,
                        "sensitivity": "contact",
                    },
                    {
                        "key": "state",
                        "label": "State",
                        "type": "text",
                        "required": True,
                        "help_text": "Use the 2-letter state code, e.g. CA.",
                        "validation": {
                            "min_length": 2,
                            "max_length": 2,
                            "pattern": "^[A-Za-z]{2}$",
                        },
                        "sensitivity": "campaign_safe",
                    },
                    {
                        "key": "date_of_birth",
                        "label": "Date of birth",
                        "type": "date",
                        "required": True,
                        "sensitivity": "identity",
                    },
                    {
                        "key": "age_21_to_36",
                        "label": "Are you currently between the ages of 21 and 36?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                        "sensitivity": "operational",
                    },
                    {
                        "key": "us_citizen_or_pr",
                        "label": "Are you a citizen or permanent resident of the US?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                        "sensitivity": "operational",
                    },
                    {
                        "key": "journey_timing_preference",
                        "label": "When would you like to start your surrogacy journey?",
                        "type": "radio",
                        "required": True,
                        "options": journey_options,
                        "sensitivity": "operational",
                    },
                    {
                        "key": "race",
                        "label": "Please specify your race",
                        "type": "select",
                        "required": True,
                        "options": race_options,
                        "sensitivity": "operational",
                    },
                    {
                        "key": "has_raised_child",
                        "label": "Have you given birth to and raised at least one child?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                        "sensitivity": "sensitive_reproductive",
                    },
                    {
                        "key": "nicotine_or_tobacco_use",
                        "label": (
                            "Do you use nicotine/tobacco products of any kind "
                            "(cigarettes, cigars, vape devices, hookahs, marijuana, etc.)?"
                        ),
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                        "sensitivity": "sensitive_health",
                    },
                    {
                        "key": "height_ft",
                        "label": "Height",
                        "type": "height",
                        "required": True,
                        "sensitivity": "sensitive_health",
                    },
                    {
                        "key": "weight_lb",
                        "label": "Weight (lb)",
                        "type": "number",
                        "required": True,
                        "validation": {"min_value": 1, "max_value": 1000},
                        "sensitivity": "sensitive_health",
                    },
                    {
                        "key": "num_deliveries",
                        "label": "How many deliveries have you had?",
                        "type": "number",
                        "required": True,
                        "validation": {"min_value": 1, "max_value": 20},
                        "sensitivity": "sensitive_reproductive",
                    },
                    {
                        "key": "num_csections",
                        "label": "How many C-sections have you had?",
                        "type": "number",
                        "required": True,
                        "validation": {"min_value": 0, "max_value": 20},
                        "sensitivity": "sensitive_reproductive",
                    },
                ],
            }
        ],
        "public_eyebrow": "Pre-questionnaire",
        "public_title": "EWI pre-questionnaire",
        "public_subtitle": TEMPLATE_DESCRIPTION,
        "privacy_notice": COMPLIANCE_NOTICE,
    }


def _settings() -> dict:
    return {
        "purpose": "lead_capture",
        "max_file_size_bytes": 10 * 1024 * 1024,
        "max_file_count": 0,
        "allowed_mime_types": [],
        "mappings": [
            {"field_key": "email", "surrogate_field": "email"},
            {"field_key": "full_name", "surrogate_field": "full_name"},
            {"field_key": "phone", "surrogate_field": "phone"},
            {"field_key": "state", "surrogate_field": "state"},
            {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
            {"field_key": "age_21_to_36", "surrogate_field": "is_age_eligible"},
            {"field_key": "us_citizen_or_pr", "surrogate_field": "is_citizen_or_pr"},
            {
                "field_key": "journey_timing_preference",
                "surrogate_field": "journey_timing_preference",
            },
            {"field_key": "race", "surrogate_field": "race"},
            {"field_key": "has_raised_child", "surrogate_field": "has_child"},
            {"field_key": "height_ft", "surrogate_field": "height_ft"},
            {"field_key": "weight_lb", "surrogate_field": "weight_lb"},
            {"field_key": "num_deliveries", "surrogate_field": "num_deliveries"},
            {"field_key": "num_csections", "surrogate_field": "num_csections"},
        ],
    }


def _template_table() -> sa.Table:
    return sa.table(
        "platform_form_templates",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("schema_json", postgresql.JSONB),
        sa.column("settings_json", postgresql.JSONB),
        sa.column("published_name", sa.String),
        sa.column("published_description", sa.Text),
        sa.column("published_schema_json", postgresql.JSONB),
        sa.column("published_settings_json", postgresql.JSONB),
        sa.column("status", sa.String),
        sa.column("current_version", sa.Integer),
        sa.column("published_version", sa.Integer),
        sa.column("is_published_globally", sa.Boolean),
        sa.column("published_at", sa.TIMESTAMP(timezone=True)),
        sa.column("updated_at", sa.TIMESTAMP(timezone=True)),
    )


def upgrade() -> None:
    schema = _schema()
    settings = _settings()
    template_table = _template_table()
    conn = op.get_bind()

    conn.execute(
        sa.update(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
        .values(
            description=TEMPLATE_DESCRIPTION,
            schema_json=schema,
            settings_json=settings,
            published_name=TEMPLATE_NAME,
            published_description=TEMPLATE_DESCRIPTION,
            published_schema_json=schema,
            published_settings_json=settings,
            status="published",
            current_version=template_table.c.current_version + 1,
            published_version=template_table.c.published_version + 1,
            is_published_globally=True,
            published_at=sa.text("now()"),
            updated_at=sa.text("now()"),
        )
    )

    exists = conn.execute(
        sa.select(sa.literal(1))
        .select_from(template_table)
        .where(template_table.c.name == TEMPLATE_NAME)
    ).first()
    if not exists:
        conn.execute(
            sa.insert(template_table).values(
                name=TEMPLATE_NAME,
                description=TEMPLATE_DESCRIPTION,
                schema_json=schema,
                settings_json=settings,
                published_name=TEMPLATE_NAME,
                published_description=TEMPLATE_DESCRIPTION,
                published_schema_json=schema,
                published_settings_json=settings,
                status="published",
                current_version=1,
                published_version=1,
                is_published_globally=True,
                published_at=sa.text("now()"),
            )
        )


def downgrade() -> None:
    template_table = _template_table()
    conn = op.get_bind()
    conn.execute(
        sa.delete(template_table).where(
            sa.and_(
                template_table.c.name == TEMPLATE_NAME,
                template_table.c.description == TEMPLATE_DESCRIPTION,
                template_table.c.current_version == 1,
                template_table.c.published_version == 1,
            )
        )
    )
