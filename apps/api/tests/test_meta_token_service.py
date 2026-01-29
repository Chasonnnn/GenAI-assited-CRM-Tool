"""Tests for Meta token resolution."""


def test_get_token_for_ad_account_requires_oauth(db, test_org):
    from app.db.models import MetaAdAccount
    from app.services import meta_token_service

    account = MetaAdAccount(
        organization_id=test_org.id,
        ad_account_external_id="act_123",
        ad_account_name="Account",
        is_active=True,
    )
    db.add(account)
    db.commit()

    result = meta_token_service.get_token_for_ad_account(db, account)
    assert result.token is None
    assert result.needs_reauth is True


def test_get_token_for_page_uses_page_token(db, test_org, test_user):
    from app.core.encryption import encrypt_token
    from app.db.models import MetaOAuthConnection, MetaPageMapping
    from app.services import meta_token_service

    connection = MetaOAuthConnection(
        organization_id=test_org.id,
        meta_user_id="meta-user-1",
        meta_user_name="Meta User",
        access_token_encrypted=encrypt_token("conn-token"),
        token_expires_at=None,
        granted_scopes=["ads_read"],
        connected_by_user_id=test_user.id,
        is_active=True,
    )
    db.add(connection)
    db.flush()

    page = MetaPageMapping(
        organization_id=test_org.id,
        page_id="page_1",
        page_name="Page One",
        oauth_connection_id=connection.id,
        access_token_encrypted=encrypt_token("page-token"),
        is_active=True,
    )
    db.add(page)
    db.commit()

    result = meta_token_service.get_token_for_page(db, page)
    assert result.token == "page-token"
    assert result.needs_reauth is False
