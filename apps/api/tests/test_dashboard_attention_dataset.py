"""Attention rows, totals, and drilldowns retain the same record scope."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.encryption import hash_email
from app.db.models import Donor, DonorStatusHistory, Organization, Surrogate, Task
from app.schemas.record_scope import RecordScopeAdditionCreate
from app.services import (
    dashboard_service,
    donor_service,
    intelligent_suggestions_service,
    pipeline_service,
    record_scope_service,
)
from tests.test_record_scopes_v2 import _member
from tests.test_record_scopes_v2 import context as context


def _stale_record(db, session, kind, *, suffix):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, session.org_id, entity_type="surrogate" if kind == "surrogate" else f"{kind}_donor"
    )
    stage = min(pipeline.stages, key=lambda stage: stage.order)
    email = f"attention-{uuid4()}@example.test"
    stale_at = datetime.now(UTC) - timedelta(days=100)
    fields = dict(
        id=uuid4(),
        organization_id=session.org_id,
        full_name="Synthetic applicant",
        email=email,
        email_hash=hash_email(email),
        owner_type="user",
        owner_id=session.user_id,
        stage_id=stage.id,
        created_at=stale_at,
        updated_at=stale_at,
    )
    record = (
        Surrogate(**fields, surrogate_number=f"S{10000 + suffix}", status_label=stage.label)
        if kind == "surrogate"
        else Donor(**fields, donor_number=f"D{10000 + suffix}", donor_type=kind)
    )
    db.add(record)
    db.flush()
    return record


def _attention(db, session, *, limit=1, pipeline_id=None):
    return dashboard_service.get_attention_items(
        db,
        session.org_id,
        user_id=session.user_id,
        user_role=session.role,
        can_view_donors=True,
        limit=limit,
        pipeline_id=pipeline_id,
    )


def _drilldown(db, session, kind):
    if kind == "surrogate":
        return intelligent_suggestions_service._attention_stuck_ids(
            db,
            org_id=session.org_id,
            user_id=session.user_id,
            user_role=session.role,
            now_utc=datetime.now(UTC),
        )
    records, total = donor_service.list_donors(
        db,
        session.org_id,
        donor_type=kind,
        dynamic_filter="attention_stuck",
        session=session,
    )
    assert len(records) == total
    return {record.id for record in records}


@pytest.mark.parametrize("kind", ["egg", "sperm"])
def test_deleted_stage_history_does_not_hide_stuck_donor_drilldown(db, context, kind):
    record = _stale_record(db, context.intake, kind, suffix=1)
    now = datetime.now(UTC)
    db.add(
        DonorStatusHistory(
            donor_id=record.id,
            organization_id=context.org.id,
            old_stage_id=record.stage_id,
            new_stage_id=None,
            new_status="removed_stage",
            new_label_snapshot="Removed stage",
            effective_at=now,
            recorded_at=now,
        )
    )
    db.flush()
    assert _attention(db, context.intake)["stuck_donor_count"] == 1
    assert _drilldown(db, context.intake, kind) == {record.id}


@pytest.mark.parametrize("kind", ["surrogate", "egg", "sperm"])
def test_attention_totals_and_drilldowns_follow_scope_addition_and_revocation(db, context, kind):
    visible = [_stale_record(db, context.intake, kind, suffix=i) for i in (1, 2)]
    hidden = _stale_record(db, context.manager, kind, suffix=3)
    foreign_org = Organization(id=uuid4(), name="Other agency", slug=f"other-{uuid4().hex}")
    db.add(foreign_org)
    db.flush()
    outsider, _ = _member(db, foreign_org.id, "intake_specialist")
    _stale_record(db, outsider, kind, suffix=1)
    rows_key, count_key = (
        ("stuck_surrogates", "stuck_count")
        if kind == "surrogate"
        else ("stuck_donors", "stuck_donor_count")
    )

    def assert_visible(expected):
        result = _attention(db, context.intake)
        assert result[count_key] == len(expected)
        assert len(result[rows_key]) == 1
        assert {row["id"] for row in result[rows_key]} <= {str(record.id) for record in expected}
        assert _drilldown(db, context.intake, kind) == {record.id for record in expected}
        if kind == "surrogate":
            assert result["unreached_count"] == len(expected)
            assert len(result["unreached_leads"]) == 1
        else:
            assert result["stuck_donor_counts"][kind] == len(expected)

    assert_visible(visible)
    addition = record_scope_service.add_scope_addition(
        db,
        context.admin,
        context.intake.user_id,
        RecordScopeAdditionCreate(
            module="surrogates" if kind == "surrogate" else "donors",
            assignment="all",
            phase="pre_approval",
        ),
    )
    assert_visible([*visible, hidden])
    record_scope_service.remove_scope_addition(
        db, context.admin, context.intake.user_id, addition.id
    )
    assert_visible(visible)


def test_overdue_totals_use_same_linked_scope_and_pipeline_as_limited_rows(db, context):
    visible = [_stale_record(db, context.intake, "surrogate", suffix=i) for i in (1, 2)]
    hidden = _stale_record(db, context.manager, "surrogate", suffix=3)
    foreign_org = Organization(id=uuid4(), name="Other agency", slug=f"other-{uuid4().hex}")
    db.add(foreign_org)
    db.flush()
    outsider, _ = _member(db, foreign_org.id, "intake_specialist")
    foreign = _stale_record(db, outsider, "surrogate", suffix=1)
    visible_task_ids = set()
    for record in [*visible, hidden, foreign]:
        task = Task(
            id=uuid4(),
            organization_id=record.organization_id,
            surrogate_id=record.id,
            title="Synthetic overdue task",
            created_by_user_id=record.owner_id,
            owner_type="user",
            owner_id=record.owner_id,
            due_date=datetime.now(UTC).date() - timedelta(days=1),
        )
        db.add(task)
        if record in visible:
            visible_task_ids.add(str(task.id))
    db.flush()
    pipeline = pipeline_service.get_or_create_default_pipeline(db, context.org.id)
    for pipeline_id in (None, pipeline.id):
        result = _attention(db, context.intake, pipeline_id=pipeline_id)
        assert result["overdue_count"] == len(visible_task_ids)
        assert len(result["overdue_tasks"]) == 1
        assert {row["id"] for row in result["overdue_tasks"]} <= visible_task_ids
