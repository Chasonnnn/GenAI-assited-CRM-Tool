"""Pipeline edits preserve the V2 shared surrogate ownership boundary."""

import threading
import time
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.db.enums import Role
from app.db.models import (
    Organization,
    OrganizationPermissionPolicy,
    PipelineStage,
    Queue,
    RecordCollaborator,
    Surrogate,
)
from app.services import permission_policy_service, pipeline_service, record_scope_service
from tests.test_default_pipeline_concurrency import committed_org_id as committed_org_id
from tests.test_permission_handoff_publication import member, session
from tests.test_record_scopes_v2 import _record, _stage_history


def _custom_stage(db, org_id, actor_id, *, entity_type="surrogate"):
    pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id, entity_type=entity_type)
    approved = pipeline_service.get_stage_by_key(db, pipeline.id, "approved")
    custom = pipeline_service.create_stage(
        db,
        pipeline.id,
        "pool_review",
        "Pool review",
        "#475569",
        "intake",
        order=approved.order,
        user_id=actor_id,
    )
    return pipeline, custom, approved


def _draft(db, pipeline, *, custom, approved, remap=False):
    stages = [stage for stage in pipeline_service.get_stages(db, pipeline.id) if stage != custom]
    if not remap:
        stages.insert(stages.index(approved) + 1, custom)
    return [
        {
            "id": str(stage.id),
            "stage_key": stage.stage_key,
            "slug": stage.slug,
            "label": stage.label,
            "color": stage.color,
            "order": index + 1,
            "category": stage.stage_type,
            "is_active": stage.is_active,
            "semantics": stage.semantics,
        }
        for index, stage in enumerate(stages)
    ]


@pytest.mark.parametrize(
    "operation", ["update", "reorder", "delete", "publish", "remap", "rollback"]
)
def test_pipeline_phase_changes_share_records_and_retain_current_intake(
    db, test_org, test_user, operation
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    actor = session(test_org.id, intake, Role.INTAKE_SPECIALIST)
    pipeline, custom, approved = _custom_stage(db, test_org.id, test_user.id)
    target_version = None
    if operation == "rollback":
        pipeline_service.update_stage(db, custom, order=approved.order + 1, user_id=test_user.id)
        target_version = pipeline.current_version
        pipeline_service.update_stage(db, custom, order=approved.order - 1, user_id=test_user.id)
    record = _record(db, actor, "surrogate", key=custom.stage_key)
    paused = _record(db, actor, "surrogate", key="on_hold", paused=custom.stage_key, suffix=2)
    db.commit()
    assert record_scope_service.record_phase(db, test_org.id, "surrogate", record) == "pre_approval"

    if operation == "update":
        pipeline_service.update_stage(db, custom, order=approved.order + 1, user_id=test_user.id)
    elif operation == "reorder":
        stage_ids = [
            stage.id for stage in pipeline_service.get_stages(db, pipeline.id) if stage != custom
        ]
        stage_ids.insert(stage_ids.index(approved.id) + 1, custom.id)
        pipeline_service.reorder_stages(db, pipeline.id, stage_ids, test_user.id)
    elif operation == "delete":
        pipeline_service.delete_stage(db, custom, approved.id, test_user.id)
    elif operation == "rollback":
        updated, error = pipeline_service.rollback_pipeline(
            db, pipeline, target_version, test_user.id
        )
        assert updated is not None and error is None
    else:
        remap = operation == "remap"
        pipeline_service.apply_pipeline_draft(
            db,
            pipeline,
            name=pipeline.name,
            stages=_draft(db, pipeline, custom=custom, approved=approved, remap=remap),
            feature_config=pipeline.feature_config,
            remaps=[{"removed_stage_key": custom.stage_key, "target_stage_key": "approved"}]
            if remap
            else [],
            user_id=test_user.id,
        )

    pool = (
        db.query(Queue).filter_by(organization_id=test_org.id, name="Surrogate Pool").one_or_none()
    )
    assert pool is not None
    for changed in (record, paused):
        db.refresh(changed)
        assert (
            record_scope_service.record_phase(db, test_org.id, "surrogate", changed)
            == "post_approval"
        )
        assert (changed.owner_type, changed.owner_id, changed.assigned_at) == (
            "queue",
            pool.id,
            None,
        )
        assert record_scope_service.can_access_record(db, actor, "surrogate", changed)
    assert {
        row.surrogate_id for row in db.query(RecordCollaborator).filter_by(user_id=intake.id)
    } == {record.id, paused.id}


def test_pipeline_phase_change_includes_terminal_history_and_excludes_other_records(
    db, test_org, test_user
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    actor = session(test_org.id, intake, Role.INTAKE_SPECIALIST)
    pipeline, custom, approved = _custom_stage(db, test_org.id, test_user.id)
    terminal = _record(db, actor, "surrogate", key="lost")
    _stage_history(db, terminal, "surrogate", custom.id, terminal.stage_id)
    donor = _record(db, actor, "donor", key="approved")
    early = _record(db, actor, "surrogate", suffix=2)
    other_pipeline = pipeline_service.create_pipeline(
        db, test_org.id, test_user.id, "Other pipeline"
    )
    other_pipeline_record = _record(db, actor, "surrogate", suffix=3)
    other_pipeline_record.stage_id = pipeline_service.get_stage_by_key(
        db, other_pipeline.id, "approved"
    ).id
    other_org = Organization(id=uuid4(), name="Other", slug=f"pipeline-pool-{uuid4()}")
    db.add(other_org)
    db.flush()
    foreign = _record(
        db, SimpleNamespace(org_id=other_org.id, user_id=test_user.id), "surrogate", key="approved"
    )
    db.commit()

    pipeline_service.update_stage(db, custom, order=approved.order + 1, user_id=test_user.id)

    db.refresh(terminal)
    assert terminal.owner_type == "queue"
    assert record_scope_service.can_access_record(db, actor, "surrogate", terminal)
    for unchanged in (donor, early, foreign, other_pipeline_record):
        db.refresh(unchanged)
        assert unchanged.owner_type == "user"
    assert {row.surrogate_id for row in db.query(RecordCollaborator)} == {terminal.id}


@pytest.mark.parametrize("policy_version, entity_type", [(1, "surrogate"), (2, "egg_donor")])
def test_pipeline_phase_edits_preserve_legacy_and_donor_ownership(
    db, test_org, test_user, policy_version, entity_type
):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=policy_version))
    pipeline, custom, approved = _custom_stage(
        db, test_org.id, test_user.id, entity_type=entity_type
    )
    actor = session(test_org.id, test_user, Role.DEVELOPER)
    record = _record(
        db, actor, "donor" if entity_type == "egg_donor" else "surrogate", key=custom.stage_key
    )
    db.commit()

    pipeline_service.update_stage(db, custom, order=approved.order + 1, user_id=test_user.id)

    db.refresh(record)
    assert (record.owner_type, record.owner_id) == ("user", test_user.id)
    assert db.query(RecordCollaborator).count() == 0


