from __future__ import annotations

import threading
import uuid
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from app.core.encryption import hash_email
from app.core.policies import POLICIES
from app.db.enums import JobStatus, JobType, NotificationType, Role, TaskStatus, TaskType
from app.db.models import Donor, Job, Membership, Notification, Organization, Task, User
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import (
    dashboard_service,
    google_tasks_cleanup_service,
    google_tasks_sync_service,
    notification_service,
    oauth_service,
    permission_service,
    pipeline_service,
    task_events,
    task_service,
)
from app.utils.normalization import normalize_email


def _create_donor(db, *, org_id, donor_type: str = "egg") -> Donor:
    pipeline = pipeline_service.get_or_create_default_pipeline(
        db,
        org_id,
        entity_type=f"{donor_type}_donor",
    )
    stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new")
    assert stage is not None
    email = normalize_email(f"task-donor-{uuid.uuid4().hex[:8]}@example.com")
    donor = Donor(
        id=uuid.uuid4(),
        organization_id=org_id,
        donor_number=f"D{uuid.uuid4().int % 90000 + 10000:05d}",
        donor_type=donor_type,
        stage_id=stage.id,
        full_name="Task Donor",
        email=email,
        email_hash=hash_email(email),
    )
    db.add(donor)
    db.flush()
    return donor


def _create_donor_task(db, *, org_id, user_id, donor: Donor, **overrides) -> Task:
    values = {
        "organization_id": org_id,
        "created_by_user_id": user_id,
        "donor_id": donor.id,
        "owner_type": "user",
        "owner_id": user_id,
        "title": "Review donor application",
        "task_type": TaskType.OTHER.value,
    }
    values.update(overrides)
    task = Task(**values)
    db.add(task)
    db.flush()
    return task


def test_manual_synced_donor_task_delete_persists_cleanup_tombstone(
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        google_task_id="manual-delete-remote",
        google_task_list_id="manual-delete-list",
    )
    db.commit()
    task_id = task.id
    direct_deletes: list[uuid.UUID] = []
    monkeypatch.setattr(
        google_tasks_sync_service,
        "delete_platform_task_from_google",
        lambda _db, deleted_task: direct_deletes.append(deleted_task.id),
    )

    task_service.delete_task(db, task)

    assert db.get(Task, task_id) is None
    assert direct_deletes == []
    cleanup_job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_auth.org.id,
            Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
        )
        .one()
    )
    assert cleanup_job.payload["source_task_id"] == str(task_id)
    assert cleanup_job.payload["google_task_id"] == "manual-delete-remote"


def test_manual_synced_generic_task_delete_preserves_best_effort_google_delete(
    db,
    test_auth,
    monkeypatch,
):
    task = Task(
        organization_id=test_auth.org.id,
        created_by_user_id=test_auth.user.id,
        owner_type="user",
        owner_id=test_auth.user.id,
        title="Generic synced task",
        task_type=TaskType.OTHER.value,
        google_task_id="generic-remote",
        google_task_list_id="generic-list",
    )
    db.add(task)
    db.commit()
    task_id = task.id
    direct_deletes: list[uuid.UUID] = []
    monkeypatch.setattr(
        google_tasks_sync_service,
        "delete_platform_task_from_google",
        lambda _db, deleted_task: direct_deletes.append(deleted_task.id),
    )

    task_service.delete_task(db, task)

    assert db.get(Task, task_id) is None
    assert direct_deletes == [task_id]
    assert (
        db.query(Job)
        .filter(Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value)
        .count()
        == 0
    )


def test_donor_task_reassignment_tombstones_old_owner_before_new_sync(
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    new_owner = User(
        email=f"new-donor-owner-{uuid.uuid4().hex}@example.com",
        display_name="New Donor Owner",
        is_active=True,
    )
    db.add(new_owner)
    db.flush()
    db.add(
        Membership(
            user_id=new_owner.id,
            organization_id=test_auth.org.id,
            role=Role.DEVELOPER.value,
            is_active=True,
        )
    )
    task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        google_task_id="old-owner-remote",
        google_task_list_id="old-owner-list",
    )
    db.commit()

    sync_snapshots: list[tuple[uuid.UUID, str | None]] = []
    monkeypatch.setattr(
        task_service,
        "_sync_task_to_google_best_effort",
        lambda _db, updated: sync_snapshots.append(
            (updated.owner_id, updated.google_task_id)
        ),
    )

    updated = task_service.update_task(
        db,
        task,
        TaskUpdate(owner_type="user", owner_id=new_owner.id),
        actor_user_id=test_auth.user.id,
    )

    assert updated.owner_id == new_owner.id
    assert updated.google_task_id is None
    assert sync_snapshots == [(new_owner.id, None)]
    cleanup_job = (
        db.query(Job)
        .filter(Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value)
        .one()
    )
    assert cleanup_job.payload["user_id"] == str(test_auth.user.id)
    assert cleanup_job.payload["google_task_id"] == "old-owner-remote"
    assert cleanup_job.payload["google_task_list_id"] == "old-owner-list"


