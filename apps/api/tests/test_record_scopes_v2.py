"""Shared v2 scope, list/detail parity, review, and tenant boundaries."""

from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import aliased

from app.core.encryption import hash_email
from app.db.enums import Role
from app.db.models import Donor, IntendedParent, Membership, Organization, Surrogate, User
from app.db.models.permission_policy import OrganizationPermissionPolicy
from app.db.models.record_access import RecordCollaborator, UserRecordScopeAddition
from app.schemas.record_scope import (
    HandoffMigrationReviewRequest,
    RecordScopeAdditionCreate,
    RecordScopeRule,
)
from app.services import pipeline_service
from app.services import record_scope_service as scopes
from app.services.record_access_service import get_record_with_access


def _member(db, org_id, role):
    user = User(
        id=uuid4(), email=f"scope-{uuid4()}@example.test", display_name="Staff", is_active=True
    )
    db.add(user)
    db.flush()
    member = Membership(
        id=uuid4(), user_id=user.id, organization_id=org_id, role=role, is_active=True
    )
    db.add(member)
    db.flush()
    return SimpleNamespace(org_id=org_id, user_id=user.id, role=Role(role)), member


@pytest.fixture
def context(db, test_org):
    db.add(OrganizationPermissionPolicy(organization_id=test_org.id, version=2))
    intake, member = _member(db, test_org.id, "intake_specialist")
    manager, _ = _member(db, test_org.id, "case_manager")
    admin, _ = _member(db, test_org.id, "admin")
    return SimpleNamespace(org=test_org, intake=intake, member=member, manager=manager, admin=admin)


def _record(db, session, kind, *, key=None, owner_id=None, paused=None, archived=False, suffix=1):
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, session.org_id, entity_type="egg_donor" if kind == "donor" else kind
    )
    stages = {stage.stage_key: stage for stage in pipeline.stages if stage.is_active}
    stage = stages[key] if key else min(stages.values(), key=lambda value: value.order)
    email = f"scope-record-{uuid4()}@example.test"
    fields = dict(
        id=uuid4(),
        organization_id=session.org_id,
        full_name="Applicant",
        email=email,
        email_hash=hash_email(email),
        owner_type="user",
        owner_id=owner_id or session.user_id,
        stage_id=stage.id,
        is_archived=archived,
    )
    if kind == "surrogate":
        record = Surrogate(
            **fields,
            surrogate_number=f"S{10000 + suffix}",
            status_label=stage.label,
            paused_from_stage_id=stages[paused].id if paused else None,
        )
    elif kind == "donor":
        record = Donor(
            **fields,
            donor_number=f"D{10000 + suffix}",
            donor_type="egg",
            paused_from_stage_id=stages[paused].id if paused else None,
        )
    else:
        record = IntendedParent(
            **fields, intended_parent_number=f"I{10000 + suffix}", status=stage.stage_key
        )
    db.add(record)
    db.flush()
    return record


def _assert_parity(db, session, kind, records, expected, **kwargs):
    model = scopes.RECORDS[kind][0]
    actual = {
        row.id
        for row in db.query(model)
        .filter(scopes.build_visibility_filter(db, session, kind, **kwargs))
        .all()
    }
    assert actual == {record.id for record in expected}
    for record in records:
        assert scopes.can_access_record(db, session, kind, record, **kwargs) is (record in expected)
        explanation = scopes.explain_record_access(db, session, kind, record, **kwargs)
        assert explanation.allowed is (record in expected)
        assert bool(explanation.sources) is (record in expected)


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_assignment_and_phase_are_conjoined_and_approved_starts_post(db, context, kind):
    mine = _record(db, context.intake, kind, suffix=1)
    other = _record(db, context.manager, kind, suffix=2)
    approved_mine = _record(db, context.intake, kind, key="approved", suffix=3)
    approved_other = _record(db, context.manager, kind, key="approved", suffix=4)
    records = [mine, other, approved_mine, approved_other]
    _assert_parity(db, context.intake, kind, records, [mine])
    _assert_parity(db, context.manager, kind, records, [approved_mine, approved_other])
    alias = aliased(scopes.RECORDS[kind][0])
    assert {
        row.id
        for row in db.query(alias).filter(
            scopes.build_visibility_filter(db, context.intake, kind, model=alias)
        )
    } == {mine.id}


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_handoff_retention_is_idempotent_and_revocation_keeps_other_grants(db, context, kind):
    record = _record(db, context.intake, kind, key="approved")
    first = scopes.retain_intake_owner_at_handoff(
        db, context.org.id, kind, record, context.intake.user_id
    )
    again = scopes.retain_intake_owner_at_handoff(
        db, context.org.id, kind, record, context.intake.user_id
    )
    assert first.id == again.id
    record.owner_id = context.manager.user_id
    db.flush()
    _assert_parity(db, context.intake, kind, [record], [record], personal_only=True)
    assert scopes.explain_record_access(db, context.intake, kind, record).sources == [
        "intake_collaborator"
    ]
    addition = scopes.add_scope_addition(
        db,
        context.admin,
        context.intake.user_id,
        RecordScopeAdditionCreate(
            module=scopes.RECORDS[kind][1], assignment="all", phase="post_approval"
        ),
    )
    scopes.remove_collaborator(db, context.manager, kind, record.id, context.intake.user_id)
    _assert_parity(db, context.intake, kind, [record], [record])
    _assert_parity(db, context.intake, kind, [record], [], personal_only=True)
    scopes.remove_scope_addition(db, context.admin, context.intake.user_id, addition.id)
    _assert_parity(db, context.intake, kind, [record], [])


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_paused_stage_uses_prior_phase_and_archive_policy_is_shared(db, context, kind):
    pre_key = "new_unread" if kind == "surrogate" else "new"
    paused_pre = _record(db, context.intake, kind, key="on_hold", paused=pre_key, suffix=1)
    paused_post = _record(db, context.manager, kind, key="on_hold", paused="approved", suffix=2)
    archived = _record(db, context.manager, kind, key="approved", archived=True, suffix=3)
    records = [paused_pre, paused_post, archived]
    _assert_parity(db, context.intake, kind, records, [paused_pre])
    _assert_parity(db, context.manager, kind, records, [paused_post])
    _assert_parity(db, context.manager, kind, records, [paused_post, archived], allow_archived=True)
    _assert_parity(db, context.admin, kind, records, records)


