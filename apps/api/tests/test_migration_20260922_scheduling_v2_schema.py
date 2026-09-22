"""Scheduling v2 schema migration preserves scoped calendar ownership."""

import importlib.util
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


def test_scheduling_v2_schema_migration_round_trip(db):
    path = Path(__file__).parents[1] / "alembic/versions/20260922_1000_scheduling_v2_schema.py"
    spec = importlib.util.spec_from_file_location("scheduling_v2_schema_migration", path)
    migration = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(migration)
    connection = db.connection()

    with Operations.context(MigrationContext.configure(connection)):
        migration.downgrade()
        tables = set(inspect(connection).get_table_names())
        assert {
            "calendar_bindings",
            "external_calendar_events",
            "scheduling_request_receipts",
        }.isdisjoint(tables)
        migration.upgrade()

    inspector = inspect(connection)
    assert {
        "calendar_bindings",
        "external_calendar_events",
        "scheduling_request_receipts",
    } <= set(inspector.get_table_names())
    assert "timezone" in {column["name"] for column in inspector.get_columns("calendar_bindings")}
    assert {
        "revision",
        "origin",
        "google_last_synced",
        "google_conflict",
        "google_sync_error",
        "availability_override_reason",
    } <= {column["name"] for column in inspector.get_columns("appointments")}

    defaults = {
        column["name"]: column["default"] for column in inspector.get_columns("appointments")
    }
    assert defaults["revision"] == "0"
    assert "crm" in str(defaults["origin"])

    binding_fks = {
        constraint["name"]: (tuple(constraint["constrained_columns"]), constraint["referred_table"])
        for constraint in inspector.get_foreign_keys("calendar_bindings")
    }
    assert binding_fks["fk_calendar_bindings_membership_scope"] == (
        ("organization_id", "user_id"),
        "memberships",
    )
    assert binding_fks["fk_calendar_bindings_integration_owner"] == (
        ("user_id", "integration_id"),
        "user_integrations",
    )

    projection_fks = {
        constraint["name"]: tuple(constraint["constrained_columns"])
        for constraint in inspector.get_foreign_keys("external_calendar_events")
    }
    assert projection_fks["fk_external_calendar_events_binding_scope"] == (
        "organization_id",
        "binding_id",
    )
    receipt_fks = {
        constraint["name"]: tuple(constraint["constrained_columns"])
        for constraint in inspector.get_foreign_keys("scheduling_request_receipts")
    }
    assert receipt_fks["fk_scheduling_request_receipts_appointment_scope"] == (
        "organization_id",
        "appointment_id",
    )

    indexes = connection.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'calendar_bindings' "
            "AND indexname = 'uq_calendar_bindings_active_booking_owner'"
        )
    ).scalar_one()
    assert "WHERE (is_active AND write_bookings)" in indexes


def test_calendar_binding_scope_constraints_reject_cross_org_and_wrong_owner(
    db, test_org, test_user
):
    from app.db.models import CalendarBinding, Organization, User, UserIntegration

    other_org = Organization(name="Other Organization", slug=f"other-org-{uuid4().hex}")
    other_user = User(
        email=f"other-user-{uuid4().hex}@test.com",
        display_name="Other User",
        token_version=1,
        is_active=True,
    )
    db.add_all([other_org, other_user])
    db.flush()

    owner_integration = UserIntegration(
        user_id=test_user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="owner@example.com",
    )
    other_integration = UserIntegration(
        user_id=other_user.id,
        integration_type="google_calendar",
        access_token_encrypted="test-token",
        account_email="other@example.com",
    )
    db.add_all([owner_integration, other_integration])
    db.flush()

    def binding(*, organization_id, integration_id):
        return CalendarBinding(
            organization_id=organization_id,
            user_id=test_user.id,
            integration_id=integration_id,
            account_email="owner@example.com",
            calendar_id=f"calendar-{uuid4().hex}",
            display_name="Test calendar",
            access_role="owner",
        )

    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(binding(organization_id=other_org.id, integration_id=owner_integration.id))
        db.flush()

    with pytest.raises(IntegrityError), db.begin_nested():
        db.add(binding(organization_id=test_org.id, integration_id=other_integration.id))
        db.flush()
