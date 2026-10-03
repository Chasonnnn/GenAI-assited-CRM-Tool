"""Submission tasks expose actionable dates and tenant-scoped form context."""

from uuid import uuid4

import pytest
from sqlalchemy import event

from app.db.models import Organization, Task, WorkflowExecution
from app.schemas.workflow import WorkflowCreate
from app.services import form_intake_service, form_routing_service, task_service, workflow_service
from tests.test_form_routing import routing_submission, tasks


@pytest.mark.asyncio
@pytest.mark.parametrize("step", ["match", "create_lead"])
async def test_review_task_reads_include_form_context_and_filterable_due_date(
    authed_client, db, test_org, test_user, step
):
    form, submission = routing_submission(
        db, test_org.id, test_user.id, exact="review" if step == "match" else "auto"
    )
    form_routing_service.route_submission(db, org_id=test_org.id, submission_id=submission.id)
    task = tasks(db, submission)[0]
    assert task.due_date == task.due_at.date()
    assert task.due_time == task.due_at.time()
    assert submission.routing_review_step == step

    detail = await authed_client.get(f"/tasks/{task.id}")
    listed = await authed_client.get(
        "/tasks",
        params={
            "task_type": "review",
            "due_after": task.due_date.isoformat(),
            "due_before": task.due_date.isoformat(),
        },
    )
    assert detail.status_code == 200, detail.text
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()["items"]] == [str(task.id)]
    for item in (detail.json(), listed.json()["items"][0]):
        assert item["form_submission_id"] == str(submission.id)
        assert item["form_id"] == str(form.id)
        assert item["form_name"] == form.name
        assert item["due_date"] == task.due_date.isoformat()
        assert item["due_time"] == task.due_time.isoformat()


@pytest.mark.asyncio
async def test_form_workflow_approval_reads_include_submission_context(
    authed_client, db, test_org, test_user
):
    form, submission = routing_submission(db, test_org.id, test_user.id)
    workflow = workflow_service.create_workflow(
        db,
        test_org.id,
        test_user.id,
        WorkflowCreate(
            name="Review staff notification",
            subject_type="form_submission",
            trigger_type="form_submitted",
            trigger_config={"form_id": str(form.id)},
            actions=[
                {
                    "action_type": "send_notification",
                    "title": "Application received",
                    "recipients": "creator",
                    "requires_approval": True,
                }
            ],
        ),
    )
    form_intake_service.process_form_submission_workflow(
        db, org_id=test_org.id, submission_id=submission.id
    )
    execution = db.query(WorkflowExecution).filter_by(workflow_id=workflow.id).one()
    assert execution.status == "paused"
    task = db.query(Task).filter_by(workflow_execution_id=execution.id).one()
    assert task.form_submission_id == submission.id

    listed = await authed_client.get("/tasks", params={"task_type": "workflow_approval"})
    detail = await authed_client.get(f"/tasks/{task.id}")
    resolved = await authed_client.post(f"/tasks/{task.id}/resolve", json={"decision": "approve"})
    for response in (listed, detail, resolved):
        assert response.status_code == 200, response.text
    assert [item["id"] for item in listed.json()["items"]] == [str(task.id)]
    for item in (listed.json()["items"][0], detail.json(), resolved.json()):
        assert item["form_submission_id"] == str(submission.id)
        assert item["form_id"] == str(form.id)
        assert item["form_name"] == form.name


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_link", ["foreign_task", "foreign_form"])
async def test_task_reads_never_expose_foreign_submission_or_form(
    authed_client, db, test_org, test_user, bad_link
):
    other = Organization(name="Private organization", slug=uuid4().hex)
    db.add(other)
    db.flush()
    foreign_form, foreign_submission = routing_submission(db, other.id, test_user.id)
    org_id, submission = other.id, foreign_submission
    if bad_link == "foreign_form":
        _, submission = routing_submission(db, test_org.id, test_user.id)
        # Legacy data can link a same-org submission to a foreign form through the simple FK.
        submission.form_id = foreign_form.id
        org_id = test_org.id
    task = Task(
        organization_id=org_id,
        form_submission_id=submission.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        task_type="review",
        title="Private review",
    )
    db.add(task)
    db.commit()

    listed = await authed_client.get("/tasks")
    detail = await authed_client.get(f"/tasks/{task.id}")
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    assert detail.status_code == 404, detail.text
    context = task_service.get_task_context(db, test_org.id, [task])
    assert context["submission_metadata"] == {}
    for serializer in (task_service.to_task_read, task_service.to_task_list_item):
        item = serializer(task, context)
        assert item.form_submission_id is None
        assert item.form_id is None
        assert item.form_name is None


def test_task_form_context_is_loaded_in_one_query(db, test_org, test_user):
    expected = {}
    task_rows = []
    for _ in range(3):
        form, submission = routing_submission(db, test_org.id, test_user.id)
        task = Task(
            organization_id=test_org.id,
            form_submission_id=submission.id,
            created_by_user_id=test_user.id,
            owner_type="user",
            owner_id=test_user.id,
            title="Review submission",
        )
        db.add(task)
        db.flush()
        expected[submission.id] = {
            "form_submission_id": submission.id,
            "form_id": form.id,
            "form_name": form.name,
        }
        task_rows.append(task)
    db.commit()
    # Load task rows before counting context lookups, including after commit expiration.
    task_rows = db.query(Task).filter_by(organization_id=test_org.id).all()
    queries = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "form_submissions" in statement:
            queries.append(statement)

    connection = db.connection()
    event.listen(connection, "before_cursor_execute", capture)
    try:
        context = task_service.get_task_context(db, test_org.id, task_rows)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert context["submission_metadata"] == expected
    assert len(queries) == 1


@pytest.mark.asyncio
async def test_unrelated_task_form_fields_are_null(authed_client, db, test_org, test_user):
    task = Task(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        owner_type="user",
        owner_id=test_user.id,
        title="General task",
    )
    db.add(task)
    db.commit()
    listed = await authed_client.get("/tasks")
    detail = await authed_client.get(f"/tasks/{task.id}")
    assert listed.status_code == 200, listed.text
    assert detail.status_code == 200, detail.text
    for item in (listed.json()["items"][0], detail.json()):
        assert item["form_submission_id"] is None
        assert item["form_id"] is None
        assert item["form_name"] is None
