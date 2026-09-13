from contextlib import contextmanager
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.core.encryption import encrypt_token
from app.db.enums import AuditEventType
from app.db.models import (
    AuditLog,
    MetaAdAccount,
    MetaOAuthConnection,
    MetaPageMapping,
    Organization,
)
from app.services import meta_oauth_service
from app.services.meta_oauth_service import PaginatedResult


def connection(db, org_id, user_id, name):
    row = MetaOAuthConnection(
        organization_id=org_id,
        meta_user_id=uuid4().hex,
        meta_user_name=name,
        access_token_encrypted=encrypt_token("synthetic-token"),
        granted_scopes=[],
        connected_by_user_id=user_id,
        is_active=True,
    )
    db.add(row)
    db.flush()
    return row


def test_bulk_owner_lookup_cannot_read_connection_from_other_org(db, test_auth):
    other = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    own = connection(db, test_auth.org.id, test_auth.user.id, "Own")
    foreign = connection(db, other.id, test_auth.user.id, "Foreign")
    assert meta_oauth_service.get_oauth_connections_by_ids(
        db, test_auth.org.id, {own.id, foreign.id}
    ) == {own.id: own}
    with asset_selects(db) as statements:
        assert meta_oauth_service.get_oauth_connections_by_ids(db, test_auth.org.id, set()) == {}
    assert statements == []


@contextmanager
def asset_selects(db):
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.startswith("SELECT") and any(
            f"FROM {table}" in statement
            for table in ("meta_ad_accounts", "meta_page_mappings", "meta_oauth_connections")
        ):
            statements.append(statement)

    event.listen(db.get_bind(), "before_cursor_execute", capture)
    try:
        yield statements
    finally:
        event.remove(db.get_bind(), "before_cursor_execute", capture)


@pytest.mark.asyncio
async def test_available_assets_batches_owner_names_and_excludes_other_org(
    authed_client,
    db,
    test_auth,
    monkeypatch,
):
    current = connection(db, test_auth.org.id, test_auth.user.id, "Current")
    accounts = []
    for index in range(4):
        owner = connection(db, test_auth.org.id, test_auth.user.id, f"Owner {index}")
        accounts.append({"id": f"act_{index}", "name": f"Account {index}"})
        db.add(
            MetaAdAccount(
                organization_id=test_auth.org.id,
                ad_account_external_id=f"act_{index}",
                oauth_connection_id=owner.id,
            )
        )
    other = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    foreign = connection(db, other.id, test_auth.user.id, "Foreign owner")
    db.add(
        MetaAdAccount(
            organization_id=other.id,
            ad_account_external_id="foreign",
            oauth_connection_id=foreign.id,
        )
    )
    accounts.append({"id": "foreign", "name": "Unconnected here"})
    db.flush()
    current_id = current.id
    db.expire_all()

    async def fetch_accounts(*_args):
        return PaginatedResult(data=accounts, next_cursor=None)

    async def fetch_pages(*_args):
        return PaginatedResult(data=[], next_cursor=None)

    monkeypatch.setattr(meta_oauth_service, "fetch_user_ad_accounts", fetch_accounts)
    monkeypatch.setattr(meta_oauth_service, "fetch_user_pages", fetch_pages)
    with asset_selects(db) as statements:
        response = await authed_client.get(
            f"/integrations/meta/connections/{current_id}/available-assets"
        )
    assert response.status_code == 200
    result = response.json()["ad_accounts"]
    assert [item["connected_by_meta_user"] for item in result] == [
        "Owner 0",
        "Owner 1",
        "Owner 2",
        "Owner 3",
        None,
    ]
    assert result[-1]["is_connected"] is False
    assert len(statements) == 4


