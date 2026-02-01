from datetime import datetime, timedelta, timezone

import pytest


@pytest.mark.asyncio
async def test_platform_delete_org_schedules_purge(authed_client, db, test_user, test_org):
    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.post(f"/platform/orgs/{test_org.id}/delete")
    assert res.status_code == 200
    data = res.json()
    assert data["deleted_at"] is not None
    assert data["purge_at"] is not None

    deleted_at = datetime.fromisoformat(data["deleted_at"])
    purge_at = datetime.fromisoformat(data["purge_at"])
    assert purge_at - deleted_at >= timedelta(days=29)

    from app.db.models import Job
    from app.db.enums import JobType

    job = (
        db.query(Job)
        .filter(Job.organization_id == test_org.id, Job.job_type == JobType.ORG_DELETE.value)
        .first()
    )
    assert job is not None


@pytest.mark.asyncio
async def test_platform_restore_org_clears_deleted_at(authed_client, db, test_user, test_org):
    from app.services import platform_service

    test_user.is_platform_admin = True
    db.commit()

    platform_service.request_organization_deletion(db, test_org.id, test_user.id)

    res = await authed_client.post(f"/platform/orgs/{test_org.id}/restore")
    assert res.status_code == 200
    data = res.json()
    assert data["deleted_at"] is None
    assert data["purge_at"] is None


@pytest.mark.asyncio
async def test_org_access_blocked_when_deleted(authed_client, db, test_org):
    test_org.deleted_at = datetime.now(timezone.utc)
    test_org.purge_at = test_org.deleted_at + timedelta(days=30)
    db.commit()

    res = await authed_client.get("/settings/organization")
    assert res.status_code == 403
    assert "deletion" in res.json()["detail"].lower()


def test_purge_organization_hard_deletes(db, test_org):
    from app.services import platform_service
    from app.db.models import Organization

    now = datetime.now(timezone.utc)
    test_org.deleted_at = now - timedelta(days=31)
    test_org.purge_at = now - timedelta(days=1)
    db.commit()

    assert platform_service.purge_organization(db, test_org.id) is True
    assert db.query(Organization).filter(Organization.id == test_org.id).first() is None


@pytest.mark.asyncio
async def test_platform_force_delete_org_immediate(authed_client, db, test_user, test_org):
    from app.db.models import Organization

    test_user.is_platform_admin = True
    db.commit()

    res = await authed_client.post(f"/platform/orgs/{test_org.id}/purge")
    assert res.status_code == 200
    data = res.json()
    assert data["org_id"] == str(test_org.id)
    assert data["deleted"] is True
    assert db.query(Organization).filter(Organization.id == test_org.id).first() is None
