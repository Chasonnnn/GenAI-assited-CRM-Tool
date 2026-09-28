"""Store donor source with the canonical lowercase surrogate source values.

Meta Lead Ads donors were stored as ``Meta`` and hosted or embedded CRM form
donors as their routing path (``shared_intake``, ``form_embed``, review
resolutions). Those become ``meta`` and ``website``. Other unknown values become
``website`` when the donor was promoted from an intake lead and ``other``
otherwise. Donors without a source were created manually and become ``manual``,
the create default. Downgrade is a no-op: the original spellings are not kept.

Revision ID: 20260928_1310_donor_source_canonical
Revises: 20260928_1300_workflow_fixed_trigger_subjects
"""

import sqlalchemy as sa

from alembic import op

revision = "20260928_1310_donor_source_canonical"
down_revision = "20260928_1300_workflow_fixed_trigger_subjects"
branch_labels = None
depends_on = None

# Frozen copies of SurrogateSource values and app.schemas.donor website aliases,
# so later vocabulary edits cannot change this revision.
CANONICAL_SOURCES = (
    "manual",
    "meta",
    "tiktok",
    "google",
    "website",
    "referral",
    "import",
    "agency",
    "other",
)
WEBSITE_ALIASES = (
    "shared_intake",
    "form_embed",
    "website_intake",
    "website_embed",
    "manual_review_resolution",
    "manual_retry_resolution",
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '3s'")
    op.execute("SET LOCAL statement_timeout = '60s'")
    connection = op.get_bind()
    canonical = {"canonical": list(CANONICAL_SOURCES)}

    def execute(sql: str, params: dict | None = None) -> None:
        statement = sa.text(sql)
        for name in params or {}:
            statement = statement.bindparams(sa.bindparam(name, expanding=True))
        connection.execute(statement, params or {})

    execute("UPDATE donors SET source = 'manual' WHERE source IS NULL OR btrim(source) = ''")
    execute(
        """
        UPDATE donors SET source = lower(btrim(source))
        WHERE lower(btrim(source)) IN :canonical AND source <> lower(btrim(source))
        """,
        canonical,
    )
    execute(
        "UPDATE donors SET source = 'website' WHERE lower(btrim(source)) IN :aliases",
        {"aliases": list(WEBSITE_ALIASES)},
    )
    execute(
        """
        UPDATE donors SET source = 'website'
        WHERE source NOT IN :canonical
          AND EXISTS (
            SELECT 1 FROM intake_leads
            WHERE intake_leads.organization_id = donors.organization_id
              AND intake_leads.promoted_donor_id = donors.id
          )
        """,
        canonical,
    )
    execute("UPDATE donors SET source = 'other' WHERE source NOT IN :canonical", canonical)


def downgrade() -> None:
    pass
