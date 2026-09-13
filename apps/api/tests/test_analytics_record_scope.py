"""Analytics aggregates use the same visible records as operational pages."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from app.db.models import AnalyticsSnapshot, Donor, Surrogate, UserRecordScopeAddition
from app.schemas.record_scope import RecordScopeAdditionCreate
from app.services import analytics_access_service as access
from app.services import analytics_service, record_scope_service
from tests.test_record_scopes_v2 import _member, _record
from tests.test_record_scopes_v2 import context as context


@pytest.mark.parametrize("kind,model", [("surrogate", Surrogate), ("donor", Donor)])
def test_dataset_filters_aggregates_aliases_and_restores_session(db, context, kind, model):
    mine = _record(db, context.intake, kind, suffix=1)
    _record(db, context.manager, kind, suffix=2)
    _record(db, context.intake, kind, key="approved", suffix=3)
    with access.authorized_dataset(db, context.intake):
        assert db.query(func.count(model.id)).scalar() == 1
        alias = aliased(model)
        assert db.scalars(select(alias.id)).all() == [mine.id]
    assert db.query(func.count(model.id)).scalar() == 3
    assert access.REQUEST_CACHE_KEY not in db.info


def test_cached_reports_follow_viewer_and_revocation(db, context):
    _record(db, context.intake, "surrogate", suffix=1)
    _record(db, context.manager, "surrogate", suffix=2)
    _record(db, context.intake, "surrogate", key="approved", suffix=3)
    start, end = datetime.now(UTC) - timedelta(days=1), datetime.now(UTC) + timedelta(days=1)
    for session, expected in [(context.admin, 3), (context.intake, 1), (context.manager, 1)]:
        with access.authorized_dataset(db, session):
            for _ in range(2):
                assert (
                    analytics_service.get_cached_analytics_summary(db, context.org.id, start, end)[
                        "total_surrogates"
                    ]
                    == expected
                )
    assert db.query(AnalyticsSnapshot).filter_by(organization_id=context.org.id).count() == 0
    addition = record_scope_service.add_scope_addition(
        db,
        context.admin,
        context.intake.user_id,
        RecordScopeAdditionCreate(module="surrogates", assignment="all", phase="all"),
    )
    with access.authorized_dataset(db, context.intake):
        assert (
            analytics_service.get_cached_analytics_summary(db, context.org.id, start, end)[
                "total_surrogates"
            ]
            == 3
        )
    db.query(UserRecordScopeAddition).filter_by(id=addition.id).delete()
    db.flush()
    with access.authorized_dataset(db, context.intake):
        assert (
            analytics_service.get_cached_analytics_summary(db, context.org.id, start, end)[
                "total_surrogates"
            ]
            == 1
        )


def test_exception_removes_dataset_listener(db, context):
    _record(db, context.manager, "surrogate")
    with pytest.raises(RuntimeError), access.authorized_dataset(db, context.intake):
        assert db.query(Surrogate).count() == 0
        raise RuntimeError("cancel report")
    assert db.query(Surrogate).count() == 1


def test_reports_never_include_another_organization(db, context):
    from uuid import uuid4

    from app.db.models import Organization

    other = Organization(id=uuid4(), name="Other agency", slug=f"other-{uuid4().hex}")
    db.add(other)
    db.flush()
    outsider, _ = _member(db, other.id, "admin")
    mine = _record(db, context.admin, "surrogate")
    _record(db, outsider, "surrogate")
    with access.authorized_dataset(db, context.admin):
        assert db.scalars(select(Surrogate.id)).all() == [mine.id]


@pytest.mark.asyncio
async def test_reports_http_respects_added_report_action_and_record_scope(db, context):
    from app.db.enums import Role
    from app.db.models import User, UserPermissionOverride
    from tests.test_email_templates_personal_scope import authed_client_for_user

    user = db.get(User, context.intake.user_id)
    _record(db, context.intake, "surrogate")
    _record(db, context.manager, "surrogate", suffix=2)
    async with authed_client_for_user(db, context.org.id, user, Role.INTAKE_SPECIALIST) as client:
        denied = await client.get("/analytics/summary")
        assert denied.status_code == 403
        db.add(
            UserPermissionOverride(
                organization_id=context.org.id,
                user_id=user.id,
                permission="view_reports",
                override_type="grant",
            )
        )
        db.flush()
        summary = await client.get("/analytics/summary")
        assert summary.status_code == 200, summary.text
        assert summary.json()["total_surrogates"] == 1
        other_owner = await client.get(
            f"/analytics/surrogates/by-status?owner_id={context.manager.user_id}"
        )
        assert other_owner.status_code == 200, other_owner.text
        assert sum(item["count"] for item in other_owner.json()) == 0
        spend = await client.get("/analytics/meta/spend/totals")
        assert spend.status_code == 403


def test_unlinked_meta_leads_require_their_module_and_intake_queue_role(db, context):
    from uuid import uuid4

    from app.db.models import MetaLead, RolePermission

    leads = {}
    for kind in (None, "surrogate", "egg_donor", "sperm_donor"):
        lead = MetaLead(organization_id=context.org.id, meta_lead_id=uuid4().hex, lead_kind=kind)
        db.add(lead)
        db.flush()
        leads[kind] = lead.id
    db.add(
        RolePermission(
            organization_id=context.org.id,
            role="intake_specialist",
            permission="view_donors",
            is_granted=False,
        )
    )
    db.flush()
    with access.authorized_dataset(db, context.intake):
        assert db.scalars(select(MetaLead.id)).all() == [leads["surrogate"]]
    with access.authorized_dataset(db, context.manager):
        assert db.query(MetaLead).count() == 0
    with access.authorized_dataset(db, context.admin):
        assert db.query(MetaLead).count() == 4


@pytest.mark.asyncio
async def test_report_pdf_keeps_viewer_scope_and_omits_organization_spend(db, context, monkeypatch):
    from unittest.mock import AsyncMock

    from app.db.enums import Role
    from app.db.models import User, UserPermissionOverride
    from app.services import pdf_export_service
    from tests.test_email_templates_personal_scope import authed_client_for_user

    _record(db, context.intake, "surrogate")
    _record(db, context.manager, "surrogate", suffix=2)
    db.add(
        UserPermissionOverride(
            organization_id=context.org.id,
            user_id=context.intake.user_id,
            permission="view_reports",
            override_type="grant",
        )
    )
    db.flush()
    received = {}

    def capture_html(**kwargs):
        received.update(kwargs)
        return "<p>synthetic report</p>"

    spend = AsyncMock(
        side_effect=AssertionError("restricted report must not load organization spend")
    )
    monkeypatch.setattr(analytics_service, "get_meta_spend_summary", spend)
    monkeypatch.setattr(pdf_export_service, "_generate_analytics_html", capture_html)
    monkeypatch.setattr(
        pdf_export_service, "_render_html_to_pdf", AsyncMock(return_value=b"%PDF-synthetic")
    )
    user = db.get(User, context.intake.user_id)
    async with authed_client_for_user(db, context.org.id, user, Role.INTAKE_SPECIALIST) as client:
        response = await client.get("/analytics/export/pdf")
    assert response.status_code == 200, response.text
    assert received["summary"]["total_surrogates"] == 1
    assert received["meta_spend"] is None
    spend.assert_not_awaited()
