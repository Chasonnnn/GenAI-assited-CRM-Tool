import uuid

import pytest
from httpx import AsyncClient, ASGITransport

from app.core.deps import COOKIE_NAME, get_db
from app.core.csrf import CSRF_COOKIE_NAME, CSRF_HEADER, generate_csrf_token
from app.core.permissions import PERMISSION_REGISTRY, PermissionKey as P
from app.core.policies import POLICIES
from app.core.security import create_session_token
from app.db.enums import Role
from app.db.models import Membership, User, UserPermissionOverride
from app.main import app


async def _client_with_revoked_permission(db, test_org, permission: P) -> AsyncClient:
    user = User(
        id=uuid.uuid4(),
        email=f"rbac-{uuid.uuid4().hex[:8]}@test.com",
        display_name="RBAC Test User",
        token_version=1,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = Membership(
        id=uuid.uuid4(),
        user_id=user.id,
        organization_id=test_org.id,
        role=Role.ADMIN.value,
    )
    db.add(membership)

    override = UserPermissionOverride(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        user_id=user.id,
        permission=permission.value,
        override_type="revoke",
    )
    db.add(override)
    db.commit()

    token = create_session_token(
        user_id=user.id,
        org_id=test_org.id,
        role=Role.ADMIN.value,
        token_version=user.token_version,
        mfa_verified=True,
        mfa_required=True,
    )
    from app.services import session_service

    session_service.create_session(
        db=db,
        user_id=user.id,
        org_id=test_org.id,
        token=token,
        request=None,
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    csrf_token = generate_csrf_token()
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies={COOKIE_NAME: token, CSRF_COOKIE_NAME: csrf_token},
        headers={CSRF_HEADER: csrf_token},
    )


@pytest.mark.asyncio
async def test_policies_reference_known_permissions():
    policy_keys: set[str] = set()
    for policy in POLICIES.values():
        if policy.default:
            policy_keys.add(policy.default.value)
        policy_keys.update(p.value for p in policy.actions.values())

    missing = policy_keys - set(PERMISSION_REGISTRY.keys())
    assert not missing, f"Policy permissions missing from registry: {sorted(missing)}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,path,permission",
    [
        ("GET", "/surrogates", P.SURROGATES_VIEW),
        ("GET", "/intended-parents", P.INTENDED_PARENTS_VIEW),
        ("GET", "/matches/", P.MATCHES_VIEW),
        ("GET", "/tasks", P.TASKS_VIEW),
        ("GET", "/analytics/summary", P.REPORTS_VIEW),
        ("GET", "/email-templates", P.EMAIL_TEMPLATES_VIEW),
        ("GET", "/templates", P.AUTOMATION_MANAGE),
        # /workflows is accessible to all users - permissions filter what's visible
        ("GET", "/settings/pipelines", P.PIPELINES_MANAGE),
        ("GET", "/queues", P.SURROGATES_ASSIGN),
        ("GET", "/settings/invites", P.TEAM_MANAGE),
        ("GET", "/settings/permissions/available", P.TEAM_MANAGE),
        ("GET", "/admin/meta-pages", P.META_LEADS_MANAGE),
        ("GET", "/ops/health", P.OPS_MANAGE),
        ("GET", "/jobs", P.JOBS_MANAGE),
        ("GET", "/audit/", P.AUDIT_VIEW),
        ("GET", "/surrogates/import", P.SURROGATES_IMPORT),
    ],
)
async def test_permission_guard_blocks_revoked(
    db,
    test_org,
    method: str,
    path: str,
    permission: P,
):
    client = await _client_with_revoked_permission(db, test_org, permission)
    async with client:
        response = await client.request(method, path)
    app.dependency_overrides.clear()
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_effective_permissions_me_does_not_require_team_manage(
    db,
    test_org,
):
    client = await _client_with_revoked_permission(db, test_org, P.TEAM_MANAGE)
    async with client:
        response = await client.get("/settings/permissions/effective/me")
    app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"]
    assert payload["role"] == Role.ADMIN.value
    assert isinstance(payload["permissions"], list)