def test_pipeline_handoff_audit_failure_rolls_back_configuration_and_access(
    db, test_org, test_user, monkeypatch
):
    from app.services import audit_service

    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake = member(db, test_org.id, Role.INTAKE_SPECIALIST)
    actor = session(test_org.id, intake, Role.INTAKE_SPECIALIST)
    pipeline, custom, approved = _custom_stage(db, test_org.id, test_user.id)
    record = _record(db, actor, "surrogate", key=custom.stage_key)
    db.commit()
    original_order, original_version = custom.order, pipeline.current_version
    real_audit = audit_service.log_event

    def fail_assignment_audit(*args, **kwargs):
        if kwargs.get("target_type") == "surrogate":
            raise RuntimeError("Pool audit unavailable")
        return real_audit(*args, **kwargs)

    monkeypatch.setattr(audit_service, "log_event", fail_assignment_audit)
    with pytest.raises(RuntimeError, match="Pool audit unavailable"), db.begin_nested():
        pipeline_service.update_stage(db, custom, order=approved.order + 1, user_id=test_user.id)

    assert custom.order == original_order
    assert pipeline.current_version == original_version
    assert (record.owner_type, record.owner_id) == ("user", intake.id)
    assert not db.query(RecordCollaborator).filter_by(surrogate_id=record.id).count()
    assert not db.query(Queue).filter_by(organization_id=test_org.id, name="Surrogate Pool").count()


def test_pipeline_edit_waits_for_activation_and_uses_activated_ownership_policy(
    db_engine, committed_org_id
):
    with Session(bind=db_engine) as seed:
        intake = member(seed, committed_org_id, Role.INTAKE_SPECIALIST)
        intake_id = intake.id
        actor = session(committed_org_id, intake, Role.INTAKE_SPECIALIST)
        pipeline, custom, approved = _custom_stage(seed, committed_org_id, None)
        record = _record(seed, actor, "surrogate", key=custom.stage_key)
        stage_id, record_id, new_order = custom.id, record.id, approved.order + 1
        seed.commit()
    probe_engine = create_engine(db_engine.url, poolclass=NullPool)
    outcome = {}

    def update_after_activation():
        try:
            with Session(bind=db_engine) as writer:
                stage = writer.get(PipelineStage, stage_id)
                pipeline_service.update_stage(writer, stage, order=new_order)
        except Exception as exc:
            outcome["error"] = exc

    racer = None
    try:
        with Session(bind=db_engine) as activation:
            permission_policy_service.lock_configuration(activation, committed_org_id)
            activation.add(
                OrganizationPermissionPolicy(organization_id=committed_org_id, version=2)
            )
            activation.flush()
            activation_pid = activation.execute(text("SELECT pg_backend_pid()")).scalar_one()
            racer = threading.Thread(target=update_after_activation)
            racer.start()
            deadline = time.monotonic() + 10
            blocked = False
            while time.monotonic() < deadline and not blocked:
                with probe_engine.connect() as probe:
                    blocked = probe.execute(
                        text(
                            "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE :pid = ANY(pg_blocking_pids(pid)))"
                        ),
                        {"pid": activation_pid},
                    ).scalar_one()
                if not blocked:
                    time.sleep(0.01)
            assert blocked, "pipeline write did not wait for permission activation"
            activation.commit()
        racer.join(timeout=10)
        assert not racer.is_alive()
        assert "error" not in outcome, outcome.get("error")
        with Session(bind=db_engine) as observed:
            record = observed.get(Surrogate, record_id)
            assert record.owner_type == "queue"
            assert (
                observed.query(RecordCollaborator)
                .filter_by(surrogate_id=record_id, user_id=intake_id)
                .count()
                == 1
            )
    finally:
        if racer:
            racer.join(timeout=10)
        probe_engine.dispose()
        with db_engine.begin() as cleanup:
            # The shared fixture removes the organization; delete only this test's
            # immutable audit rows first, using the disposable-test cleanup pattern.
            cleanup.execute(text("SET LOCAL session_replication_role = replica"))
            cleanup.execute(
                text("DELETE FROM audit_logs WHERE organization_id = :id"),
                {"id": committed_org_id},
            )
            cleanup.execute(text("SET LOCAL session_replication_role = origin"))
            cleanup.execute(text("DELETE FROM users WHERE id = :id"), {"id": intake_id})
