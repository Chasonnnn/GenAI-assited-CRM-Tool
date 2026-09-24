"""Authorization contracts without a database or delivery provider."""

from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.db.enums import Role
from app.routers import email_template_draft_tests, email_template_drafts, email_templates
from app.schemas.auth import UserSession
from app.schemas.email import EmailTemplateUpdate
from app.services import email_template_access


@pytest.fixture(autouse=True)
def legacy_policy(monkeypatch):
    from app.services import permission_policy_service

    monkeypatch.setattr(permission_policy_service, "is_enabled", lambda *_: False)


@pytest.fixture
def session():
    return UserSession(
        user_id=uuid4(),
        org_id=uuid4(),
        role=Role.INTAKE_SPECIALIST,
        email="staff@example.test",
        display_name="Staff",
    )


@pytest.mark.parametrize(
    "scope,role,is_owner,can_manage,allowed",
    [
        ("personal", Role.INTAKE_SPECIALIST, True, False, True),
        ("personal", Role.CASE_MANAGER, True, False, True),
        ("personal", Role.INTAKE_SPECIALIST, False, False, False),
        ("personal", Role.CASE_MANAGER, False, True, False),
        ("personal", Role.ADMIN, False, False, True),
        ("personal", Role.DEVELOPER, False, False, True),
        ("org", Role.INTAKE_SPECIALIST, True, False, False),
        ("org", Role.CASE_MANAGER, False, True, True),
        ("org", Role.ADMIN, False, False, False),
        ("org", Role.DEVELOPER, False, False, False),
        ("org", Role.ADMIN, False, True, True),
    ],
)
def test_template_edit_access_preserves_scope_owner_and_role_rules(
    monkeypatch, session, scope, role, is_owner, can_manage, allowed
):
    session.role = role
    db = object()
    check_permission = Mock(return_value=can_manage)
    monkeypatch.setattr(
        email_template_access.permission_service, "check_permission", check_permission
    )

    result = email_template_access.can_edit_template(
        db,
        session,
        scope=scope,
        owner_user_id=session.user_id if is_owner else uuid4(),
    )

    assert result is allowed
    if scope == "org":
        check_permission.assert_called_once_with(
            db, session.org_id, session.user_id, role.value, "manage_email_templates"
        )
    else:
        check_permission.assert_not_called()


def _call_template_endpoint(endpoint, *, template_id, db, session):
    if endpoint == "update":
        return email_templates.update_template(
            template_id, EmailTemplateUpdate(subject="Changed"), db, session
        )
    if endpoint == "delete":
        return email_templates.delete_template(template_id, db, session)
    return email_templates.get_template_versions(template_id, 50, db, session)


@pytest.mark.parametrize(
    "endpoint,scope,status_code,detail",
    [
        ("update", "personal", 403, "You can only edit your own personal templates"),
        ("delete", "personal", 403, "You can only delete your own personal templates"),
        ("versions", "personal", 404, "Template not found"),
        ("update", "org", 403, "You don't have permission to edit organization templates"),
        ("delete", "org", 403, "You don't have permission to delete organization templates"),
        ("versions", "org", 403, "Missing permission: manage_email_templates"),
    ],
)
def test_template_endpoints_keep_denial_contract(
    monkeypatch, session, endpoint, scope, status_code, detail
):
    db = object()
    template_id = uuid4()
    get_template = Mock(return_value=SimpleNamespace(scope=scope, owner_user_id=uuid4()))
    monkeypatch.setattr(email_templates.email_service, "get_template", get_template)
    check_permission = Mock(return_value=False)
    monkeypatch.setattr(
        email_template_access.permission_service, "check_permission", check_permission
    )

    with pytest.raises(HTTPException) as exc_info:
        _call_template_endpoint(endpoint, template_id=template_id, db=db, session=session)

    assert (exc_info.value.status_code, exc_info.value.detail) == (status_code, detail)
    get_template.assert_called_once_with(db, template_id, session.org_id)
    assert check_permission.call_count == (1 if scope == "org" else 0)


@pytest.mark.parametrize("endpoint", ["update", "delete", "versions"])
def test_missing_template_is_hidden_before_permission_lookup(monkeypatch, session, endpoint):
    monkeypatch.setattr(email_templates.email_service, "get_template", Mock(return_value=None))
    check_permission = Mock(
        side_effect=AssertionError("Missing templates must not load permissions")
    )
    monkeypatch.setattr(
        email_template_access.permission_service, "check_permission", check_permission
    )

    with pytest.raises(HTTPException) as exc_info:
        _call_template_endpoint(endpoint, template_id=uuid4(), db=object(), session=session)

    assert (exc_info.value.status_code, exc_info.value.detail) == (404, "Template not found")
    check_permission.assert_not_called()


@pytest.mark.parametrize(
    "scope,status_code,detail",
    [
        ("personal", 404, "Draft not found"),
        ("org", 403, "Missing permission: manage_email_templates"),
    ],
)
@pytest.mark.asyncio
async def test_draft_editor_and_test_send_keep_same_denial_contract(
    monkeypatch, session, scope, status_code, detail
):
    db = object()
    draft_id = uuid4()
    draft = SimpleNamespace(scope=scope, owner_user_id=uuid4())
    get_draft = Mock(return_value=draft)
    monkeypatch.setattr(
        email_template_draft_tests.email_template_draft_service, "get_draft", get_draft
    )
    check_permission = Mock(return_value=False)
    monkeypatch.setattr(
        email_template_access.permission_service, "check_permission", check_permission
    )

    with pytest.raises(HTTPException) as editor_error:
        email_template_drafts._require_draft_editor(db, session, draft)
    with pytest.raises(HTTPException) as send_error:
        await email_template_draft_tests.send_email_template_draft_test(
            draft_id, object(), db, session
        )

    for error in (editor_error.value, send_error.value):
        assert (error.status_code, error.detail) == (status_code, detail)
    get_draft.assert_called_once_with(db, org_id=session.org_id, draft_id=draft_id, for_update=True)
    assert check_permission.call_count == (2 if scope == "org" else 0)
