"""seed surrogate pre-screening questionnaire platform form template

Revision ID: 20260223_2358
Revises: 20260223_1300
Create Date: 2026-02-23 23:58:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260223_2358"
down_revision: str | Sequence[str] | None = "20260223_1300"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TEMPLATE_NAME = "Surrogate Pre-Screening Questionnaire"
TEMPLATE_DESCRIPTION = (
    "Quick pre-screening questionnaire for surrogate eligibility prior to full application."
)
COMPLIANCE_NOTICE = (
    "By submitting this questionnaire, you consent to the collection and use of your information "
    "for intake screening and eligibility review."
)


def _options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def _schema() -> dict:
    yes_no = _options(["Yes", "No"])
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
                "title": "Pre-Screening",
                "fields": [
                    {
                        "key": "age_21_to_36",
                        "label": "Are you currently between the ages of 21 and 36?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "has_raised_child",
                        "label": "Have you given birth to and raised at least one child?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "us_citizen_or_pr",
                        "label": "Are you a citizen or permanent resident of the US?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "surrogate_experience",
                        "label": "Have you ever been a surrogate before?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "email",
                        "label": "Email",
                        "type": "email",
                        "required": True,
                    },
                    {
                        "key": "phone",
                        "label": "Phone",
                        "type": "phone",
                        "required": True,
                    },
                    {
                        "key": "date_of_birth",
                        "label": "Date of Birth",
                        "type": "date",
                        "required": True,
                    },
                    {
                        "key": "height",
                        "label": "Height",
                        "type": "number",
                        "required": True,
                    },
                    {
                        "key": "weight",
                        "label": "Weight",
                        "type": "number",
                        "required": True,
                    },
                    {
                        "key": "race",
                        "label": "Race",
                        "type": "select",
                        "required": True,
                        "options": race_options,
                    },
                    {
                        "key": "city",
                        "label": "What city do you live in?",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "state",
                        "label": "What state do you live in?",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "deliveries_count",
                        "label": "How many deliveries have you had?",
                        "type": "number",
                        "required": True,
                    },
                    {
                        "key": "c_sections_more_than_two",
                        "label": "Have you had more than 2 C-sections?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "psychiatric_medication",
                        "label": (
                            "Are you currently taking any medication for depression, anxiety, "
                            "bipolar disorder, or any other psychiatric condition?"
                        ),
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "criminal_history_household",
                        "label": "Have you or your spouse/partner ever committed any crimes?",
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "nicotine_or_tobacco_use_household",
                        "label": (
                            "Do You or your Spouse/Partner use nicotine/tobacco products of any kind "
                            "(cigarettes, cigars, vape devices, hookahs, marijuana, etc.)?"
                        ),
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                    {
                        "key": "government_assistance",
                        "label": (
                            "Do you currently receive any forms of government assistance "
                            "(Cash Aid/TANF/Foodstamps/ Medicaid/Section 8/etc.)?"
                        ),
                        "type": "radio",
                        "required": True,
                        "options": yes_no,
                    },
                ],
            }
        ],
        "public_title": TEMPLATE_NAME,
        "privacy_notice": COMPLIANCE_NOTICE,
    }


def _settings() -> dict:
    return {
        "max_file_size_bytes": 10 * 1024 * 1024,
        "max_file_count": 5,
        "allowed_mime_types": ["image/*", "application/pdf"],
        "mappings": [
            {"field_key": "age_21_to_36", "surrogate_field": "is_age_eligible"},
            {"field_key": "has_raised_child", "surrogate_field": "has_child"},
            {"field_key": "us_citizen_or_pr", "surrogate_field": "is_citizen_or_pr"},
            {"field_key": "surrogate_experience", "surrogate_field": "has_surrogate_experience"},
            {"field_key": "full_name", "surrogate_field": "full_name"},
            {"field_key": "email", "surrogate_field": "email"},
            {"field_key": "phone", "surrogate_field": "phone"},
            {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
            {"field_key": "height", "surrogate_field": "height_ft"},
            {"field_key": "weight", "surrogate_field": "weight_lb"},
            {"field_key": "race", "surrogate_field": "race"},
            {"field_key": "state", "surrogate_field": "state"},
            {"field_key": "deliveries_count", "surrogate_field": "num_deliveries"},
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