@pytest.mark.asyncio
async def test_donor_reassignment_defers_new_owner_remote_until_old_cleanup_finishes(
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    new_owner = User(
        email=f"deferred-donor-owner-{uuid.uuid4().hex}@example.com",
        display_name="Deferred Donor Owner",
        is_active=True,
    )
    db.add(new_owner)
    db.flush()
    db.add(
        Membership(
            user_id=new_owner.id,
            organization_id=test_auth.org.id,
            role=Role.DEVELOPER.value,
            is_active=True,
        )
    )
    task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        google_task_id="prior-owner-remote",
        google_task_list_id="prior-owner-list",
    )
    db.commit()
    monkeypatch.setattr(task_service, "_sync_task_to_google_best_effort", lambda *_args: None)

    task = task_service.update_task(
        db,
        task,
        TaskUpdate(owner_type="user", owner_id=new_owner.id),
        actor_user_id=test_auth.user.id,
    )
    cleanup_job = (
        db.query(Job)
        .filter(Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value)
        .one()
    )

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(granted_scopes=None),
    )
    remote_creates: list[uuid.UUID] = []

    async def upsert(updated_task, _db):
        remote_creates.append(updated_task.owner_id)
        return "new-owner-remote", "new-owner-list", None

    monkeypatch.setattr(
        google_tasks_sync_service,
        "_upsert_google_task_for_platform_task",
        upsert,
    )

    google_tasks_sync_service.sync_platform_task_to_google(db, task)

    assert remote_creates == []
    recovery_job = (
        db.query(Job)
        .filter(Job.job_type == JobType.GOOGLE_TASK_CREATION_RECONCILE.value)
        .one()
    )
    assert recovery_job.payload["user_id"] == str(new_owner.id)

    cleanup_job.status = JobStatus.COMPLETED.value
    db.commit()

    async def access_token(*_args, **_kwargs):
        return "token"

    async def concrete_list(_token, _task_list_id):
        return "new-owner-list"

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_access_token_async",
        access_token,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "_resolve_concrete_google_task_list_id",
        concrete_list,
    )

    await google_tasks_sync_service.reconcile_uncertain_google_donor_task_creation(
        db,
        recovery_job,
    )
    db.commit()

    db.refresh(task)
    assert remote_creates == [new_owner.id]
    assert task.google_task_id == "new-owner-remote"
    assert task.google_task_list_id == "new-owner-list"


@pytest.mark.asyncio
async def test_donor_reassignment_waits_for_prior_owner_uncertain_creation(
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    new_owner = User(
        email=f"uncertain-reassign-{uuid.uuid4().hex}@example.com",
        display_name="Uncertain Reassignment Owner",
        is_active=True,
    )
    db.add(new_owner)
    db.flush()
    db.add(
        Membership(
            user_id=new_owner.id,
            organization_id=test_auth.org.id,
            role=Role.DEVELOPER.value,
            is_active=True,
        )
    )
    task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
    )
    db.commit()
    old_recovery_id = google_tasks_sync_service._ensure_donor_creation_recovery_job(db, task)
    monkeypatch.setattr(task_service, "_sync_task_to_google_best_effort", lambda *_args: None)
    task = task_service.update_task(
        db,
        task,
        TaskUpdate(owner_type="user", owner_id=new_owner.id),
        actor_user_id=test_auth.user.id,
    )

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(granted_scopes=None),
    )
    remote_creates: list[uuid.UUID] = []

    async def upsert(updated_task, _db):
        remote_creates.append(updated_task.owner_id)
        return "new-owner-after-recovery", "new-owner-list", None

    monkeypatch.setattr(
        google_tasks_sync_service,
        "_upsert_google_task_for_platform_task",
        upsert,
    )
    google_tasks_sync_service.sync_platform_task_to_google(db, task)
    assert remote_creates == []

    recovery_jobs = (
        db.query(Job)
        .filter(Job.job_type == JobType.GOOGLE_TASK_CREATION_RECONCILE.value)
        .all()
    )
    old_recovery = next(job for job in recovery_jobs if job.id == old_recovery_id)
    new_recovery = next(
        job for job in recovery_jobs if job.payload["user_id"] == str(new_owner.id)
    )
    old_recovery.status = JobStatus.RUNNING.value
    db.commit()

    async def access_token(*_args, **_kwargs):
        return "token"

    async def concrete_list(_token, _task_list_id):
        return "concrete-list"

    async def no_prior_remote(**_kwargs):
        return [], None

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_access_token_async",
        access_token,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "_resolve_concrete_google_task_list_id",
        concrete_list,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "_find_correlated_google_donor_tasks",
        no_prior_remote,
    )

    await google_tasks_sync_service.reconcile_uncertain_google_donor_task_creation(
        db,
        old_recovery,
    )
    old_recovery.status = JobStatus.COMPLETED.value
    db.commit()
    await google_tasks_sync_service.reconcile_uncertain_google_donor_task_creation(
        db,
        new_recovery,
    )
    db.commit()

    db.refresh(task)
    assert remote_creates == [new_owner.id]
    assert task.google_task_id == "new-owner-after-recovery"


def test_archived_donor_rejects_new_task(db, test_auth):
    donor = _create_donor(db, org_id=test_auth.org.id)
    donor.is_archived = True
    db.commit()

    with pytest.raises(ValueError, match="archived donor"):
        task_service.create_task(
            db,
            test_auth.org.id,
            test_auth.user.id,
            TaskCreate(title="Must not be created", donor_id=donor.id),
        )


