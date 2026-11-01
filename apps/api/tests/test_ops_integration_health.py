from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import event

from app.db.enums import IntegrationType
from app.db.models import IntegrationErrorRollup, IntegrationHealth, Organization
from app.services import ops_service


@contextmanager
def _collect_selects(db):
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        if statement.lstrip().lower().startswith("select"):
            statements.append(" ".join(statement.split()))

    event.listen(db.bind, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(db.bind, "before_cursor_execute", before_cursor_execute)


def _add_health(db, *, org_id, integration_type: IntegrationType, key: str) -> None:
    db.add(
        IntegrationHealth(
            organization_id=org_id,
            integration_type=integration_type.value,
            integration_key=key,
            status="error",
            config_status="configured",
        )
    )


def _add_rollup(
    db,
    *,
    org_id,
    integration_type: IntegrationType,
    key: str,
    period_start: datetime,
    error_count: int,
) -> None:
    db.add(
        IntegrationErrorRollup(
            organization_id=org_id,
            integration_type=integration_type.value,
            integration_key=key,
            period_start=period_start,
            error_count=error_count,
        )
    )


def test_list_integration_health_counts_recent_errors_per_integration(db, test_org):
    other_org = Organization(id=uuid4(), name="Other Org", slug=f"other-{uuid4().hex[:8]}")
    db.add(other_org)
    db.flush()

    recent = ops_service.get_hour_bucket() - timedelta(hours=1)
    stale = ops_service.get_hour_bucket() - timedelta(hours=30)
    default_key = ops_service.DEFAULT_INTEGRATION_KEY

    _add_health(db, org_id=test_org.id, integration_type=IntegrationType.META_LEADS, key="page-1")
    _add_health(db, org_id=test_org.id, integration_type=IntegrationType.META_LEADS, key="page-2")
    _add_health(db, org_id=test_org.id, integration_type=IntegrationType.WORKER, key=default_key)
    _add_health(db, org_id=test_org.id, integration_type=IntegrationType.ZAPIER, key=default_key)

    _add_rollup(
        db,
        org_id=test_org.id,
        integration_type=IntegrationType.META_LEADS,
        key="page-1",
        period_start=recent,
        error_count=2,
    )
    _add_rollup(
        db,
        org_id=test_org.id,
        integration_type=IntegrationType.META_LEADS,
        key="page-1",
        period_start=recent - timedelta(hours=1),
        error_count=3,
    )
    _add_rollup(
        db,
        org_id=test_org.id,
        integration_type=IntegrationType.META_LEADS,
        key="page-2",
        period_start=stale,
        error_count=7,
    )
    _add_rollup(
        db,
        org_id=test_org.id,
        integration_type=IntegrationType.WORKER,
        key=default_key,
        period_start=recent,
        error_count=4,
    )
    _add_rollup(
        db,
        org_id=other_org.id,
        integration_type=IntegrationType.ZAPIER,
        key=default_key,
        period_start=recent,
        error_count=9,
    )
    db.flush()

    with _collect_selects(db) as statements:
        result = ops_service.list_integration_health(db, test_org.id)

    counts = {
        (item["integration_type"], item["integration_key"]): item["error_count_24h"]
        for item in result
    }
    assert counts == {
        (IntegrationType.META_LEADS.value, "page-1"): 5,
        (IntegrationType.META_LEADS.value, "page-2"): 0,
        (IntegrationType.WORKER.value, default_key): 4,
        (IntegrationType.ZAPIER.value, default_key): 0,
    }
    rollup_selects = [s for s in statements if "integration_error_rollup" in s]
    assert len(rollup_selects) == 1
