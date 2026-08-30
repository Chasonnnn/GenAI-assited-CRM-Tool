from __future__ import annotations

import importlib.util
import uuid
from pathlib import Path

from sqlalchemy import text

from app.core.stage_definitions import get_default_stage_defs

MIGRATION_PATH = (
    Path(__file__).resolve().parents[1] / "app" / "db" / "migration_steps" / "donor_pipelines.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("migration_donor_pipelines", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_donor_pipelines_is_idempotent_and_subtype_specific(db, test_org):
    migration = _load_migration()
    connection = db.connection()

    migration._seed_default_donor_pipelines(connection)
    migration._seed_default_donor_pipelines(connection)

    pipelines = (
        connection.execute(
            text(
                """
            SELECT id, entity_type, feature_config
            FROM pipelines
            WHERE organization_id = :organization_id
              AND entity_type IN ('egg_donor', 'sperm_donor')
              AND is_default = TRUE
            ORDER BY entity_type
            """
            ),
            {"organization_id": test_org.id},
        )
        .mappings()
        .all()
    )
    assert [row["entity_type"] for row in pipelines] == ["egg_donor", "sperm_donor"]
    assert pipelines[0]["feature_config"]["analytics"]["qualification_stage_key"] == (
        "ready_to_match"
    )
    assert pipelines[1]["feature_config"]["analytics"]["qualification_stage_key"] == "available"

    stage_counts = dict(
        connection.execute(
            text(
                """
                SELECT p.entity_type, count(ps.id)
                FROM pipelines p
                JOIN pipeline_stages ps ON ps.pipeline_id = p.id
                WHERE p.organization_id = :organization_id
                  AND p.entity_type IN ('egg_donor', 'sperm_donor')
                GROUP BY p.entity_type
                """
            ),
            {"organization_id": test_org.id},
        ).all()
    )
    assert stage_counts == {"egg_donor": 13, "sperm_donor": 13}
    for entity_type, definition in migration.PIPELINES.items():
        migration_stages = [
            (stage_key, label, color, stage_type)
            for stage_key, label, color, stage_type in definition["stages"]
        ]
        runtime_stages = [
            (
                stage["stage_key"],
                stage["label"],
                stage["color"],
                stage["stage_type"],
            )
            for stage in get_default_stage_defs(entity_type)
        ]
        assert migration_stages == runtime_stages


def test_seed_donor_pipeline_downgrade_preserves_only_referenced_seeded_pipeline(db, test_org):
    migration = _load_migration()
    connection = db.connection()
    migration._seed_default_donor_pipelines(connection)

    egg_stage_id = connection.execute(
        text(
            """
            SELECT ps.id
            FROM pipeline_stages ps
            JOIN pipelines p ON p.id = ps.pipeline_id
            WHERE p.organization_id = :organization_id
              AND p.entity_type = 'egg_donor'
              AND ps.stage_key = 'new'
            """
        ),
        {"organization_id": test_org.id},
    ).scalar_one()
    donor_id = uuid.uuid4()
    connection.execute(
        text(
            """
            INSERT INTO donors (
                id, organization_id, donor_number, donor_type, full_name,
                email, email_hash, stage_id
            ) VALUES (
                :id, :organization_id, :donor_number, 'egg', 'Migration Donor',
                :email, :email_hash, :stage_id
            )
            """
        ),
        {
            "id": donor_id,
            "organization_id": test_org.id,
            "donor_number": "D99001",
            "email": "encrypted-test-value",
            "email_hash": uuid.uuid4().hex + uuid.uuid4().hex,
            "stage_id": egg_stage_id,
        },
    )

    migration._remove_seeded_donor_pipelines(connection)

    remaining_types = (
        connection.execute(
            text(
                """
            SELECT entity_type
            FROM pipelines
            WHERE organization_id = :organization_id
              AND entity_type IN ('egg_donor', 'sperm_donor')
            ORDER BY entity_type
            """
            ),
            {"organization_id": test_org.id},
        )
        .scalars()
        .all()
    )
    assert remaining_types == ["egg_donor"]