def test_member_deprovision_blocks_synced_or_unresolved_donor_google_work(
    db,
    test_auth,
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        google_task_id="still-synced",
        google_task_list_id="concrete-list",
    )
    db.commit()

    with pytest.raises(ValueError, match="synced donor tasks remain"):
        permission_service.assert_google_donor_tasks_deprovisionable(
            db,
            test_auth.org.id,
            test_auth.user.id,
        )

    task.google_task_id = None
    task.google_task_list_id = None
    recovery_job = Job(
        organization_id=test_auth.org.id,
        job_type=JobType.GOOGLE_TASK_CREATION_RECONCILE.value,
        status=JobStatus.PENDING.value,
        payload={
            "user_id": str(test_auth.user.id),
            "source_task_id": str(task.id),
            "google_task_list_id": "concrete-list",
        },
    )
    db.add(recovery_job)
    db.commit()

    with pytest.raises(ValueError, match="cleanup is pending or failed"):
        permission_service.assert_google_donor_tasks_deprovisionable(
            db,
            test_auth.org.id,
            test_auth.user.id,
        )


def test_compensation_double_failure_keeps_creation_recovery_outbox(
    db_engine,
    monkeypatch,
):
    session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with session_factory() as setup_db:
        setup_db.add_all(
            [
                Organization(
                    id=org_id,
                    name="Double Failure Recovery Org",
                    slug=f"double-failure-recovery-{uuid.uuid4().hex}",
                ),
                User(
                    id=user_id,
                    email=f"double-failure-{uuid.uuid4().hex}@example.com",
                    display_name="Double Failure User",
                ),
            ]
        )
        setup_db.flush()
        setup_db.add(
            Membership(
                user_id=user_id,
                organization_id=org_id,
                role=Role.DEVELOPER.value,
            )
        )
        donor = _create_donor(setup_db, org_id=org_id)
        task = _create_donor_task(
            setup_db,
            org_id=org_id,
            user_id=user_id,
            donor=donor,
        )
        setup_db.commit()
        task_id = task.id
        recovery_job_id = google_tasks_sync_service._ensure_donor_creation_recovery_job(
            setup_db,
            task,
        )

    monkeypatch.setattr(
        google_tasks_cleanup_service,
        "enqueue_remote_deletion",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("outbox unavailable")),
    )
    def fail_delete(coro, *_args, **_kwargs):
        coro.close()
        raise RuntimeError("delete unavailable")

    monkeypatch.setattr(google_tasks_sync_service, "run_async", fail_delete)

    try:
        with session_factory() as recovery_db:
            google_tasks_sync_service._compensate_failed_donor_task_identity_persistence(
                recovery_db,
                org_id=org_id,
                user_id=user_id,
                source_task_id=task_id,
                google_task_list_id="concrete-list",
                google_task_id="untracked-remote",
            )

        with session_factory() as verify_db:
            recovery_job = verify_db.get(Job, recovery_job_id)
            assert recovery_job is not None
            assert recovery_job.status == JobStatus.PENDING.value
    finally:
        with session_factory() as cleanup_db:
            cleanup_db.query(Organization).filter(Organization.id == org_id).delete()
            cleanup_db.query(User).filter(User.id == user_id).delete()
            cleanup_db.commit()


def test_cleanup_enqueue_membership_lock_fences_deprovision(
    db_engine,
    monkeypatch,
):
    session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with session_factory() as setup_db:
        setup_db.add_all(
            [
                Organization(
                    id=org_id,
                    name="Cleanup Membership Fence Org",
                    slug=f"cleanup-membership-fence-{uuid.uuid4().hex}",
                ),
                User(
                    id=user_id,
                    email=f"cleanup-membership-fence-{uuid.uuid4().hex}@example.com",
                    display_name="Cleanup Membership Fence User",
                ),
            ]
        )
        setup_db.flush()
        setup_db.add(
            Membership(
                user_id=user_id,
                organization_id=org_id,
                role=Role.DEVELOPER.value,
                is_active=True,
            )
        )
        setup_db.commit()

    membership_locked = threading.Event()
    enqueue_may_finish = threading.Event()
    deprovision_finished = threading.Event()
    errors: list[BaseException] = []
    deprovision_result: list[str] = []
    original_enqueue = google_tasks_cleanup_service._enqueue_validated_remote_deletion

    def paused_enqueue(*args, **kwargs):
        membership_locked.set()
        if not enqueue_may_finish.wait(timeout=2):
            raise TimeoutError("cleanup enqueue was not released")
        return original_enqueue(*args, **kwargs)

    monkeypatch.setattr(
        google_tasks_cleanup_service,
        "_enqueue_validated_remote_deletion",
        paused_enqueue,
    )

    def enqueue_cleanup() -> None:
        with session_factory() as enqueue_db:
            try:
                google_tasks_cleanup_service.enqueue_remote_deletion(
                    enqueue_db,
                    org_id=org_id,
                    user_id=user_id,
                    source_task_id=uuid.uuid4(),
                    google_task_id="membership-race-remote",
                    google_task_list_id="membership-race-list",
                )
                enqueue_db.commit()
            except BaseException as exc:
                errors.append(exc)

    def deprovision_check() -> None:
        with session_factory() as deprovision_db:
            try:
                permission_service.assert_google_donor_tasks_deprovisionable(
                    deprovision_db,
                    org_id,
                    user_id,
                )
                deprovision_result.append("allowed")
            except ValueError as exc:
                deprovision_result.append(str(exc))
            except BaseException as exc:
                errors.append(exc)
            finally:
                deprovision_db.rollback()
                deprovision_finished.set()

    enqueue_thread = threading.Thread(target=enqueue_cleanup)
    deprovision_thread = threading.Thread(target=deprovision_check)
    try:
        enqueue_thread.start()
        assert membership_locked.wait(timeout=2), errors
        deprovision_thread.start()
        assert not deprovision_finished.wait(timeout=0.2)
        enqueue_may_finish.set()
        enqueue_thread.join(timeout=2)
        deprovision_thread.join(timeout=2)

        assert not enqueue_thread.is_alive()
        assert not deprovision_thread.is_alive()
        assert errors == []
        assert len(deprovision_result) == 1
        assert "Google cleanup is pending or failed" in deprovision_result[0]
    finally:
        enqueue_may_finish.set()
        if enqueue_thread.is_alive():
            enqueue_thread.join(timeout=2)
        if deprovision_thread.is_alive():
            deprovision_thread.join(timeout=2)
        with session_factory() as cleanup_db:
            cleanup_db.query(Organization).filter(Organization.id == org_id).delete()
            cleanup_db.query(User).filter(User.id == user_id).delete()
            cleanup_db.commit()


