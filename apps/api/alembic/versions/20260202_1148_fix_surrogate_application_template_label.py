"""Fix long label in surrogate application form template.

Revision ID: 20260202_1148
Revises: 20260202_2359
Create Date: 2026-02-02 11:48:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260202_1148"
down_revision: Union[str, Sequence[str], None] = "20260202_2359"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TEMPLATE_NAME = "Surrogate Application Form Template"
OLD_LABEL = (
    "Do you and your partner understand that you MUST agree to abstain "
    "from sexual activity while undergoing medical treatment and participating "
    "in this program? Any period(s) of abstinence will be directed by the physician."
)
NEW_LABEL = (
    "Do you and your partner agree to abstain from sexual activity during medical "
    "treatment as directed by the physician?"
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE platform_form_templates
            SET
                schema_json = CASE
                    WHEN schema_json IS NULL THEN NULL
                    ELSE replace(schema_json::text, :old_label, :new_label)::jsonb
                END,
                published_schema_json = CASE
                    WHEN published_schema_json IS NULL THEN NULL
                    ELSE replace(published_schema_json::text, :old_label, :new_label)::jsonb
                END,
                updated_at = now()
            WHERE
                name = :template_name
                OR published_name = :template_name
            """
        ),
        {
            "old_label": OLD_LABEL,
            "new_label": NEW_LABEL,
            "template_name": TEMPLATE_NAME,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE platform_form_templates
            SET
                schema_json = CASE
                    WHEN schema_json IS NULL THEN NULL
                    ELSE replace(schema_json::text, :new_label, :old_label)::jsonb
                END,
                published_schema_json = CASE
                    WHEN published_schema_json IS NULL THEN NULL
                    ELSE replace(published_schema_json::text, :new_label, :old_label)::jsonb
                END,
                updated_at = now()
            WHERE
                name = :template_name
                OR published_name = :template_name
            """
        ),
        {
            "old_label": OLD_LABEL,
            "new_label": NEW_LABEL,
            "template_name": TEMPLATE_NAME,
        },
    )