def test_stage_constraints_and_tenant_boundaries(db, context):
    record = _record(db, context.manager, "surrogate", key="approved")
    later = _record(db, context.manager, "surrogate", key="ready_to_match", suffix=2)
    scopes.save_role_scope(
        db,
        context.admin,
        "case_manager",
        "surrogates",
        RecordScopeRule(assignment="assigned", phase="post_approval", stage_ids=[record.stage_id]),
    )
    _assert_parity(db, context.manager, "surrogate", [record, later], [record])
    other_org = Organization(id=uuid4(), name="Other", slug=f"scope-{uuid4()}")
    db.add(other_org)
    db.flush()
    foreign_staff, _ = _member(db, other_org.id, "intake_specialist")
    foreign = _record(db, foreign_staff, "surrogate")
    assert not scopes.can_access_record(db, context.admin, "surrogate", foreign)
    with pytest.raises(ValueError, match="this organization's"):
        scopes.save_role_scope(
            db,
            context.admin,
            "case_manager",
            "surrogates",
            RecordScopeRule(assignment="all", stage_ids=[foreign.stage_id]),
        )
    with pytest.raises(LookupError):
        scopes.grant_collaborator(db, context.admin, "surrogate", record.id, foreign_staff.user_id)
    with pytest.raises(HTTPException) as error:
        scopes.grant_collaborator(
            db, context.admin, "surrogate", foreign.id, context.intake.user_id
        )
    assert error.value.status_code == 404


def test_collaboration_does_not_grant_ip_access_and_departure_ends_access(db, context):
    record = _record(db, context.manager, "surrogate", key="approved")
    ip = _record(db, context.manager, "intended_parent")
    scopes.grant_collaborator(db, context.admin, "surrogate", record.id, context.intake.user_id)
    assert scopes.can_access_record(db, context.intake, "surrogate", record)
    assert not scopes.can_access_record(db, context.intake, "intended_parent", ip)
    context.member.is_active = False
    db.flush()
    assert not scopes.can_access_record(db, context.intake, "surrogate", record)


def test_operations_scope_is_readonly_through_action_permissions(db, context):
    operations, _ = _member(db, context.org.id, "operations")
    record = _record(db, context.intake, "surrogate")
    assert get_record_with_access(db, operations, "surrogate", record.id).id == record.id
    with pytest.raises(HTTPException) as error:
        get_record_with_access(db, operations, "surrogate", record.id, action="edit")
    assert error.value.status_code == 403


def test_role_review_only_removes_selected_grant_sources(db, context):
    record = _record(db, context.manager, "surrogate", key="approved")
    scopes.grant_collaborator(db, context.admin, "surrogate", record.id, context.intake.user_id)
    scopes.add_scope_addition(
        db,
        context.admin,
        context.intake.user_id,
        RecordScopeAdditionCreate(module="surrogates", assignment="all"),
    )
    scopes.apply_member_access_review(
        db,
        context.org.id,
        context.intake.user_id,
        retain_additions=False,
        retain_collaborators=True,
    )
    assert db.query(UserRecordScopeAddition).filter_by(user_id=context.intake.user_id).count() == 0
    assert db.query(RecordCollaborator).filter_by(user_id=context.intake.user_id).count() == 1
    scopes.apply_member_access_review(
        db,
        context.org.id,
        context.intake.user_id,
        retain_additions=True,
        retain_collaborators=False,
    )
    assert db.query(RecordCollaborator).filter_by(user_id=context.intake.user_id).count() == 0