def test_donor_google_post_is_fenced_against_transactional_cleanup(
    db_engine,
    monkeypatch,
):
    session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with session_factory() as setup_db:
        setup_db.add_all(
            [
                Organization(
                    id=org_id,
                    name="Google Task Fence Org",
                    slug=f"google-task-fence-{uuid.uuid4().hex}",
                ),
                User(
                    id=user_id,
                    email=f"google-task-fence-{uuid.uuid4().hex}@example.com",
                    display_name="Google Task Fence User",
                ),
            ]
        )
        setup_db.flush()
        setup_db.add(
            Membership(
                user_id=user_id,
                organization_id=org_id,
                role=Role.DEVELOPER.value,
            )
        )
        donor = _create_donor(setup_db, org_id=org_id)
        task = _create_donor_task(
            setup_db,
            org_id=org_id,
            user_id=user_id,
            donor=donor,
        )
        setup_db.commit()
        task_id = task.id

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(granted_scopes=None),
    )
    monkeypatch.setattr(task_service, "user_can_view_donors", lambda *_args, **_kwargs: True)
    provider_started = threading.Event()
    provider_may_return = threading.Event()
    cleanup_finished = threading.Event()
    errors: list[BaseException] = []

    async def remote_create(_task, _db):
        provider_started.set()
        if not provider_may_return.wait(timeout=2):
            raise TimeoutError("provider response was not released")
        return "raced-remote-task", "@default", None

    monkeypatch.setattr(
        google_tasks_sync_service,
        "_upsert_google_task_for_platform_task",
        remote_create,
    )

    def sync_task() -> None:
        with session_factory() as sync_db:
            try:
                synced_task = sync_db.get(Task, task_id)
                assert synced_task is not None
                google_tasks_sync_service.sync_platform_task_to_google(sync_db, synced_task)
            except BaseException as exc:
                errors.append(exc)

    def cleanup_task() -> None:
        with session_factory() as cleanup_db:
            try:
                google_tasks_cleanup_service.enqueue_donor_task_remote_deletions(
                    cleanup_db,
                    org_id=org_id,
                    task_ids={task_id},
                )
                cleanup_db.query(Task).filter(
                    Task.organization_id == org_id,
                    Task.id == task_id,
                ).delete(synchronize_session=False)
                cleanup_db.commit()
            except BaseException as exc:
                errors.append(exc)
            finally:
                cleanup_finished.set()

    sync_thread = threading.Thread(target=sync_task)
    cleanup_thread = threading.Thread(target=cleanup_task)
    try:
        sync_thread.start()
        assert provider_started.wait(timeout=2), errors
        cleanup_thread.start()
        cleanup_was_fenced = not cleanup_finished.wait(timeout=0.2)
        provider_may_return.set()
        sync_thread.join(timeout=2)
        cleanup_thread.join(timeout=2)

        assert cleanup_was_fenced
        assert not sync_thread.is_alive()
        assert not cleanup_thread.is_alive()
        assert errors == []
        with session_factory() as verify_db:
            assert verify_db.get(Task, task_id) is None
            cleanup_job = (
                verify_db.query(Job)
                .filter(
                    Job.organization_id == org_id,
                    Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
                )
                .one()
            )
            assert cleanup_job.payload["google_task_id"] == "raced-remote-task"
            assert cleanup_job.payload["google_task_list_id"] == "@default"
    finally:
        provider_may_return.set()
        if sync_thread.is_alive():
            sync_thread.join(timeout=2)
        if cleanup_thread.is_alive():
            cleanup_thread.join(timeout=2)
        with session_factory() as cleanup_db:
            cleanup_db.query(Organization).filter(Organization.id == org_id).delete()
            cleanup_db.query(User).filter(User.id == user_id).delete()
            cleanup_db.commit()


