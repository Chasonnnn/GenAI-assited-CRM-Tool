"""fix_workflow_pause_fk

Revision ID: 20260129_0051
Revises: faed99d040d9
Create Date: 2026-01-29 00:51:38.438726

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260129_0051"
down_revision: Union[str, Sequence[str], None] = "faed99d040d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_fk_for_column(table: str, column: str) -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        op.drop_constraint(f"{table}_{column}_fkey", table, type_="foreignkey")
        return

    result = bind.execute(
        sa.text(
            """
            SELECT DISTINCT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_attribute att ON att.attrelid = rel.oid
            WHERE con.contype = 'f'
              AND rel.relname = :table
              AND att.attname = :column
              AND att.attnum = ANY (con.conkey)
            """
        ),
        {"table": table, "column": column},
    )
    for row in result:
        op.drop_constraint(row.conname, table, type_="foreignkey")


def upgrade() -> None:
    """Upgrade schema."""
    _drop_fk_for_column("workflow_executions", "paused_task_id")
    op.create_foreign_key(
        "fk_workflow_executions_paused_task_id",
        "workflow_executions",
        "tasks",
        ["paused_task_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "fk_workflow_executions_paused_task_id",
        "workflow_executions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "workflow_executions_paused_task_id_fkey",
        "workflow_executions",
        "tasks",
        ["paused_task_id"],
        ["id"],
        ondelete="SET NULL",
    )
