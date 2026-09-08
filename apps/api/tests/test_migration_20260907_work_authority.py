"""Migration keeps live donor stages while installing an explicit approval boundary."""

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import text

from app.db.migration_steps.donor_pipelines import _seed_default_donor_pipelines


def test_donor_approval_seed_is_idempotent_and_preserves_existing_stage_ids(db, test_org):
    path = Path(__file__).resolve().parents[1] / "alembic/versions/20260907_2220_work_authority.py"
    spec = importlib.util.spec_from_file_location("work_authority_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connection = db.connection()
    _seed_default_donor_pipelines(connection)
    before = (
        connection.execute(
            text("""SELECT s.id, s.stage_key, s."order", p.entity_type
        FROM pipeline_stages s JOIN pipelines p ON p.id=s.pipeline_id
        WHERE p.organization_id=:org AND p.entity_type IN ('egg_donor','sperm_donor')"""),
            {"org": test_org.id},
        )
        .mappings()
        .all()
    )
    connection.execute(
        text(
            "UPDATE pipeline_stages SET slug='approved' WHERE stage_key='application_submitted' AND pipeline_id IN (SELECT id FROM pipelines WHERE organization_id=:org)"
        ),
        {"org": test_org.id},
    )
    module.seed_donor_approval_gates(connection)
    module.seed_donor_approval_gates(connection)
    after = (
        connection.execute(
            text("""SELECT s.id, s.stage_key, s."order", p.entity_type
        FROM pipeline_stages s JOIN pipelines p ON p.id=s.pipeline_id
        WHERE p.organization_id=:org AND p.entity_type IN ('egg_donor','sperm_donor')"""),
            {"org": test_org.id},
        )
        .mappings()
        .all()
    )
    assert len(after) == len(before) + 2
    assert {row["id"] for row in before} <= {row["id"] for row in after}
    for entity_type, first_post in (("egg_donor", "ready_to_match"), ("sperm_donor", "available")):
        stages = {row["stage_key"]: row for row in after if row["entity_type"] == entity_type}
        assert stages["approved"]["order"] < stages[first_post]["order"]
        assert stages["approved"]["order"] > stages["application_submitted"]["order"]


@pytest.mark.parametrize(
    "filename",
    [
        "20260907_2200_permission_policy.py",
        "20260907_2210_record_scope.py",
        "20260907_2220_work_authority.py",
    ],
)
def test_active_policy_blocks_schema_downgrade_before_data_loss(
    db, test_org, monkeypatch, filename
):
    from sqlalchemy import inspect

    from app.db.models import OrganizationPermissionPolicy

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    db.flush()
    path = Path(__file__).resolve().parents[1] / "alembic/versions" / filename
    spec = importlib.util.spec_from_file_location("guarded_permission_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    connection = db.connection()
    before = set(inspect(connection).get_table_names())
    monkeypatch.setattr(module.op, "get_bind", lambda: connection)
    with pytest.raises(RuntimeError, match="reviewed rollback"):
        module.downgrade()
    assert set(inspect(connection).get_table_names()) == before
    assert db.get(OrganizationPermissionPolicy, test_org.id).version == 2