def test_donor_google_post_commit_failure_tombstones_and_compensates(
    db_engine,
    monkeypatch,
):
    session_factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with session_factory() as setup_db:
        setup_db.add_all(
            [
                Organization(
                    id=org_id,
                    name="Google Compensation Org",
                    slug=f"google-compensation-{uuid.uuid4().hex}",
                ),
                User(
                    id=user_id,
                    email=f"google-compensation-{uuid.uuid4().hex}@example.com",
                    display_name="Google Compensation User",
                ),
            ]
        )
        setup_db.flush()
        setup_db.add(
            Membership(
                user_id=user_id,
                organization_id=org_id,
                role=Role.DEVELOPER.value,
            )
        )
        donor = _create_donor(setup_db, org_id=org_id)
        task = _create_donor_task(
            setup_db,
            org_id=org_id,
            user_id=user_id,
            donor=donor,
        )
        setup_db.commit()
        task_id = task.id

    monkeypatch.setattr(
        google_tasks_sync_service.oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: SimpleNamespace(granted_scopes=None),
    )
    monkeypatch.setattr(task_service, "user_can_view_donors", lambda *_args, **_kwargs: True)
    remote_creates: list[uuid.UUID] = []
    remote_deletes: list[tuple[str, str]] = []

    async def remote_create(created_task, _db):
        remote_creates.append(created_task.id)
        return "unpersisted-remote", "unpersisted-list", None

    async def remote_delete(
        _db,
        *,
        user_id,
        google_task_list_id,
        google_task_id,
    ):
        del user_id
        remote_deletes.append((google_task_list_id, google_task_id))
        return True

    monkeypatch.setattr(
        google_tasks_sync_service,
        "_upsert_google_task_for_platform_task",
        remote_create,
    )
    monkeypatch.setattr(
        google_tasks_sync_service,
        "_delete_google_task_by_remote_identity",
        remote_delete,
    )
    try:
        with session_factory() as sync_db:
            persisted_task = sync_db.get(Task, task_id)
            assert persisted_task is not None
            original_commit = sync_db.commit
            commit_count = 0

            def fail_identity_commit_once():
                nonlocal commit_count
                commit_count += 1
                if commit_count == 2:
                    raise RuntimeError("identity persistence failed")
                return original_commit()

            monkeypatch.setattr(sync_db, "commit", fail_identity_commit_once)

            google_tasks_sync_service.sync_platform_task_to_google(sync_db, persisted_task)

            persisted_task = sync_db.get(Task, task_id)
            assert persisted_task is not None
            assert persisted_task.google_task_id is None
            assert remote_creates == [task_id]
            assert remote_deletes == [("unpersisted-list", "unpersisted-remote")]
            cleanup_job = (
                sync_db.query(Job)
                .filter(
                    Job.organization_id == org_id,
                    Job.job_type == JobType.GOOGLE_TASK_REMOTE_DELETE.value,
                )
                .one()
            )
            assert cleanup_job.status == JobStatus.PENDING.value
            assert cleanup_job.payload["source_task_id"] == str(task_id)
            assert cleanup_job.payload["google_task_id"] == "unpersisted-remote"

            google_tasks_sync_service.sync_platform_task_to_google(sync_db, persisted_task)
            assert remote_creates == [task_id]
    finally:
        with session_factory() as cleanup_db:
            cleanup_db.query(Organization).filter(Organization.id == org_id).delete()
            cleanup_db.query(User).filter(User.id == user_id).delete()
            cleanup_db.commit()


@pytest.mark.asyncio
async def test_create_and_filter_donor_task_hydrates_donor_metadata(
    authed_client, db, test_auth
):
    donor = _create_donor(db, org_id=test_auth.org.id, donor_type="egg")

    created = await authed_client.post(
        "/tasks",
        json={"title": "Review donor application", "donor_id": str(donor.id)},
    )

    assert created.status_code == 201, created.text
    assert created.json()["donor_id"] == str(donor.id)
    assert created.json()["donor_number"] == donor.donor_number
    assert created.json()["donor_type"] == "egg"
    assert created.json()["donor_name"] == donor.full_name

    listed = await authed_client.get("/tasks", params={"donor_id": str(donor.id)})
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["donor_id"] == str(donor.id)
    assert listed.json()["items"][0]["donor_number"] == donor.donor_number

    typed = await authed_client.get("/tasks", params={"donor_type": "egg"})
    assert typed.status_code == 200, typed.text
    assert typed.json()["total"] == 1
    assert typed.json()["items"][0]["donor_type"] == "egg"


@pytest.mark.asyncio
async def test_create_donor_task_rejects_other_subjects_and_cross_org_donor(
    authed_client, db, test_auth
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    ambiguous = await authed_client.post(
        "/tasks",
        json={
            "title": "Ambiguous task",
            "donor_id": str(donor.id),
            "surrogate_id": str(uuid.uuid4()),
        },
    )
    assert ambiguous.status_code == 400

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Donor Task Org",
        slug=f"other-donor-task-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    foreign_donor = _create_donor(db, org_id=other_org.id)

    cross_org = await authed_client.post(
        "/tasks",
        json={"title": "Cross-org donor task", "donor_id": str(foreign_donor.id)},
    )
    assert cross_org.status_code == 400
    assert cross_org.json()["detail"] == "Donor not found"


@pytest.mark.asyncio
async def test_donor_tasks_fail_closed_without_donor_view_permission(
    authed_client, db, test_auth, monkeypatch
):
    donor = _create_donor(db, org_id=test_auth.org.id)
    donor_task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        due_date=date.today() - timedelta(days=1),
    )
    db.commit()

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

    listed = await authed_client.get("/tasks")
    assert listed.status_code == 200, listed.text
    assert donor_task.id not in {uuid.UUID(item["id"]) for item in listed.json()["items"]}

    detail = await authed_client.get(f"/tasks/{donor_task.id}")
    assert detail.status_code == 403

    created = await authed_client.post(
        "/tasks",
        json={"title": "Forbidden donor task", "donor_id": str(donor.id)},
    )
    assert created.status_code == 403

    typed = await authed_client.get("/tasks", params={"donor_type": "egg"})
    assert typed.status_code == 403

    updated = await authed_client.patch(
        f"/tasks/{donor_task.id}",
        json={"title": "Must remain private"},
    )
    assert updated.status_code == 403

    completed = await authed_client.post(f"/tasks/{donor_task.id}/complete")
    assert completed.status_code == 403

    conversation = await authed_client.get(f"/ai/conversations/task/{donor_task.id}")
    assert conversation.status_code == 403

    upcoming = await authed_client.get("/dashboard/upcoming")
    assert upcoming.status_code == 200, upcoming.text
    assert str(donor_task.id) not in {item["id"] for item in upcoming.json()["tasks"]}

    attention = await authed_client.get("/dashboard/attention")
    assert attention.status_code == 200, attention.text
    assert str(donor_task.id) not in {
        item["id"] for item in attention.json()["overdue_tasks"]
    }
    assert attention.json()["overdue_count"] == 0