def test_activation_snapshot_requires_per_record_handoff_review(db, context):
    record = _record(db, context.manager, "surrogate", key="approved")
    snapshot = scopes.get_policy_scope_snapshot(db, context.org.id)
    assert not snapshot["ready"]
    candidate = snapshot["unresolved_handoffs"][0]
    with pytest.raises(ValueError, match="evidence"):
        scopes.resolve_handoff_migration(
            db,
            context.admin,
            "surrogate",
            record.id,
            HandoffMigrationReviewRequest(
                decision="retain_verified_owner",
                intake_user_id=context.intake.user_id,
                expected_fingerprint=candidate["fingerprint"],
            ),
        )
    scopes.resolve_handoff_migration(
        db,
        context.admin,
        "surrogate",
        record.id,
        HandoffMigrationReviewRequest(
            decision="retain_verified_owner",
            intake_user_id=context.intake.user_id,
            evidence_reference="Approval history reviewed",
            expected_fingerprint=candidate["fingerprint"],
        ),
    )
    assert scopes.get_policy_scope_snapshot(db, context.org.id)["ready"]
    record.owner_id = context.intake.user_id
    db.flush()
    assert not scopes.get_policy_scope_snapshot(db, context.org.id)["ready"]


@pytest.mark.asyncio
async def test_scope_settings_require_admin_and_csrf(db, test_user, authed_client):
    response = await authed_client.put(
        "/record-scopes/roles/case_manager/surrogates",
        json={"assignment": "assigned", "phase": "post_approval"},
    )
    assert response.status_code == 200, response.text
    response = await authed_client.post(
        f"/record-scopes/members/{uuid4()}/additions",
        json={"module": "surrogates", "assignment": "all"},
    )
    assert response.status_code == 404
    from app.core.csrf import CSRF_HEADER

    csrf = authed_client.headers.pop(CSRF_HEADER)
    response = await authed_client.put(
        "/record-scopes/roles/case_manager/surrogates", json={"assignment": "all"}
    )
    assert response.status_code == 403
    authed_client.headers[CSRF_HEADER] = csrf
    db.query(Membership).filter_by(user_id=test_user.id).one().role = "case_manager"
    db.flush()
    response = await authed_client.put(
        "/record-scopes/roles/intake_specialist/surrogates", json={"assignment": "all"}
    )
    assert response.status_code == 403


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
def test_terminal_phase_comes_from_history_not_display_order(db, context, kind):
    from datetime import UTC, datetime

    from app.db.models import DonorStatusHistory, SurrogateStatusHistory

    record = _record(db, context.intake, kind, key="disqualified")
    assert not scopes.can_access_record(db, context.manager, kind, record)
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db, context.org.id, entity_type="egg_donor" if kind == "donor" else kind
    )
    pre = next(
        stage
        for stage in pipeline.stages
        if stage.stage_key == ("new_unread" if kind == "surrogate" else "new")
    )
    fields = dict(
        id=uuid4(),
        organization_id=context.org.id,
        effective_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC),
    )
    if kind == "surrogate":
        history = SurrogateStatusHistory(
            **fields, surrogate_id=record.id, from_stage_id=pre.id, to_stage_id=record.stage_id
        )
    else:
        history = DonorStatusHistory(
            **fields,
            donor_id=record.id,
            old_stage_id=pre.id,
            new_stage_id=record.stage_id,
            new_status="disqualified",
            new_label_snapshot="Disqualified",
        )
    db.add(history)
    db.flush()
    _assert_parity(db, context.intake, kind, [record], [record])
    _assert_parity(db, context.manager, kind, [record], [])