@pytest.mark.asyncio
async def test_connect_assets_deduplicates_and_audits_once_per_request(
    authed_client,
    db,
    test_auth,
    monkeypatch,
):
    current = connection(db, test_auth.org.id, test_auth.user.id, "Current")
    current_id = current.id
    subscribed = []

    async def pages(*_args):
        return PaginatedResult(
            data=[{"id": "page", "access_token": "synthetic-page-token"}], next_cursor=None
        )

    async def subscribe(_token, page_id):
        subscribed.append(page_id)
        return True

    monkeypatch.setattr(meta_oauth_service, "fetch_user_pages", pages)
    monkeypatch.setattr(meta_oauth_service, "subscribe_page_to_leadgen", subscribe)
    payload = {"ad_account_ids": ["act", "act"], "page_ids": ["page", "page"]}
    for _ in range(2):
        response = await authed_client.post(
            f"/integrations/meta/connections/{current_id}/connect-assets",
            json=payload,
        )
        assert response.status_code == 200
        assert response.json() == {"ad_accounts": ["act"], "pages": ["page"], "overwrites": []}
    assert subscribed == ["page", "page"]
    assert db.query(MetaAdAccount).filter_by(organization_id=test_auth.org.id).count() == 1
    assert db.query(MetaPageMapping).filter_by(organization_id=test_auth.org.id).count() == 1
    audits = (
        db.query(AuditLog)
        .filter_by(
            organization_id=test_auth.org.id,
            event_type=AuditEventType.META_ASSETS_CONNECTED.value,
        )
        .all()
    )
    assert len(audits) == 2
    assert all(audit.details["ad_accounts"] == ["act"] for audit in audits)


@pytest.mark.asyncio
async def test_connect_assets_conflict_does_not_commit_earlier_accounts_or_subscribe(
    authed_client,
    db,
    test_auth,
    monkeypatch,
):
    current = connection(db, test_auth.org.id, test_auth.user.id, "Current")
    owner = connection(db, test_auth.org.id, test_auth.user.id, "Owner")
    db.add(
        MetaPageMapping(
            organization_id=test_auth.org.id,
            page_id="occupied",
            oauth_connection_id=owner.id,
        )
    )
    db.commit()
    current_id, org_id = current.id, test_auth.org.id
    subscribed = []

    async def pages(*_args):
        return PaginatedResult(
            data=[{"id": "occupied", "access_token": "synthetic"}], next_cursor=None
        )

    async def subscribe(*_args):
        subscribed.append(True)
        return True

    monkeypatch.setattr(meta_oauth_service, "fetch_user_pages", pages)
    monkeypatch.setattr(meta_oauth_service, "subscribe_page_to_leadgen", subscribe)
    response = await authed_client.post(
        f"/integrations/meta/connections/{current_id}/connect-assets",
        json={"ad_account_ids": ["new"], "page_ids": ["occupied"]},
    )
    assert response.status_code == 409
    db.rollback()
    assert db.query(MetaAdAccount).filter_by(organization_id=org_id).count() == 0
    assert subscribed == []


@pytest.mark.asyncio
async def test_connect_assets_rejects_foreign_connection_and_missing_csrf(
    authed_client,
    db,
    test_auth,
):
    from app.core.csrf import CSRF_HEADER

    other = Organization(name="Other", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    foreign = connection(db, other.id, test_auth.user.id, "Foreign")
    response = await authed_client.post(
        f"/integrations/meta/connections/{foreign.id}/connect-assets",
        json={"ad_account_ids": ["new"]},
    )
    assert response.status_code == 404
    del authed_client.headers[CSRF_HEADER]
    response = await authed_client.post(
        f"/integrations/meta/connections/{foreign.id}/connect-assets",
        json={"ad_account_ids": ["new"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_connect_assets_audit_failure_rolls_back_new_accounts(
    authed_client,
    db,
    test_auth,
    monkeypatch,
):
    from app.services import audit_service

    current = connection(db, test_auth.org.id, test_auth.user.id, "Current")
    db.commit()
    current_id, org_id = current.id, test_auth.org.id

    def failed_audit(**_kwargs):
        db.flush()
        raise RuntimeError("Synthetic audit failure")

    monkeypatch.setattr(audit_service, "log_event", failed_audit)
    with pytest.raises(RuntimeError, match="Synthetic audit failure"):
        await authed_client.post(
            f"/integrations/meta/connections/{current_id}/connect-assets",
            json={"ad_account_ids": ["first", "second"]},
        )
    db.rollback()
    assert db.query(MetaAdAccount).filter_by(organization_id=org_id).count() == 0