def test_non_admin_attention_includes_authorized_donor_tasks(db, test_org, test_user):
    donor = _create_donor(db, org_id=test_org.id, donor_type="sperm")
    donor_task = _create_donor_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        donor=donor,
        due_date=date.today() - timedelta(days=2),
    )
    db.commit()

    data = dashboard_service.get_attention_items(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        user_role="intake_specialist",
        can_view_donors=True,
    )

    assert str(donor_task.id) in {item["id"] for item in data["overdue_tasks"]}
    item = next(item for item in data["overdue_tasks"] if item["id"] == str(donor_task.id))
    assert item["donor_id"] == str(donor.id)
    assert item["donor_number"] == donor.donor_number
    assert item["donor_type"] == "sperm"


@pytest.mark.asyncio
async def test_donor_task_access_does_not_require_surrogate_view_permission(
    authed_client,
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id, donor_type="egg")
    donor_task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
    )
    db.commit()

    original_check = permission_service.check_permission

    def deny_surrogate_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["surrogates"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_surrogate_view)

    detail = await authed_client.get(f"/tasks/{donor_task.id}")
    assert detail.status_code == 200, detail.text

    updated = await authed_client.patch(
        f"/tasks/{donor_task.id}",
        json={"title": "Donor-only role can update donor tasks"},
    )
    assert updated.status_code == 200, updated.text


@pytest.mark.asyncio
async def test_donor_task_notifications_fail_closed_after_donor_permission_revoke(
    authed_client,
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id, donor_type="sperm")
    donor_task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
    )
    db.commit()

    notification_service.notify_task_assigned(
        db=db,
        task_id=donor_task.id,
        task_title=donor_task.title,
        org_id=test_auth.org.id,
        assignee_id=test_auth.user.id,
        actor_name="Coordinator",
        donor_number=donor.donor_number,
        donor_type=donor.donor_type,
    )
    existing = (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_auth.org.id,
            Notification.user_id == test_auth.user.id,
            Notification.entity_type == "donor_task",
            Notification.entity_id == donor_task.id,
        )
        .one()
    )
    assert donor.donor_number in (existing.body or "")
    direct = notification_service.create_notification(
        db=db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        type=NotificationType.WORKFLOW_NOTIFICATION,
        title="Direct donor notification",
        entity_type="donor",
        entity_id=donor.id,
    )
    assert direct is not None

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)

    listed = await authed_client.get("/me/notifications")
    assert listed.status_code == 200, listed.text
    assert str(existing.id) not in {item["id"] for item in listed.json()["items"]}
    assert str(direct.id) not in {item["id"] for item in listed.json()["items"]}
    assert listed.json()["unread_count"] == 0

    counted = await authed_client.get("/me/notifications/count")
    assert counted.status_code == 200, counted.text
    assert counted.json()["count"] == 0

    marked = await authed_client.patch(f"/me/notifications/{existing.id}/read")
    assert marked.status_code == 404

    marked_all = await authed_client.post("/me/notifications/read-all")
    assert marked_all.status_code == 200, marked_all.text
    assert marked_all.json()["marked_read"] == 0

    second_task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        title="New private donor notification",
    )
    db.commit()
    notification_service.notify_task_assigned(
        db=db,
        task_id=second_task.id,
        task_title=second_task.title,
        org_id=test_auth.org.id,
        assignee_id=test_auth.user.id,
        actor_name="Coordinator",
        donor_number=donor.donor_number,
        donor_type=donor.donor_type,
    )
    assert (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_auth.org.id,
            Notification.entity_type == "donor_task",
            Notification.entity_id == second_task.id,
        )
        .count()
        == 0
    )

    google_sync_attempts: list[object] = []

    def capture_google_integration(*args, **kwargs):
        google_sync_attempts.append((args, kwargs))
        return object()

    monkeypatch.setattr(oauth_service, "get_user_integration", capture_google_integration)
    google_tasks_sync_service.sync_platform_task_to_google(db, second_task)
    assert google_sync_attempts == []


