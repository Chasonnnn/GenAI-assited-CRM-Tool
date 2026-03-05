"""add form purpose and org-level default surrogate application form

Revision ID: 20260223_1300
Revises: 20260222_1800
Create Date: 2026-02-23 13:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260223_1300"
down_revision: str | Sequence[str] | None = "20260222_1800"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_table(table_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(table_name: str, index_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_foreign_key(table_name: str, foreign_key_name: str) -> bool:
    if not _has_table(table_name):
        return False
    inspector = sa.inspect(op.get_bind())
    return any(
        foreign_key.get("name") == foreign_key_name
        for foreign_key in inspector.get_foreign_keys(table_name)
    )


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _has_column(table_name, column.name):
        op.add_column(table_name, column)


def _create_foreign_key_if_missing(
    constraint_name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if not _has_foreign_key(source_table, constraint_name):
        op.create_foreign_key(
            constraint_name,
            source_table,
            referent_table,
            local_cols,
            remote_cols,
            ondelete=ondelete,
        )


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if not _has_index(table_name, index_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    _add_column_if_missing(
        "forms",
        sa.Column(
            "purpose",
            sa.String(length=40),
            nullable=False,
            server_default=sa.text("'surrogate_application'"),
        ),
    )
    op.execute(sa.text("UPDATE forms SET purpose = 'surrogate_application' WHERE purpose IS NULL"))
    _create_index_if_missing(
        "idx_forms_org_purpose_status",
        "forms",
        ["organization_id", "purpose", "status"],
    )

    _add_column_if_missing(
        "organizations",
        sa.Column(
            "default_surrogate_application_form_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    _create_foreign_key_if_missing(
        "fk_organizations_default_surrogate_application_form",
        "organizations",
        "forms",
        ["default_surrogate_application_form_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _create_index_if_missing(
        "idx_organizations_default_surrogate_application_form",
        "organizations",
        ["default_surrogate_application_form_id"],
    )

    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT
                    f.organization_id,
                    f.id AS form_id,
                    ROW_NUMBER() OVER (
                        PARTITION BY f.organization_id
                        ORDER BY f.updated_at DESC, f.created_at DESC
                    ) AS rn
                FROM forms f
                WHERE f.status = 'published'
                  AND f.purpose = 'surrogate_application'
            )
            UPDATE organizations o
            SET default_surrogate_application_form_id = ranked.form_id
            FROM ranked
            WHERE o.id = ranked.organization_id
              AND ranked.rn = 1
              AND o.default_surrogate_application_form_id IS NULL
            """
        )
    )


def downgrade() -> None:
    if _has_index("organizations", "idx_organizations_default_surrogate_application_form"):
        op.drop_index(
            "idx_organizations_default_surrogate_application_form", table_name="organizations"
        )
    if _has_foreign_key("organizations", "fk_organizations_default_surrogate_application_form"):
        op.drop_constraint(
            "fk_organizations_default_surrogate_application_form",
            "organizations",
            type_="foreignkey",
        )
    if _has_column("organizations", "default_surrogate_application_form_id"):
        op.drop_column("organizations", "default_surrogate_application_form_id")

    if _has_index("forms", "idx_forms_org_purpose_status"):
        op.drop_index("idx_forms_org_purpose_status", table_name="forms")
    if _has_column("forms", "purpose"):
        op.drop_column("forms", "purpose")
