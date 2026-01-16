import uuid

from app.core.encryption import hash_email
from app.db.models import Organization, Pipeline, PipelineStage, Surrogate, EntityNote, Task
from app.services.ai_action_executor import AddNoteExecutor, CreateTaskExecutor
from app.utils.normalization import normalize_email


def _seed_org2_surrogate(db):
    org2 = Organization(
        id=uuid.uuid4(),
        name="Org 2",
        slug=f"org2-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)
    db.flush()

    pipeline = Pipeline(
        id=uuid.uuid4(),
        organization_id=org2.id,
        name="Org 2 Pipeline",
        is_default=True,
        current_version=1,
    )
    db.add(pipeline)
    db.flush()

    stage = PipelineStage(
        id=uuid.uuid4(),
        pipeline_id=pipeline.id,
        slug="new_unread",
        label="New Unread",
        color="#3B82F6",
        stage_type="intake",
        order=1,
        is_active=True,
        is_intake_stage=True,
    )
    db.add(stage)
    db.flush()

    email = f"org2-{uuid.uuid4().hex[:8]}@example.com"
    surrogate = Surrogate(
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        organization_id=org2.id,
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=uuid.uuid4(),
        full_name="Org 2 Surrogate",
        email=normalize_email(email),
        email_hash=hash_email(email),
    )
    db.add(surrogate)
    db.flush()

    return surrogate


def test_add_note_executor_scoped_to_org(db, test_org, test_user):
    surrogate = _seed_org2_surrogate(db)

    executor = AddNoteExecutor()
    result = executor.execute(
        {"content": "AI note"},
        db,
        test_user.id,
        test_org.id,
        surrogate.id,
    )

    assert result["success"] is False
    assert result["error"] == "Surrogate not found"
    assert (
        db.query(EntityNote)
        .filter(EntityNote.entity_id == surrogate.id)
        .count()
        == 0
    )


def test_create_task_executor_scoped_to_org(db, test_org, test_user):
    surrogate = _seed_org2_surrogate(db)

    executor = CreateTaskExecutor()
    result = executor.execute(
        {"title": "Follow up"},
        db,
        test_user.id,
        test_org.id,
        surrogate.id,
    )

    assert result["success"] is False
    assert result["error"] == "Surrogate not found"
    assert db.query(Task).filter(Task.surrogate_id == surrogate.id).count() == 0