@pytest.mark.asyncio
async def test_task_list_hides_cross_org_donor_subject(
    authed_client,
    db,
    test_auth,
):
    other_org = Organization(
        id=uuid.uuid4(),
        name="Foreign Donor Subject Org",
        slug=f"foreign-donor-subject-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    foreign_donor = _create_donor(db, org_id=other_org.id)
    corrupt_task = Task(
        organization_id=test_auth.org.id,
        created_by_user_id=test_auth.user.id,
        donor_id=foreign_donor.id,
        owner_type="user",
        owner_id=test_auth.user.id,
        title="Cross-organization donor task must be hidden",
        task_type=TaskType.OTHER.value,
    )
    db.add(corrupt_task)
    db.commit()

    listed = await authed_client.get("/tasks")

    assert listed.status_code == 200, listed.text
    assert str(corrupt_task.id) not in {item["id"] for item in listed.json()["items"]}

    notification = notification_service.create_notification(
        db=db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        type=NotificationType.TASK_ASSIGNED,
        title="Cross-org donor task notification must be suppressed",
        entity_type="donor_task",
        entity_id=corrupt_task.id,
    )
    assert notification is None
    assert (
        db.query(Notification)
        .filter(
            Notification.organization_id == test_auth.org.id,
            Notification.entity_id == corrupt_task.id,
        )
        .count()
        == 0
    )


@pytest.mark.asyncio
async def test_inbound_google_sync_does_not_reimport_unauthorized_donor_task(
    db,
    test_auth,
    monkeypatch,
):
    donor = _create_donor(db, org_id=test_auth.org.id, donor_type="egg")
    donor_task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        title="Private donor task",
        google_task_id="private-donor-remote",
        google_task_list_id="private-list",
    )
    db.commit()

    original_check = permission_service.check_permission

    def deny_donor_view(db, org_id, user_id, role, permission):
        if permission == POLICIES["donors"].default.value:
            return False
        return original_check(db, org_id, user_id, role, permission)

    monkeypatch.setattr(permission_service, "check_permission", deny_donor_view)
    monkeypatch.setattr(
        oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: type(
            "Integration",
            (),
            {"granted_scopes": None},
        )(),
    )

    async def access_token(*_args, **_kwargs):
        return "token"

    async def task_lists(_token):
        return [{"id": "private-list"}], None

    async def google_tasks(_token, _task_list_id):
        return [
            {
                "id": "private-donor-remote",
                "title": "Private donor task from Google",
                "notes": f"Donor #{donor.donor_number}",
                "status": "needsAction",
                "updated": "2026-08-29T12:00:00Z",
            }
        ]

    monkeypatch.setattr(oauth_service, "get_access_token_async", access_token)
    monkeypatch.setattr(google_tasks_sync_service, "_list_google_task_lists", task_lists)
    monkeypatch.setattr(google_tasks_sync_service, "_list_google_tasks", google_tasks)

    changed = await google_tasks_sync_service._sync_google_tasks_for_user_async(
        db,
        user_id=test_auth.user.id,
        org_id=test_auth.org.id,
    )

    assert changed == 0
    assert db.get(Task, donor_task.id).title == "Private donor task"
    assert (
        db.query(Task)
        .filter(
            Task.organization_id == test_auth.org.id,
            Task.google_task_id == "private-donor-remote",
        )
        .count()
        == 1
    )


@pytest.mark.parametrize("cleanup_status", [JobStatus.PENDING.value, JobStatus.FAILED.value])
@pytest.mark.parametrize(
    ("cleanup_list_id", "remote_list_id"),
    [("purged-list", "purged-list"), ("@default", "actual-default-list")],
)
@pytest.mark.asyncio
async def test_inbound_google_sync_does_not_recreate_tombstoned_donor_task(
    db,
    test_auth,
    monkeypatch,
    cleanup_status,
    cleanup_list_id,
    remote_list_id,
):
    cleanup_job = Job(
        organization_id=test_auth.org.id,
        job_type=JobType.GOOGLE_TASK_REMOTE_DELETE.value,
        status=cleanup_status,
        payload={
            "user_id": str(test_auth.user.id),
            "source_task_id": str(uuid.uuid4()),
            "google_task_id": "purged-donor-remote",
            "google_task_list_id": cleanup_list_id,
        },
    )
    db.add(cleanup_job)
    db.commit()

    monkeypatch.setattr(
        oauth_service,
        "get_user_integration",
        lambda *_args, **_kwargs: type(
            "Integration",
            (),
            {"granted_scopes": None},
        )(),
    )

    async def access_token(*_args, **_kwargs):
        return "token"

    async def task_lists(_token):
        return [{"id": remote_list_id}], None

    async def google_tasks(_token, _task_list_id):
        return [
            {
                "id": "purged-donor-remote",
                "title": "Purged donor task must not return",
                "status": "needsAction",
                "updated": "2026-08-29T12:00:00Z",
            }
        ]

    monkeypatch.setattr(oauth_service, "get_access_token_async", access_token)
    monkeypatch.setattr(google_tasks_sync_service, "_list_google_task_lists", task_lists)
    monkeypatch.setattr(google_tasks_sync_service, "_list_google_tasks", google_tasks)

    changed = await google_tasks_sync_service._sync_google_tasks_for_user_async(
        db,
        user_id=test_auth.user.id,
        org_id=test_auth.org.id,
    )

    assert changed == 0
    assert (
        db.query(Task)
        .filter(
            Task.organization_id == test_auth.org.id,
            Task.google_task_id == "purged-donor-remote",
        )
        .count()
        == 0
    )


