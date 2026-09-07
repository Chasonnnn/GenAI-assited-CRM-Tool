"""Preserve stage/permission semantics while bounding database round trips."""

from contextlib import contextmanager
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import event

from app.core.permissions import ROLE_DEFAULTS
from app.db.models import Organization, Pipeline, PipelineStage, RolePermission
from app.services import campaign_service, permission_service, pipeline_service


@contextmanager
def _selects(db):
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().lower().startswith("select"):
            statements.append(statement)

    bind = db.get_bind()
    event.listen(bind, "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(bind, "before_cursor_execute", capture)


def _pipeline(db, org_id, entity_type="surrogate"):
    pipeline = Pipeline(organization_id=org_id, entity_type=entity_type)
    db.add(pipeline)
    db.flush()
    return pipeline


def _stage(db, pipeline, key, slug=None, active=True):
    stage = PipelineStage(
        pipeline_id=pipeline.id,
        stage_key=key,
        slug=slug or key,
        label=key,
        stage_type="intake",
        color="#123456",
        order=0,
        is_active=active,
    )
    db.add(stage)
    db.flush()
    return stage


def test_bulk_stage_resolution_preserves_precedence_aliases_order_and_scope(db, test_org):
    pipeline = _pipeline(db, test_org.id)
    canonical = _stage(db, pipeline, "contacted", "renamed-contact")
    collision = _stage(db, pipeline, "custom", "contacted")
    alias = _stage(db, pipeline, "pre_qualified")
    inactive = _stage(db, pipeline, "inactive", active=False)
    uuid_slug = str(uuid4())
    fallback = _stage(db, pipeline, "uuid_fallback", uuid_slug)
    other = _pipeline(db, test_org.id, "egg_donor")
    forbidden = _stage(db, other, "foreign")
    refs = [
        "CONTACTED",
        "custom",
        "qualified",
        str(canonical.id),
        "renamed-contact",
        "inactive",
        "missing",
        str(forbidden.id),
        uuid_slug,
        "custom",
    ]
    expected = [canonical.id, collision.id, alias.id, inactive.id, fallback.id]
    with _selects(db) as statements:
        actual = pipeline_service.get_stage_ids_by_keys_or_slugs(
            db, test_org.id, refs, pipeline_id=pipeline.id
        )
    assert actual == expected
    assert len(statements) == 1
    assert pipeline_service.resolve_stage(db, pipeline.id, "contacted").id == canonical.id
    assert pipeline_service.resolve_stage(db, pipeline.id, None) is None
    assert pipeline_service.resolve_stage(db, pipeline.id, " ") is None
    assert pipeline_service.resolve_stage(db, pipeline.id, forbidden.id) is None
    assert pipeline_service.resolve_stages_bulk(
        db, test_org.id, pipeline.id, [UUID(uuid_slug), uuid_slug, None, " "]
    ) == [None, fallback, None, None]


@pytest.mark.parametrize(
    "recipient_type,entity_type", [("case", "surrogate"), ("egg_donor", "egg_donor")]
)
def test_campaign_filter_queries_are_bounded_and_preserve_order(
    db, test_org, recipient_type, entity_type
):
    pipeline = _pipeline(db, test_org.id, entity_type)
    stages = [_stage(db, pipeline, f"stage_{index}") for index in range(12)]
    requested = list(reversed(stages))
    with _selects(db) as statements:
        result = campaign_service.normalize_filter_criteria(
            db,
            test_org.id,
            recipient_type,
            {
                "stage_ids": [str(stage.id) for stage in requested] + [str(requested[0].id)],
                "stage_keys": [stage.stage_key for stage in stages],
                "stage_slugs": [stage.slug for stage in stages],
            },
        )
    assert result["stage_ids"] == [str(stage.id) for stage in requested]
    assert result["stage_keys"] == [stage.stage_key for stage in requested]
    assert "stage_slugs" not in result
    assert len(statements) <= 3


def test_donor_filters_reject_inactive_wrong_subtype_and_other_tenant(db, test_org):
    egg = _pipeline(db, test_org.id, "egg_donor")
    inactive = _stage(db, egg, "inactive", active=False)
    sperm = _pipeline(db, test_org.id, "sperm_donor")
    wrong_type = _stage(db, sperm, "new")
    other_org = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    other = _pipeline(db, other_org.id, "egg_donor")
    foreign = _stage(db, other, "new")
    assert (
        pipeline_service.get_stage_ids_by_keys_or_slugs(
            db, test_org.id, ["new", str(foreign.id)], pipeline_id=other.id
        )
        == []
    )
    for stage_id in [inactive.id, wrong_type.id, foreign.id, uuid4()]:
        with pytest.raises(ValueError, match="Stage filter not found"):
            campaign_service.normalize_filter_criteria(
                db, test_org.id, "egg_donor", {"stage_ids": [str(stage_id)]}
            )
    with pytest.raises(ValueError, match="Stage filter not found"):
        campaign_service.normalize_filter_criteria(
            db, test_org.id, "egg_donor", {"stage_keys": ["missing"]}
        )
    # Existing reference semantics retain an inactive ID, but omit its key.
    result = campaign_service.normalize_filter_criteria(
        db, test_org.id, "egg_donor", {"stage_keys": ["inactive"]}
    )
    assert result["stage_ids"] == [str(inactive.id)]
    assert result["stage_keys"] == []


def test_campaign_filters_keep_invalid_uuid_validation_and_ignore_missing_case_ids(db, test_org):
    pipeline = _pipeline(db, test_org.id)
    active = _stage(db, pipeline, "active")
    inactive = _stage(db, pipeline, "inactive", active=False)
    with pytest.raises(ValidationError):
        campaign_service.normalize_filter_criteria(
            db, test_org.id, "case", {"stage_ids": ["not-a-uuid"]}
        )
    result = campaign_service.normalize_filter_criteria(
        db,
        test_org.id,
        "case",
        {"stage_ids": [str(uuid4()), str(inactive.id), str(active.id)]},
    )
    assert result["stage_ids"] == [str(active.id)]
    assert result["stage_keys"] == ["active"]


def test_case_campaign_explicit_stage_ids_are_tenant_scoped(db, test_org):
    pipeline = _pipeline(db, test_org.id)
    local = _stage(db, pipeline, "local")
    alternate = Pipeline(organization_id=test_org.id, entity_type="surrogate", is_default=False)
    db.add(alternate)
    db.flush()
    alternate_stage = _stage(db, alternate, "alternate")
    other_org = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other_org)
    db.flush()
    foreign_pipeline = _pipeline(db, other_org.id)
    foreign = _stage(db, foreign_pipeline, "foreign")

    result = campaign_service.normalize_filter_criteria(
        db,
        test_org.id,
        "case",
        {"stage_ids": [str(foreign.id), str(alternate_stage.id), str(local.id)]},
    )

    assert result["stage_ids"] == [str(alternate_stage.id), str(local.id)]
    assert result["stage_keys"] == ["alternate", "local"]


def test_permission_seed_is_bounded_idempotent_and_preserves_denials(db, test_org):
    role, permissions = next((r, p) for r, p in ROLE_DEFAULTS.items() if r != "developer")
    permission = next(iter(permissions))
    denied = RolePermission(
        organization_id=test_org.id, role=role, permission=permission, is_granted=False
    )
    other_org = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add_all([denied, other_org])
    db.flush()
    other = RolePermission(
        organization_id=other_org.id, role=role, permission=permission, is_granted=False
    )
    db.add(other)
    db.flush()
    expected = sum(len(p) for r, p in ROLE_DEFAULTS.items() if r != "developer") - 1
    with _selects(db) as statements:
        assert permission_service.seed_role_defaults(db, test_org.id) == expected
    assert len(statements) == 1
    db.flush()
    with _selects(db) as statements:
        assert permission_service.seed_role_defaults(db, test_org.id) == 0
    assert len(statements) == 1
    db.flush()
    db.refresh(denied)
    db.refresh(other)
    assert denied.is_granted is False
    assert other.is_granted is False
    assert db.query(RolePermission).filter_by(organization_id=other_org.id).count() == 1
    assert (
        db.query(RolePermission).filter_by(organization_id=test_org.id, role="developer").count()
        == 0
    )