@pytest.mark.parametrize(
    "phase,can_intake,can_manager", [("pre_approval", True, False), ("post_approval", False, True)]
)
def test_unknown_terminal_phase_needs_record_evidence_and_resolution(
    db, context, phase, can_intake, can_manager
):
    record = _record(db, context.intake, "surrogate", key="disqualified")
    snapshot = scopes.get_policy_scope_snapshot(db, context.org.id)
    candidate = snapshot["unresolved_handoffs"][0]
    assert candidate["phase_requires_review"]
    assert not snapshot["ready"]
    with pytest.raises(ValueError, match="evidence"):
        scopes.resolve_handoff_migration(
            db,
            context.admin,
            "surrogate",
            record.id,
            HandoffMigrationReviewRequest(
                decision="no_verified_owner",
                expected_fingerprint=candidate["fingerprint"],
                resolved_phase=phase,
            ),
        )
    scopes.resolve_handoff_migration(
        db,
        context.admin,
        "surrogate",
        record.id,
        HandoffMigrationReviewRequest(
            decision="no_verified_owner",
            expected_fingerprint=candidate["fingerprint"],
            resolved_phase=phase,
            evidence_reference="Reviewed historical application record",
        ),
    )
    assert scopes.get_policy_scope_snapshot(db, context.org.id)["ready"]
    assert scopes.can_access_record(db, context.intake, "surrogate", record) is can_intake
    assert scopes.can_access_record(db, context.manager, "surrogate", record) is can_manager


@pytest.mark.parametrize("decision", ["remove", "replace_with_scope_addition"])
def test_legacy_pool_grants_need_explicit_current_snapshot_resolution(db, context, decision):
    from app.db.models import IntakePoolAccessGrant
    from app.schemas.record_scope import LegacyPoolResolutionRequest

    grantee, _ = _member(db, context.org.id, "intake_specialist")
    record = _record(db, context.intake, "surrogate")
    grant = IntakePoolAccessGrant(
        organization_id=context.org.id,
        source_user_id=context.intake.user_id,
        grantee_user_id=grantee.user_id,
    )
    db.add(grant)
    db.flush()
    snapshot = scopes.get_policy_scope_snapshot(db, context.org.id)
    assert not snapshot["ready"]
    row = snapshot["legacy_pool_grants"][0]
    assert row["current_record_ids"] == [str(record.id)]
    scopes.resolve_legacy_pool_grant(
        db,
        context.admin,
        grant.id,
        LegacyPoolResolutionRequest(
            expected_fingerprint=row["fingerprint"],
            decision=decision,
            replacement=RecordScopeAdditionCreate(
                module="surrogates", assignment="all", phase="pre_approval"
            )
            if decision == "replace_with_scope_addition"
            else None,
        ),
    )
    assert scopes.get_policy_scope_snapshot(db, context.org.id)["ready"]
    assert db.query(IntakePoolAccessGrant).filter_by(organization_id=context.org.id).count() == 0
    assert scopes.can_access_record(db, grantee, "surrogate", record) is (
        decision == "replace_with_scope_addition"
    )


def test_scope_mutations_recheck_actor_after_permission_removal(db, context):
    db.query(Membership).filter_by(user_id=context.admin.user_id).one().role = "case_manager"
    db.flush()
    assert context.admin.role == Role.ADMIN
    with pytest.raises(PermissionError):
        scopes.save_role_scope(
            db, context.admin, "intake_specialist", "surrogates", RecordScopeRule(assignment="all")
        )
    record = _record(db, context.manager, "surrogate", key="approved")
    db.query(Membership).filter_by(user_id=context.manager.user_id).one().role = "intake_specialist"
    db.flush()
    with pytest.raises(PermissionError):
        scopes.grant_collaborator(
            db, context.manager, "surrogate", record.id, context.intake.user_id
        )


def test_role_scope_can_participate_in_callers_atomic_transaction(db, context, monkeypatch):
    commit = []
    monkeypatch.setattr(db, "commit", lambda: commit.append(True))
    scopes.save_role_scope(
        db,
        context.admin,
        "case_manager",
        "surrogates",
        RecordScopeRule(assignment="assigned", phase="post_approval"),
        commit=False,
    )
    assert not commit
    assert (
        scopes.get_role_scope(db, context.org.id, "case_manager", "surrogates").assignment
        == "assigned"
    )


def test_migration_scope_counts_compare_legacy_without_changing_policy(db, context):
    record = _record(db, context.intake, "surrogate", key="approved")
    policy = db.get(OrganizationPermissionPolicy, context.org.id)
    policy.version = 1
    db.flush()
    snapshot = scopes.get_policy_scope_snapshot(db, context.org.id)
    row = next(
        row
        for row in snapshot["member_record_scope_differences"]
        if row["user_id"] == str(context.intake.user_id) and row["module"] == "surrogates"
    )
    assert row["scope_only"]
    assert row["current_count"] == 1
    assert row["proposed_count"] == 0
    assert row["lost_count"] == 1
    assert row["lost_record_id_samples"] == [str(record.id)]
    assert policy.version == 1
    record.owner_id = context.manager.user_id
    db.flush()
    updated = scopes.get_policy_scope_snapshot(db, context.org.id)
    assert snapshot["record_state_digest"] != updated["record_state_digest"]