def test_overdue_task_count_excludes_unauthorized_and_cross_org_donor_subjects(
    db,
    test_auth,
):
    today = date.today()
    donor = _create_donor(db, org_id=test_auth.org.id, donor_type="sperm")
    _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        due_date=today - timedelta(days=1),
    )
    db.add(
        Task(
            organization_id=test_auth.org.id,
            created_by_user_id=test_auth.user.id,
            owner_type="user",
            owner_id=test_auth.user.id,
            title="Visible overdue task",
            task_type=TaskType.OTHER.value,
            due_date=today - timedelta(days=1),
        )
    )

    other_org = Organization(
        name="Foreign overdue donor count org",
        slug=f"foreign-overdue-count-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    foreign_donor = _create_donor(db, org_id=other_org.id)
    db.add(
        Task(
            organization_id=test_auth.org.id,
            created_by_user_id=test_auth.user.id,
            donor_id=foreign_donor.id,
            owner_type="user",
            owner_id=test_auth.user.id,
            title="Corrupt foreign donor overdue task",
            task_type=TaskType.OTHER.value,
            due_date=today - timedelta(days=1),
        )
    )
    db.commit()

    assert (
        task_service.count_overdue_tasks(
            db,
            test_auth.org.id,
            today,
            can_view_donors=False,
        )
        == 1
    )
    assert (
        task_service.count_overdue_tasks(
            db,
            test_auth.org.id,
            today,
            can_view_donors=True,
        )
        == 2
    )


@pytest.mark.asyncio
async def test_update_donor_task_can_relink_unlink_and_reject_invalid_subjects(
    authed_client, db, test_auth
):
    first_donor = _create_donor(db, org_id=test_auth.org.id)
    second_donor = _create_donor(db, org_id=test_auth.org.id)
    created = await authed_client.post(
        "/tasks",
        json={"title": "Editable donor task", "donor_id": str(first_donor.id)},
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["id"]

    relinked = await authed_client.patch(
        f"/tasks/{task_id}",
        json={
            "surrogate_id": None,
            "intended_parent_id": None,
            "donor_id": str(second_donor.id),
        },
    )
    assert relinked.status_code == 200, relinked.text
    assert relinked.json()["donor_id"] == str(second_donor.id)
    assert relinked.json()["donor_number"] == second_donor.donor_number

    ambiguous = await authed_client.patch(
        f"/tasks/{task_id}",
        json={"surrogate_id": str(uuid.uuid4()), "donor_id": str(second_donor.id)},
    )
    assert ambiguous.status_code == 400
    assert "cannot be combined" in ambiguous.json()["detail"]

    other_org = Organization(
        id=uuid.uuid4(),
        name="Other Donor Task Update Org",
        slug=f"other-donor-task-update-{uuid.uuid4().hex[:8]}",
        ai_enabled=True,
    )
    db.add(other_org)
    db.flush()
    foreign_donor = _create_donor(db, org_id=other_org.id)
    cross_org = await authed_client.patch(
        f"/tasks/{task_id}",
        json={
            "surrogate_id": None,
            "intended_parent_id": None,
            "donor_id": str(foreign_donor.id),
        },
    )
    assert cross_org.status_code == 400
    assert cross_org.json()["detail"] == "Donor not found"

    unlinked = await authed_client.patch(
        f"/tasks/{task_id}",
        json={"surrogate_id": None, "intended_parent_id": None, "donor_id": None},
    )
    assert unlinked.status_code == 200, unlinked.text
    assert unlinked.json()["surrogate_id"] is None
    assert unlinked.json()["intended_parent_id"] is None
    assert unlinked.json()["donor_id"] is None


@pytest.mark.asyncio
async def test_workflow_approval_task_subject_is_immutable(authed_client, db, test_auth):
    donor = _create_donor(db, org_id=test_auth.org.id)
    task = _create_donor_task(
        db,
        org_id=test_auth.org.id,
        user_id=test_auth.user.id,
        donor=donor,
        task_type=TaskType.WORKFLOW_APPROVAL.value,
        status=TaskStatus.PENDING.value,
    )
    db.commit()

    response = await authed_client.patch(
        f"/tasks/{task.id}",
        json={"surrogate_id": None, "intended_parent_id": None, "donor_id": None},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Workflow approval task subject cannot be changed"


def test_donor_task_context_notifications_and_google_metadata(db, test_org, test_user, monkeypatch):
    donor = _create_donor(db, org_id=test_org.id, donor_type="sperm")
    task = _create_donor_task(
        db,
        org_id=test_org.id,
        user_id=test_user.id,
        donor=donor,
        task_type=TaskType.WORKFLOW_APPROVAL.value,
        status=TaskStatus.PENDING.value,
    )
    db.commit()

    captured = {}
    monkeypatch.setattr(
        "app.services.notification_facade.notify_task_assigned",
        lambda **kwargs: captured.update(kwargs),
    )
    task_events.notify_task_assigned(
        db=db,
        task=task,
        actor_user_id=test_user.id,
        assignee_id=test_user.id,
    )
    assert captured["donor_number"] == donor.donor_number
    assert captured["donor_type"] == "sperm"

    context = task_service.get_task_context(db, test_org.id, [task])
    task_read = task_service.to_task_read(task, context)
    assert task_read.donor_id == donor.id
    assert task_read.donor_number == donor.donor_number
    assert task_read.donor_type == "sperm"
    assert task_read.donor_name == donor.full_name

    payload = google_tasks_sync_service._build_google_task_payload(task)
    assert f"Sperm donor #{donor.donor_number}" in payload["notes"]
