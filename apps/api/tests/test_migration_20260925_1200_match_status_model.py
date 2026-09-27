"""Upgrade legacy match states without inventing decline reasons or acceptance."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from alembic import command
from app.db.enums import AuditEventType
from app.db.models import AutomationWorkflow
from app.services import audit_service, pipeline_service, version_service
from tests.test_match_events import _create_case, _create_intended_parent
from tests.test_migration_20260829_donor_module import _alembic_config, _insert_donor_fixture
from tests.test_migration_20260920_workflow_template_subject_type import _insert_template

REVISION = "20260925_1200_match_status_model"
PREVIOUS = "20260924_0930_scheduling_permission_heads"


@pytest.mark.parametrize("donor", [False, True])
@pytest.mark.parametrize("unknown_status", [False, True])
def test_upgrade_preserves_reasons_history_and_rejects_unknown_statuses(
    db_engine, donor, unknown_status
):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)
            command.downgrade(config, PREVIOUS)
            fixture = _insert_donor_fixture(connection, label="match-status")
            org_id, user_id = fixture["org_id"], fixture["user_id"]
            cases = {}
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                pipeline = pipeline_service.get_or_create_default_pipeline(db, org_id)
                stage = pipeline_service.get_stage_by_key(db, pipeline.id, "new_unread")
                for index, (label, status, expected) in enumerate(
                    [
                        ("proposed", "proposed", "under_review"),
                        ("reviewing", "reviewing", "under_review"),
                        ("rejected", "rejected", "declined"),
                        ("withdrawn", "cancelled", "declined"),
                        ("auto_closed", "cancelled", "declined"),
                        ("viewed_then_withdrawn", "cancelled", "declined"),
                        ("accepted", "accepted", "accepted"),
                        ("pending", "cancel_pending", "cancellation_pending"),
                        ("accepted_then_cancelled", "cancelled", "cancelled"),
                        ("approved_cancellation", "cancelled", "cancelled"),
                        ("completed", "completed", "completed"),
                    ]
                ):
                    ip = _create_intended_parent(db, org_id)
                    surrogate = None if donor else _create_case(db, org_id, user_id, stage)
                    match_id = uuid4()
                    rejection_reason = "Not a fit" if label == "rejected" else None
                    closure_reason = "Another match accepted" if label == "auto_closed" else None
                    cases[label] = (match_id, status, expected, rejection_reason, closure_reason)
                    db.execute(
                        text("""
                        INSERT INTO matches (id, organization_id, match_number, surrogate_id, donor_id, match_kind,
                            intended_parent_id, status, proposed_by_user_id, reviewed_at, rejection_reason, closure_reason, notes)
                        VALUES (:id, :org, :number, :surrogate, :donor, :kind, :ip, :status, :user, :reviewed,
                            :rejection_reason, :closure_reason, 'Preserved')
                    """),
                        {
                            "id": match_id,
                            "org": org_id,
                            "number": f"M{10001 + index}",
                            "surrogate": surrogate.id if surrogate else None,
                            "donor": fixture["donor_id"] if donor else None,
                            "kind": "donor" if donor else "surrogate",
                            "ip": ip.id,
                            "status": status,
                            "user": user_id,
                            "rejection_reason": rejection_reason,
                            "closure_reason": closure_reason,
                            "reviewed": datetime.now(UTC)
                            if label == "viewed_then_withdrawn"
                            else None,
                        },
                    )
                    if label == "accepted_then_cancelled":
                        audit_service.log_event(
                            db,
                            org_id,
                            AuditEventType.MATCH_ACCEPTED,
                            actor_user_id=user_id,
                            target_type="match",
                            target_id=match_id,
                        )
                        db.flush()
                    if label == "approved_cancellation":
                        db.execute(
                            text("""INSERT INTO status_change_requests (id, organization_id, entity_type, entity_id,
                            target_status, effective_at, reason, requested_by_user_id, status, requested_at)
                            VALUES (:id, :org, 'match', :match, 'cancelled', now(), 'Ended', :user, 'approved', now())"""),
                            {"id": uuid4(), "org": org_id, "match": match_id, "user": user_id},
                        )
                db.commit()
            workflow_id = uuid4()
            with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                db.add(
                    AutomationWorkflow(
                        id=workflow_id,
                        organization_id=org_id,
                        name="Legacy decline",
                        trigger_type="match_rejected",
                        subject_type="match",
                        trigger_config={},
                        conditions=[],
                        actions=[],
                        created_by_user_id=user_id,
                    )
                )
                db.commit()
            template_id = _insert_template(
                connection,
                stored_trigger_type="match_rejected",
                draft_trigger_type="match_rejected",
                name="Legacy match template",
            )
            if unknown_status:
                connection.execute(
                    text("UPDATE matches SET status='pending' WHERE id=:id"),
                    {"id": cases["proposed"][0]},
                )

                def snapshot():
                    return {
                        table: connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
                        for table in (
                            "matches",
                            "audit_logs",
                            "automation_workflows",
                            "workflow_templates",
                        )
                    }

                original = snapshot()
                with pytest.raises(RuntimeError, match=r"1.*pending"):
                    command.upgrade(config, REVISION)
                assert snapshot() == original
                columns = {c["name"] for c in inspect(connection).get_columns("matches")}
                assert "rejection_reason" in columns and "decline_reason" not in columns
                assert (
                    connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                    == PREVIOUS
                )
                return
            command.upgrade(config, REVISION)
            command.upgrade(config, REVISION)
            for match_id, old, expected, rejection_reason, closure_reason in cases.values():
                row = connection.execute(
                    text(
                        "SELECT status, decline_reason, closure_reason, notes FROM matches WHERE id=:id"
                    ),
                    {"id": match_id},
                ).one()
                assert row.status == expected
                assert row.notes == "Preserved"
                assert row.decline_reason == rejection_reason
                assert row.closure_reason == closure_reason
                history = connection.execute(
                    text(
                        "SELECT details, actor_user_id FROM audit_logs WHERE target_id=:id AND event_type='match_status_migrated'"
                    ),
                    {"id": match_id},
                ).all()
                if old != expected:
                    assert len(history) == 1
                    assert history[0].actor_user_id is None
                    assert history[0].details == {
                        "match_id": str(match_id),
                        "original_status": old,
                        "status": expected,
                        "migration": REVISION,
                        **(
                            {"decline_reason": rejection_reason}
                            if rejection_reason is not None
                            else {}
                        ),
                        **(
                            {"closure_reason": closure_reason} if closure_reason is not None else {}
                        ),
                    }
                else:
                    assert history == []
            assert (
                connection.execute(
                    text("SELECT trigger_type FROM automation_workflows WHERE id=:id"),
                    {"id": workflow_id},
                ).scalar_one()
                == "match_declined"
            )
            template = connection.execute(
                text("SELECT trigger_type, draft_config FROM workflow_templates WHERE id=:id"),
                {"id": template_id},
            ).one()
            assert (
                template.trigger_type == template.draft_config["trigger_type"] == "match_declined"
            )
            indexes = {
                item["name"]: str(item["dialect_options"]["postgresql_where"])
                for item in inspect(connection).get_indexes("matches")
                if item["name"].startswith("uq_match_open")
                or item["name"] == "uq_one_accepted_match_per_surrogate"
            }
            assert len(indexes) == 3
            assert all(
                "cancellation_pending" in predicate and "cancel_pending" not in predicate
                for predicate in indexes.values()
            )
            # Migration appends must remain verifiable by the live audit-chain contract.
            previous = "0" * 64
            for entry in connection.execute(
                text("SELECT * FROM audit_logs WHERE organization_id=:org ORDER BY created_at, id"),
                {"org": org_id},
            ):
                assert entry.prev_hash == previous
                assert entry.entry_hash == version_service.compute_audit_hash(
                    prev_hash=previous,
                    entry_id=str(entry.id),
                    org_id=str(org_id),
                    event_type=entry.event_type,
                    created_at=str(entry.created_at),
                    details_json=audit_service.canonical_json(entry.details),
                    actor_user_id=str(entry.actor_user_id) if entry.actor_user_id else "",
                    target_type=entry.target_type or "",
                    target_id=str(entry.target_id) if entry.target_id else "",
                )
                previous = entry.entry_hash
        finally:
            transaction.rollback()
