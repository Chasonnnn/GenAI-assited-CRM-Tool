"""Update attachment quarantine semantics for pending scans.

Revision ID: 20260131_1800
Revises: 20260131_1600
Create Date: 2026-01-31 18:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260131_1800"
down_revision: Union[str, Sequence[str], None] = "20260131_1600"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "attachments",
        "quarantined",
        existing_type=sa.Boolean(),
        server_default=sa.text("FALSE"),
        nullable=False,
    )
    op.alter_column(
        "form_submission_files",
        "quarantined",
        existing_type=sa.Boolean(),
        server_default=sa.text("FALSE"),
        nullable=False,
    )
    op.execute(
        """
        UPDATE attachments
        SET quarantined = CASE WHEN scan_status IN ('infected', 'error') THEN TRUE ELSE FALSE END
        """
    )
    op.execute(
        """
        UPDATE form_submission_files
        SET quarantined = CASE WHEN scan_status IN ('infected', 'error') THEN TRUE ELSE FALSE END
        """
    )


def downgrade() -> None:
    op.alter_column(
        "attachments",
        "quarantined",
        existing_type=sa.Boolean(),
        server_default=sa.text("TRUE"),
        nullable=False,
    )
    op.alter_column(
        "form_submission_files",
        "quarantined",
        existing_type=sa.Boolean(),
        server_default=sa.text("TRUE"),
        nullable=False,
    )
    op.execute(
        """
        UPDATE attachments
        SET quarantined = CASE WHEN scan_status = 'clean' THEN FALSE ELSE TRUE END
        """
    )
    op.execute(
        """
        UPDATE form_submission_files
        SET quarantined = CASE WHEN scan_status = 'clean' THEN FALSE ELSE TRUE END
        """
    )
