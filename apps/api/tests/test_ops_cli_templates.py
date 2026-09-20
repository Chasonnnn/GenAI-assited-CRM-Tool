"""Publication must be a revision-fenced, atomic library-only operation."""

import pytest

from app.services import platform_template_write_service as writes

EMAIL = {"name": "Welcome", "subject": "Hello", "body": "<p>Welcome</p>"}


def test_workflow_ui_ids_are_not_tenant_bindings():
    from uuid import uuid4

    draft = {
        "name": "Imported studio draft",
        "trigger_type": "surrogate_created",
        "actions": [{"action_type": "add_note", "content": "Review", "clientId": str(uuid4())}],
        "conditions": [
            {"field": "age", "operator": "greater_than", "value": 23, "clientId": str(uuid4())}
        ],
    }
    checked = writes.validate_template("workflow", draft)
    assert checked["draft"]["actions"] == [{"action_type": "add_note", "content": "Review"}]
    assert "clientId" not in checked["draft"]["conditions"][0]
    draft["actions"] = [{"action_type": "send_email", "template_id": str(uuid4())}]
    with pytest.raises(writes.TemplateInputError, match="tenant identifiers"):
        writes.validate_template("workflow", draft)


def apply(db, user, **kwargs):
    return writes.apply_template(
        db, "email", actor_id=user.id, key="welcome", draft=EMAIL, **kwargs
    )


def test_publish_retry_and_stale_draft(db, test_user):
    template, result = apply(
        db, test_user, mode="publish", audience={"publish_all": True, "org_ids": []}
    )
    assert result == "published"
    revision, published_at = template.current_version, template.published_at
    repeated, result = apply(
        db, test_user, mode="publish", audience={"publish_all": True, "org_ids": []}
    )
    assert result == "unchanged"
    assert repeated.current_version == revision
    assert repeated.published_version == 1
    assert repeated.published_at == published_at
    writes.apply_template(
        db,
        "email",
        actor_id=test_user.id,
        key="welcome",
        draft={**EMAIL, "subject": "A different draft"},
        expected_revision=revision,
    )
    with pytest.raises(writes.TemplateConflict):
        apply(
            db,
            test_user,
            expected_revision=revision,
            mode="publish",
            audience={"publish_all": True, "org_ids": []},
        )
    db.refresh(template)
    assert template.subject == "A different draft"
    assert template.published_subject == "Hello"


def test_audit_failure_rolls_back_template(db, test_user, monkeypatch):
    from app.services import platform_service

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(platform_service, "log_admin_action", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        apply(db, test_user)
    assert writes.find_template(db, "email", key="welcome") is None


def test_target_change_requires_explicit_intent(db, test_user, test_org):
    template, _ = apply(
        db, test_user, mode="publish", audience={"publish_all": True, "org_ids": []}
    )
    revision = template.current_version
    with pytest.raises(ValueError, match="replace_audience"):
        apply(
            db,
            test_user,
            expected_revision=revision,
            mode="publish",
            audience={"publish_all": False, "org_ids": [str(test_org.id)]},
        )
    db.refresh(template)
    assert template.current_version == revision
    assert template.is_published_globally


def test_workflow_drafts_use_edit_revision_and_clear_null(db, test_user):
    draft = {
        "name": "Follow up",
        "description": "Old",
        "trigger_type": "surrogate_created",
        "actions": [{"action_type": "create_task", "title": "Review", "due_days": 3}],
    }
    template, _ = writes.apply_template(
        db, "workflow", actor_id=test_user.id, key="follow-up", draft=draft
    )
    revision = template.current_version
    writes.apply_template(
        db,
        "workflow",
        actor_id=test_user.id,
        key="follow-up",
        draft={**draft, "description": None},
        expected_revision=revision,
    )
    assert template.current_version == revision + 1
    assert template.draft_config["description"] is None
    with pytest.raises(writes.TemplateConflict):
        writes.apply_template(
            db,
            "workflow",
            actor_id=test_user.id,
            key="follow-up",
            draft=draft,
            expected_revision=revision,
        )


@pytest.mark.parametrize("kind", ["email", "form", "workflow"])
def test_concurrent_updates_have_one_winner(db_engine, kind):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from uuid import uuid4

    from sqlalchemy.orm import Session

    from app.db.models import AdminActionLog, User

    key = f"race-{uuid4()}"
    draft = {
        "email": EMAIL,
        "form": {"name": "Form"},
        "workflow": {"name": "Workflow", "trigger_type": "surrogate_created"},
    }[kind]
    # Separate committed setup makes both independent connections see the same base.
    with Session(db_engine) as setup:
        user = User(email=f"{key}@example.test", display_name="Race test")
        setup.add(user)
        setup.commit()
        user_id = user.id
        template, _ = writes.apply_template(
            setup, kind, key=key, actor_id=user_id, draft=draft, portable=False
        )
        revision = template.current_version
    barrier = Barrier(2)

    def edit(name):
        with Session(db_engine) as session:
            # Both read before the competing writes, exercising stale identity maps too.
            writes.find_template(session, kind, key=key)
            barrier.wait(timeout=10)
            try:
                writes.apply_template(
                    session,
                    kind,
                    key=key,
                    actor_id=user_id,
                    draft={**draft, "name": name},
                    expected_revision=revision,
                    portable=False,
                )
                return "updated"
            except writes.TemplateConflict:
                return "conflict"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(edit, ["First competing edit", "Second competing edit"]))
        assert sorted(results) == ["conflict", "updated"]
        with Session(db_engine) as check:
            template = writes.find_template(check, kind, key=key)
            assert template.current_version == revision + 1
            assert (
                check.query(AdminActionLog).filter(AdminActionLog.actor_user_id == user_id).count()
                == 2
            )
    finally:
        with Session(db_engine) as cleanup:
            cleanup.query(writes.MODELS[kind]).filter_by(external_key=key).delete()
            cleanup.query(AdminActionLog).filter_by(actor_user_id=user_id).delete()
            cleanup.query(User).filter_by(id=user_id).delete()
            cleanup.commit()