def test_consumer_lists_filter_before_pagination_and_counts(db, context, monkeypatch):
    from datetime import date, timedelta

    from app.db.models import Task
    from app.services import dashboard_service, donor_service, ip_service, task_service

    mine = _record(db, context.intake, "donor", suffix=1)
    other = _record(db, context.manager, "donor", suffix=2)
    own_ip = _record(db, context.intake, "intended_parent", suffix=1)
    _record(db, context.manager, "intended_parent", suffix=2)
    rows, count = donor_service.list_donors(db, context.org.id, session=context.intake, per_page=1)
    assert count == 1 and [row.id for row in rows] == [mine.id]
    rows, count = ip_service.list_intended_parents(
        db, context.org.id, session=context.intake, per_page=1
    )
    assert count == 1 and [row.id for row in rows] == [own_ip.id]
    assert ip_service.get_ip_stats(db, context.org.id, session=context.intake)["total"] == 1
    tasks = []
    for record in (mine, other):
        task = Task(
            organization_id=context.org.id,
            donor_id=record.id,
            title="Review",
            owner_type="user",
            owner_id=context.intake.user_id,
            created_by_user_id=context.intake.user_id,
            task_type="other",
            due_date=date.today() - timedelta(days=2),
        )
        db.add(task)
        tasks.append(task)
    db.flush()
    monkeypatch.setattr(
        task_service, "_pull_google_tasks_for_user_best_effort", lambda *a: None, raising=False
    )
    rows, count = task_service.list_tasks(
        db,
        context.org.id,
        user_role=context.intake.role,
        user_id=context.intake.user_id,
        can_view_donors=True,
        per_page=1,
    )
    assert count == 1 and [row.id for row in rows] == [tasks[0].id]
    assert (
        task_service.count_overdue_tasks(db, context.org.id, date.today(), session=context.intake)
        == 1
    )
    upcoming, _ = dashboard_service.get_upcoming_items(
        db,
        context.org.id,
        context.intake.user_id,
        7,
        True,
        can_view_donors=True,
        session=context.intake,
    )
    assert [row["id"] for row in upcoming] == [str(tasks[0].id)]
    attention = dashboard_service.get_attention_items(
        db, context.org.id, context.intake.user_id, context.intake.role, can_view_donors=True
    )
    assert attention["overdue_count"] == 1


def test_unified_search_scopes_records_notes_and_files_before_limit(db, context):
    from app.db.models import Attachment, EntityNote
    from app.services import permission_service, search_service

    mine = _record(db, context.intake, "donor", suffix=1)
    hidden = _record(db, context.manager, "donor", suffix=2)
    retained = _record(db, context.manager, "donor", key="approved", suffix=3)
    scopes.grant_collaborator(db, context.admin, "donor", retained.id, context.intake.user_id)
    expected = set()
    for record in (mine, hidden, retained):
        record.full_name = "Searchscope Applicant"
        note = EntityNote(
            organization_id=context.org.id,
            entity_type="donor",
            entity_id=record.id,
            author_id=context.intake.user_id,
            content="Searchscope detail",
        )
        attachment = Attachment(
            organization_id=context.org.id,
            donor_id=record.id,
            uploaded_by_user_id=context.intake.user_id,
            filename="Searchscope report.pdf",
            storage_key=f"test/{record.id}",
            content_type="application/pdf",
            file_size=10,
            checksum_sha256="a" * 64,
            scan_status="clean",
            quarantined=False,
        )
        db.add_all([note, attachment])
        db.flush()
        if record != hidden:
            expected.update([str(record.id), str(note.id), str(attachment.id)])
    permissions = permission_service.get_effective_permissions(
        db, context.org.id, context.intake.user_id, context.intake.role.value
    )
    result = search_service.global_search(
        db,
        context.org.id,
        "Searchscope",
        context.intake.user_id,
        context.intake.role.value,
        permissions,
        entity_types=["donor", "note", "attachment"],
        limit=20,
    )
    assert {str(row["entity_id"]) for row in result["results"]} == expected
    page = search_service.global_search(
        db,
        context.org.id,
        "Searchscope",
        context.intake.user_id,
        context.intake.role.value,
        permissions,
        entity_types=["donor"],
        limit=1,
    )
    assert len(page["results"]) == 1
    assert str(page["results"][0]["entity_id"]) in expected


