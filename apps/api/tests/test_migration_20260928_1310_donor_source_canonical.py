"""Donor source upgrade stores the canonical lowercase source values."""

from uuid import uuid4

from sqlalchemy import text

from alembic import command
from tests.test_migration_20260829_donor_module import _alembic_config, _insert_donor_fixture

REVISION = "20260928_1310_donor_source_canonical"
PREVIOUS = "20260928_1300_workflow_fixed_trigger_subjects"


def _insert_donor(connection, fixture, *, source):
    donor_id = uuid4()
    connection.execute(
        text(
            """
            INSERT INTO donors (
                id, organization_id, donor_number, donor_type, full_name,
                email, email_hash, stage_id, is_archived, source
            ) VALUES (
                :id, :organization_id, :donor_number, 'egg', 'Source Donor',
                'encrypted-email', :email_hash, :stage_id, FALSE, :source
            )
            """
        ),
        {
            "id": donor_id,
            "organization_id": fixture["org_id"],
            "donor_number": f"D{uuid4().int % 900_000_000 + 100_000_000:09d}",
            "email_hash": uuid4().hex + uuid4().hex,
            "stage_id": fixture["stage_id"],
            "source": source,
        },
    )
    return donor_id


def test_upgrade_maps_donor_source_variants_to_canonical_values(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            fixture = _insert_donor_fixture(connection, label=f"source-{uuid4().hex[:8]}")
            cases = {
                "Meta": "meta",
                " META ": "meta",
                "meta": "meta",
                "Website": "website",
                "shared_intake": "website",
                "form_embed": "website",
                "manual_review_resolution": "website",
                "manual_retry_resolution": "website",
                "referral": "referral",
                "Spring Fair 2026": "other",
                "": "manual",
                None: "manual",
            }
            donors = {
                _insert_donor(connection, fixture, source=source): expected
                for source, expected in cases.items()
            }
            promoted = _insert_donor(connection, fixture, source="event_qr")
            connection.execute(
                text(
                    """
                    INSERT INTO intake_leads (
                        id, organization_id, source, lead_type, full_name, status,
                        promoted_donor_id
                    ) VALUES (
                        :id, :org_id, 'event_qr', 'egg_donor', 'Source Donor', 'promoted',
                        :donor_id
                    )
                    """
                ),
                {"id": uuid4(), "org_id": fixture["org_id"], "donor_id": promoted},
            )
            donors[promoted] = "website"

            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)

            rows = dict(
                connection.execute(
                    text("SELECT id, source FROM donors WHERE organization_id = :org_id"),
                    {"org_id": fixture["org_id"]},
                ).all()
            )
            assert {donor_id: rows[donor_id] for donor_id in donors} == donors
        finally:
            transaction.rollback()
