"""Archive, restore, delete, and bulk assignment retain record-scope boundaries."""

from uuid import uuid4

import pytest

from app.db.enums import Role
from app.db.models import (
    Organization,
    OrganizationPermissionPolicy,
    RolePermission,
    RoleRecordScope,
    Surrogate,
    User,
    UserPermissionOverride,
)
from tests.test_email_templates_personal_scope import authed_client_for_user
from tests.test_record_scopes_v2 import _member, _record
from tests.test_record_scopes_v2 import context as context


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["archive", "restore", "delete", "bulk_assign"])
@pytest.mark.parametrize("access", ["allowed", "outside_scope", "other_org", "no_view"])
async def test_surrogate_write_requires_action_and_record_scope(db, context, operation, access):
    db.add(
        RoleRecordScope(
            organization_id=context.org.id,
            role="case_manager",
            module="surrogates",
            assignment="assigned",
            phase="all",
            stage_ids=[],
        )
    )
    db.add(
        UserPermissionOverride(
            organization_id=context.org.id,
            user_id=context.manager.user_id,
            permission="delete_surrogates",
            override_type="grant",
        )
    )
    owner = context.manager
    if access == "outside_scope":
        owner = context.intake
    elif access == "other_org":
        other = Organization(id=uuid4(), name="Other agency", slug=uuid4().hex)
        db.add(other)
        db.flush()
        owner, _ = _member(db, other.id, "admin")
    elif access == "no_view":
        db.add(
            RolePermission(
                organization_id=context.org.id,
                role="case_manager",
                permission="view_surrogates",
                is_granted=False,
            )
        )
    record = _record(
        db,
        owner,
        "surrogate",
        key="approved",
        archived=operation in {"restore", "delete"},
    )
    record_id, was_archived, previous_owner_id = record.id, record.is_archived, record.owner_id
    db.flush()
    user = db.get(User, context.manager.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        headers = {"X-CSRF-Token": client.cookies.get("crm_csrf")}
        if operation == "bulk_assign":
            response = await client.post(
                "/surrogates/bulk-assign",
                headers=headers,
                json={
                    "surrogate_ids": [str(record_id)],
                    "owner_type": "user",
                    "owner_id": str(context.intake.user_id),
                },
            )
            assert response.status_code == (403 if access == "no_view" else 200), response.text
            if access != "no_view":
                assert response.json()["assigned"] == (1 if access == "allowed" else 0)
                assert len(response.json()["failed"]) == (0 if access == "allowed" else 1)
        else:
            path = f"/surrogates/{record_id}" + (f"/{operation}" if operation != "delete" else "")
            response = await client.request(
                "DELETE" if operation == "delete" else "POST", path, headers=headers
            )
            expected = (
                (204 if operation == "delete" else 200)
                if access == "allowed"
                else (404 if access == "other_org" else 403)
            )
            assert response.status_code == expected, response.text
            if access == "allowed" and operation in {"archive", "restore"}:
                assert (await client.post(path, headers=headers)).status_code == 200
    if access != "allowed":
        db.refresh(record)
        assert record.is_archived == was_archived
        assert record.owner_id == previous_owner_id
    elif operation == "delete":
        assert db.query(Surrogate.id).filter_by(id=record_id).first() is None
    elif operation == "bulk_assign":
        assert record.owner_id == context.intake.user_id
    else:
        assert record.is_archived == (operation == "archive")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["archive", "restore"])
@pytest.mark.parametrize("denial", ["action", "csrf"])
async def test_archive_restore_keep_action_and_csrf_requirements(db, context, operation, denial):
    record = _record(
        db, context.manager, "surrogate", key="approved", archived=operation == "restore"
    )
    if denial == "action":
        db.add(
            RolePermission(
                organization_id=context.org.id,
                role="case_manager",
                permission="archive_surrogates",
                is_granted=False,
            )
        )
        db.flush()
    user = db.get(User, context.manager.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        if denial == "csrf":
            client.headers.pop("X-CSRF-Token", None)
        headers = {"X-CSRF-Token": client.cookies.get("crm_csrf")} if denial == "action" else {}
        response = await client.post(f"/surrogates/{record.id}/{operation}", headers=headers)
    assert response.status_code == 403, response.text
    assert record.is_archived == (operation == "restore")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["archive", "restore"])
async def test_legacy_archive_restore_keep_existing_scope_behavior(db, context, operation):
    db.query(OrganizationPermissionPolicy).filter_by(organization_id=context.org.id).delete()
    record = _record(db, context.intake, "surrogate", archived=operation == "restore")
    user = db.get(User, context.manager.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.CASE_MANAGER) as client:
        response = await client.post(
            f"/surrogates/{record.id}/{operation}",
            headers={
                "X-CSRF-Token": client.cookies.get("crm_csrf"),
            },
        )
    assert response.status_code == 200, response.text