async def test_form_review_queue_and_actions_are_separate_from_builder(
    db, context, authed_client, test_auth
):
    from app.core.csrf import CSRF_HEADER
    from app.db.models import Form, FormSubmission

    member = (
        db.query(Membership)
        .filter_by(organization_id=context.org.id, user_id=test_auth.user.id)
        .one()
    )
    member.role = "intake_specialist"
    actor = SimpleNamespace(
        org_id=context.org.id, user_id=test_auth.user.id, role=Role.INTAKE_SPECIALIST
    )
    own = _record(db, actor, "donor", suffix=4)
    hidden = _record(db, context.manager, "donor", suffix=5)
    form = Form(
        organization_id=context.org.id,
        name="Applications",
        lead_kind="egg_donor",
        status="published",
    )
    db.add(form)
    db.flush()
    submissions = []
    for donor in (None, own, hidden):
        submission = FormSubmission(
            organization_id=context.org.id,
            form_id=form.id,
            donor_id=donor.id if donor else None,
            lead_kind="egg_donor",
            answers_json={"full_name": "Applicant"},
            source_mode="shared",
            match_status="ambiguous_review",
        )
        db.add(submission)
        submissions.append(submission)
    db.flush()
    response = await authed_client.get("/forms/submission-review/forms")
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [str(form.id)]
    response = await authed_client.get(f"/forms/{form.id}/submissions")
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()} == {str(row.id) for row in submissions[:2]}
    assert (await authed_client.get("/forms")).status_code == 403
    assert (
        await authed_client.get(f"/forms/submissions/{submissions[2].id}/match-candidates")
    ).status_code == 403
    assert (await authed_client.get(f"/forms/{uuid4()}/submissions")).status_code == 404
    csrf = authed_client.headers.pop(CSRF_HEADER)
    response = await authed_client.post(
        f"/forms/submissions/{submissions[0].id}/match/resolve", json={"create_intake_lead": True}
    )
    assert response.status_code == 403
    authed_client.headers[CSRF_HEADER] = csrf
    member.role = "operations"
    db.flush()
    response = await authed_client.get(f"/forms/{form.id}/submissions")
    assert response.status_code == 200, response.text
    assert {row["id"] for row in response.json()} == {str(row.id) for row in submissions[1:]}
    response = await authed_client.post(
        f"/forms/submissions/{submissions[1].id}/match/retry", json={}
    )
    assert response.status_code == 403
    assert (
        await authed_client.get(f"/forms/submissions/{submissions[0].id}/match-candidates")
    ).status_code == 403


