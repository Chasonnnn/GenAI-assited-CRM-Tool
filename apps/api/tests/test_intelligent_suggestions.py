from datetime import datetime, timedelta, timezone
import uuid

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.encryption import hash_email
from app.db.enums import OwnerType, SurrogateSource
from app.db.models import Surrogate


def _ensure_intelligent_schema(db) -> None:
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS org_intelligent_suggestion_settings (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                new_unread_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                new_unread_business_days INTEGER NOT NULL DEFAULT 1,
                meeting_outcome_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                meeting_outcome_business_days INTEGER NOT NULL DEFAULT 1,
                stuck_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                stuck_business_days INTEGER NOT NULL DEFAULT 5,
                daily_digest_enabled BOOLEAN NOT NULL DEFAULT TRUE,
                digest_hour_local INTEGER NOT NULL DEFAULT 9,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS org_intelligent_suggestion_rules (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                template_key VARCHAR(100) NOT NULL,
                name VARCHAR(200) NOT NULL,
                rule_kind VARCHAR(50) NOT NULL CHECK (rule_kind IN ('stage_inactivity', 'meeting_outcome_missing')),
                stage_slug VARCHAR(100),
                business_days INTEGER NOT NULL DEFAULT 1 CHECK (business_days BETWEEN 1 AND 60),
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    )
    db.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_intel_rules_org_enabled
            ON org_intelligent_suggestion_rules (organization_id, enabled)
            """
        )
    )
    db.execute(
        text(
            """
            ALTER TABLE user_notification_settings
            ADD COLUMN IF NOT EXISTS intelligent_suggestion_digest BOOLEAN NOT NULL DEFAULT TRUE
            """
        )
    )
    db.commit()


@pytest.mark.asyncio
async def test_intelligent_suggestion_settings_defaults_and_update(authed_client, db):
    _ensure_intelligent_schema(db)
    get_response = await authed_client.get("/settings/intelligent-suggestions")
    assert get_response.status_code == 200, get_response.text
    get_payload = get_response.json()
    assert get_payload["enabled"] is True
    assert get_payload["new_unread_business_days"] == 1
    assert get_payload["meeting_outcome_business_days"] == 1
    assert get_payload["stuck_business_days"] == 5
    assert get_payload["digest_hour_local"] == 9

    patch_response = await authed_client.patch(
        "/settings/intelligent-suggestions",
        json={
            "new_unread_business_days": 2,
            "meeting_outcome_business_days": 3,
            "stuck_business_days": 7,
            "digest_hour_local": 11,
            "daily_digest_enabled": False,
        },
    )
    assert patch_response.status_code == 200, patch_response.text
    patched_payload = patch_response.json()
    assert patched_payload["new_unread_business_days"] == 2
    assert patched_payload["meeting_outcome_business_days"] == 3
    assert patched_payload["stuck_business_days"] == 7
    assert patched_payload["digest_hour_local"] == 11
    assert patched_payload["daily_digest_enabled"] is False


@pytest.mark.asyncio
async def test_intelligent_suggestion_templates_and_rule_crud(
    authed_client,
    db,
    default_stage,
):
    _ensure_intelligent_schema(db)

    templates_response = await authed_client.get("/settings/intelligent-suggestions/templates")
    assert templates_response.status_code == 200, templates_response.text
    templates = templates_response.json()
    template_keys = {template["template_key"] for template in templates}
    assert "stage_followup_custom" in template_keys
    assert "meeting_outcome_missing" in template_keys

    rules_response = await authed_client.get("/settings/intelligent-suggestions/rules")
    assert rules_response.status_code == 200, rules_response.text
    initial_rules = rules_response.json()
    assert len(initial_rules) >= 3

    create_response = await authed_client.post(
        "/settings/intelligent-suggestions/rules",
        json={
            "template_key": "stage_followup_custom",
            "name": "Custom stage check",
            "stage_slug": default_stage.slug,
            "business_days": 4,
            "enabled": True,
        },
    )
    assert create_response.status_code == 200, create_response.text
    created_rule = create_response.json()
    assert created_rule["template_key"] == "stage_followup_custom"
    assert created_rule["stage_slug"] == default_stage.slug
    assert created_rule["business_days"] == 4
    assert created_rule["enabled"] is True

    rule_id = created_rule["id"]
    update_response = await authed_client.patch(
        f"/settings/intelligent-suggestions/rules/{rule_id}",
        json={
            "name": "Custom stage check (updated)",
            "business_days": 6,
            "enabled": False,
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated_rule = update_response.json()
    assert updated_rule["name"] == "Custom stage check (updated)"
    assert updated_rule["business_days"] == 6
    assert updated_rule["enabled"] is False

    delete_response = await authed_client.delete(f"/settings/intelligent-suggestions/rules/{rule_id}")
    assert delete_response.status_code == 204, delete_response.text

    rules_after_delete = await authed_client.get("/settings/intelligent-suggestions/rules")
    assert rules_after_delete.status_code == 200, rules_after_delete.text
    remaining_ids = {rule["id"] for rule in rules_after_delete.json()}
    assert rule_id not in remaining_ids


@pytest.mark.asyncio
async def test_surrogates_dynamic_filter_new_unread_stale(
    authed_client,
    db,
    test_org,
    default_stage,
    test_user,
):
    _ensure_intelligent_schema(db)
    now = datetime.now(timezone.utc)

    stale = Surrogate(
        id=uuid.uuid4(),
        surrogate_number="S91001",
        organization_id=test_org.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        source=SurrogateSource.MANUAL.value,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        full_name="Stale Suggestion",
        email="stale-intel@example.com",
        email_hash=hash_email("stale-intel@example.com"),
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=10),
    )
    fresh = Surrogate(
        id=uuid.uuid4(),
        surrogate_number="S91002",
        organization_id=test_org.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        source=SurrogateSource.MANUAL.value,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        full_name="Fresh Suggestion",
        email="fresh-intel@example.com",
        email_hash=hash_email("fresh-intel@example.com"),
        created_at=now,
        updated_at=now,
    )
    db.add_all([stale, fresh])
    db.flush()

    response = await authed_client.get(
        "/surrogates",
        params={"dynamic_filter": "intelligent_new_unread_stale"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    ids = {item["id"] for item in data["items"]}
    assert str(stale.id) in ids
    assert str(fresh.id) not in ids


@pytest.mark.asyncio
async def test_surrogates_dynamic_filter_invalid(authed_client):
    response = await authed_client.get(
        "/surrogates",
        params={"dynamic_filter": "does_not_exist"},
    )
    assert response.status_code == 400
    assert "Invalid dynamic_filter" in response.json()["detail"]


@pytest.mark.asyncio
async def test_intelligent_suggestions_summary_endpoint(
    authed_client,
    db,
    test_org,
    default_stage,
    test_user,
):
    _ensure_intelligent_schema(db)
    now = datetime.now(timezone.utc)
    stale = Surrogate(
        id=uuid.uuid4(),
        surrogate_number="S91003",
        organization_id=test_org.id,
        stage_id=default_stage.id,
        status_label=default_stage.label,
        source=SurrogateSource.MANUAL.value,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        full_name="Summary Stale",
        email="summary-intel@example.com",
        email_hash=hash_email("summary-intel@example.com"),
        created_at=now - timedelta(days=10),
        updated_at=now - timedelta(days=10),
    )
    db.add(stale)
    db.flush()

    response = await authed_client.get("/surrogates/intelligent-suggestions/summary")
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["has_suggestions"] is True
    assert payload["total"] >= 1
    assert payload["counts"]["intelligent_new_unread_stale"] >= 1


@pytest.mark.asyncio
async def test_internal_scheduled_intelligent_suggestions(monkeypatch, client):
    from app.routers import internal as internal_router
    monkeypatch.setattr(settings, "INTERNAL_SECRET", "internal-secret-test")

    monkeypatch.setattr(
        internal_router.intelligent_suggestions_service,
        "process_daily_digest_for_all_orgs",
        lambda _db: {
            "orgs_processed": 2,
            "users_checked": 5,
            "notifications_created": 3,
            "errors": [],
        },
    )

    response = await client.post(
        "/internal/scheduled/intelligent-suggestions",
        headers={"x-internal-secret": "internal-secret-test"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["orgs_processed"] == 2
    assert payload["users_checked"] == 5
    assert payload["notifications_created"] == 3