async def test_donor_scope_detail_assignment_and_cross_org_claim(
    db, context, authed_client, test_auth
):
    from app.core.csrf import CSRF_HEADER

    member = (
        db.query(Membership)
        .filter_by(organization_id=context.org.id, user_id=test_auth.user.id)
        .one()
    )
    member.role = "intake_specialist"
    actor = SimpleNamespace(
        org_id=context.org.id, user_id=test_auth.user.id, role=Role.INTAKE_SPECIALIST
    )
    own = _record(db, actor, "donor", suffix=4)
    hidden = _record(db, context.manager, "donor", suffix=5)
    response = await authed_client.get("/donors", params={"per_page": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert (await authed_client.get(f"/donors/{hidden.id}")).status_code == 403
    response = await authed_client.patch(
        f"/donors/{own.id}", json={"owner_type": "user", "owner_id": str(context.manager.user_id)}
    )
    assert response.status_code == 403
    assert own.owner_id == actor.user_id
    csrf = authed_client.headers.pop(CSRF_HEADER)
    assert (await authed_client.post(f"/donors/{own.id}/claim")).status_code == 403
    authed_client.headers[CSRF_HEADER] = csrf
    member.role = "admin"
    other_org = Organization(id=uuid4(), name="Foreign", slug=f"scope-{uuid4()}")
    db.add(other_org)
    db.flush()
    foreign_actor, _ = _member(db, other_org.id, "intake_specialist")
    foreign = _record(db, foreign_actor, "donor")
    assert (await authed_client.post(f"/donors/{foreign.id}/claim")).status_code == 404


def test_match_list_detail_and_linked_tasks_require_both_participants(db, context):
    from app.db.models import Match, Task, UserPermissionOverride
    from app.services import match_service

    for permission in ("view_intended_parents", "view_matches"):
        db.add(
            UserPermissionOverride(
                organization_id=context.org.id,
                user_id=context.intake.user_id,
                permission=permission,
                override_type="grant",
            )
        )
    db.flush()
    donor = _record(db, context.intake, "donor")
    own_ip = _record(db, context.intake, "intended_parent", suffix=1)
    hidden_ip = _record(db, context.manager, "intended_parent", suffix=2)
    matches = []
    for index, ip in enumerate((own_ip, hidden_ip)):
        match = Match(
            organization_id=context.org.id,
            match_number=f"M{30001 + index}",
            match_kind="donor",
            donor_id=donor.id,
            intended_parent_id=ip.id,
            proposed_by_user_id=context.admin.user_id,
        )
        db.add(match)
        db.flush()
        matches.append(match)
    condition = match_service.match_visibility_filter(db, context.intake)
    assert [row.id for row in db.query(Match).filter(condition)] == [matches[0].id]
    assert (
        match_service.get_match_with_access(db, context.intake, matches[0].id).id == matches[0].id
    )
    with pytest.raises(HTTPException):
        match_service.get_match_with_access(db, context.intake, matches[1].id)
    for match in matches:
        db.add(
            Task(
                organization_id=context.org.id,
                match_id=match.id,
                donor_id=match.donor_id,
                intended_parent_id=match.intended_parent_id,
                title="Match task",
                created_by_user_id=context.intake.user_id,
                owner_type="user",
                owner_id=context.intake.user_id,
                task_type="other",
            )
        )
    db.flush()
    visible = (
        db.query(Task).filter(scopes.build_linked_visibility_filter(db, context.intake, Task)).all()
    )
    assert [task.match_id for task in visible] == [matches[0].id]


def test_manual_rematching_never_links_an_inaccessible_record(db, context, monkeypatch):
    from app.db.models import Form, FormSubmission
    from app.services import form_intake_service

    hidden = _record(db, context.manager, "surrogate")
    form = Form(organization_id=context.org.id, name="Intake", purpose="lead_capture")
    db.add(form)
    db.flush()
    submission = FormSubmission(
        organization_id=context.org.id,
        form_id=form.id,
        answers_json={"full_name": "Applicant"},
        source_mode="shared",
        match_status="ambiguous_review",
    )
    db.add(submission)
    db.flush()
    monkeypatch.setattr(form_intake_service, "_lead_capture_identity", lambda **kwargs: {})
    monkeypatch.setattr(form_intake_service, "_match_rule_phone", lambda *args, **kwargs: [hidden])
    result, outcome = form_intake_service.auto_match_submission(
        db, submission=submission, session=context.intake
    )
    assert outcome == "ambiguous_review"
    assert result.surrogate_id is None
    assert result.match_reason == "manual_review_required"


async def test_manual_email_requires_send_action_before_provider_lookup(
    db, context, authed_client, test_auth, monkeypatch
):
    from app.services import gmail_service

    member = (
        db.query(Membership)
        .filter_by(organization_id=context.org.id, user_id=test_auth.user.id)
        .one()
    )
    member.role = "operations"
    record = _record(db, context.intake, "surrogate")

    def unexpected_send(*args, **kwargs):
        raise AssertionError("Denied communication must not reach provider")

    monkeypatch.setattr(gmail_service, "send_email_logged", unexpected_send)
    response = await authed_client.post(
        f"/surrogates/{record.id}/send-email", json={"template_id": str(uuid4())}
    )
    assert response.status_code == 403, response.text
    assert "send_email" in response.json()["detail"]


def test_inactive_member_scope_can_be_reviewed_without_new_grants(db, context):
    addition = scopes.add_scope_addition(
        db,
        context.admin,
        context.intake.user_id,
        RecordScopeAdditionCreate(module="donors", assignment="all"),
    )
    context.member.is_active = False
    db.flush()
    assert [
        row.id for row in scopes.list_scope_additions(db, context.org.id, context.intake.user_id)
    ] == [addition.id]
    with pytest.raises(LookupError):
        scopes.add_scope_addition(
            db,
            context.admin,
            context.intake.user_id,
            RecordScopeAdditionCreate(module="surrogates", assignment="all"),
        )
    scopes.remove_scope_addition(db, context.admin, context.intake.user_id, addition.id)
    assert scopes.list_scope_additions(db, context.org.id, context.intake.user_id) == []


async def test_v2_surrogate_consumers_ignore_legacy_post_checkbox(
    db, context, authed_client, test_auth
):
    from app.db.models import RolePermission
    from app.services import queue_service

    member = (
        db.query(Membership)
        .filter_by(organization_id=context.org.id, user_id=test_auth.user.id)
        .one()
    )
    member.role = "case_manager"
    db.add(
        RolePermission(
            organization_id=context.org.id,
            role="case_manager",
            permission="view_post_approval_surrogates",
            is_granted=False,
        )
    )
    actor = SimpleNamespace(
        org_id=context.org.id, user_id=test_auth.user.id, role=Role.CASE_MANAGER
    )
    mine = _record(db, actor, "surrogate", key="approved", suffix=9)
    mine.full_name = "Scopeparity Search"
    pool = queue_service.get_or_create_surrogate_pool_queue(db, context.org.id)
    mine.owner_type = "queue"
    mine.owner_id = pool.id
    db.flush()
    response = await authed_client.get("/surrogates")
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [str(mine.id)]
    response = await authed_client.get("/surrogates/created-dates")
    assert response.status_code == 200, response.text
    assert response.json()
    response = await authed_client.get("/search", params={"q": "Scopeparity", "types": "surrogate"})
    assert response.status_code == 200, response.text
    assert [row["entity_id"] for row in response.json()["results"]] == [str(mine.id)]
    response = await authed_client.get("/surrogates/claim-queue")
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == [str(mine.id)]
    scopes.save_role_scope(
        db,
        context.admin,
        "case_manager",
        "surrogates",
        RecordScopeRule(assignment="assigned", phase="post_approval"),
    )
    response = await authed_client.get("/surrogates/claim-queue")
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0
    assert (await authed_client.post(f"/surrogates/{mine.id}/claim")).status_code == 403


def test_intelligent_suggestions_and_summary_follow_scopes_and_view_action(db, context):
    from datetime import UTC, datetime, timedelta

    from app.db.models import OrgIntelligentSuggestionRule, RolePermission
    from app.services import intelligent_suggestions_service as suggestions

    record = _record(db, context.intake, "surrogate", key="approved")
    record.created_at = datetime.now(UTC) - timedelta(days=40)
    from app.db.models import PipelineStage

    stage = db.get(PipelineStage, record.stage_id)
    rule = OrgIntelligentSuggestionRule(
        organization_id=context.org.id,
        template_key="stage_followup_custom",
        name="Approval followup",
        rule_kind="stage_inactivity",
        stage_slug=stage.slug,
        business_days=1,
    )
    db.add(rule)
    db.flush()
    summary = suggestions.get_intelligent_summary(
        db, org_id=context.org.id, user_id=context.manager.user_id, user_role=context.manager.role
    )
    assert summary["total"] == 1
    assert next(row for row in summary["rules"] if row["id"] == str(rule.id))["match_count"] == 1
    scopes.save_role_scope(
        db,
        context.admin,
        "case_manager",
        "surrogates",
        RecordScopeRule(assignment="assigned", phase="post_approval"),
    )
    assert (
        suggestions.get_intelligent_summary(
            db,
            org_id=context.org.id,
            user_id=context.manager.user_id,
            user_role=context.manager.role,
        )["total"]
        == 0
    )
    scopes.grant_collaborator(db, context.admin, "surrogate", record.id, context.intake.user_id)
    assert (
        suggestions.get_intelligent_summary(
            db, org_id=context.org.id, user_id=context.intake.user_id, user_role=context.intake.role
        )["total"]
        == 1
    )
    db.add(
        RolePermission(
            organization_id=context.org.id,
            role="intake_specialist",
            permission="view_surrogates",
            is_granted=False,
        )
    )
    db.flush()
    assert (
        suggestions.get_intelligent_summary(
            db, org_id=context.org.id, user_id=context.intake.user_id, user_role=context.intake.role
        )["total"]
        == 0
    )


@pytest.mark.parametrize("kind", ["surrogate", "donor"])
async def test_appointment_list_and_detail_follow_revoked_collaboration(
    db, context, authed_client, test_auth, monkeypatch, kind
):
    from datetime import UTC, datetime, timedelta

    from app.db.models import Appointment
    from app.services import appointment_integrations

    member = (
        db.query(Membership)
        .filter_by(organization_id=context.org.id, user_id=test_auth.user.id)
        .one()
    )
    member.role = "intake_specialist"
    record = _record(db, context.manager, kind, key="approved")
    scopes.grant_collaborator(db, context.admin, kind, record.id, test_auth.user.id)
    now = datetime.now(UTC)
    appointment = Appointment(
        organization_id=context.org.id,
        user_id=test_auth.user.id,
        **{f"{kind}_id": record.id},
        client_name="Applicant",
        client_email="appointment@example.test",
        client_phone="+15555551234",
        client_timezone="UTC",
        scheduled_start=now,
        scheduled_end=now + timedelta(minutes=30),
        duration_minutes=30,
        meeting_mode="phone",
        status="confirmed",
    )
    db.add(appointment)
    db.flush()
    monkeypatch.setattr(
        appointment_integrations, "backfill_confirmed_appointments_to_google", lambda **kwargs: None
    )
    monkeypatch.setattr(
        appointment_integrations,
        "sync_manual_google_events_for_appointments",
        lambda **kwargs: None,
    )
    response = await authed_client.get("/appointments", params={"per_page": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 1
    assert (await authed_client.get(f"/appointments/{appointment.id}")).status_code == 200
    scopes.remove_collaborator(db, context.admin, kind, record.id, test_auth.user.id)
    response = await authed_client.get("/appointments", params={"per_page": 1})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0
    assert response.json()["items"] == []
    assert (await authed_client.get(f"/appointments/{appointment.id}")).status_code == 403
