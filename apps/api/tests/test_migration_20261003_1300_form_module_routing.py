"""Upgrade defaults and database-enforced routing/task invariants."""

from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from alembic import command

PREVIOUS = "20261003_1200_repair_seeded_system_workflows"
REVISION = "20261003_1300_form_module_routing"


def test_upgrade_backfills_kind_defaults_and_enforces_invariants(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            org_id, other_org_id, user_id = uuid4(), uuid4(), uuid4()
            for org in (org_id, other_org_id):
                connection.execute(
                    text(
                        "INSERT INTO organizations (id, name, slug) VALUES (:id, 'Routing', :slug)"
                    ),
                    {"id": org, "slug": org.hex},
                )
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Routing editor')"
                ),
                {"id": user_id, "email": f"{user_id}@example.com"},
            )
            forms = {kind: uuid4() for kind in ("surrogate", "egg_donor", "sperm_donor")}
            for kind, form_id in forms.items():
                connection.execute(
                    text(
                        "INSERT INTO forms (id, organization_id, name, lead_kind) VALUES (:id, :org, 'Application', :kind)"
                    ),
                    {"id": form_id, "org": org_id, "kind": kind},
                )
            command.upgrade(config, REVISION)
            rows = connection.execute(
                text(
                    "SELECT lead_kind, routing_exact_match, routing_no_match, routing_lead_source, routing_auto_create_donor, routing_updated_by_user_id FROM forms WHERE organization_id = :org ORDER BY lead_kind"
                ),
                {"org": org_id},
            ).all()
            assert [tuple(row) for row in rows] == [
                ("egg_donor", "auto", "auto", "website", True, None),
                ("sperm_donor", "auto", "auto", "website", True, None),
                ("surrogate", "review", "review", None, False, None),
            ]
            surrogate_form = forms["surrogate"]
            for assignment in (
                "routing_exact_match = 'off'",
                "routing_exact_match = NULL",
                "routing_no_match = 'invalid'",
                "routing_no_match = NULL",
                "routing_lead_source = 'manual'",
                "routing_auto_create_donor = true",
            ):
                with pytest.raises(IntegrityError), connection.begin_nested():
                    connection.execute(
                        text(f"UPDATE forms SET {assignment} WHERE id = :id"),
                        {"id": surrogate_form},
                    )
            connection.execute(
                text("UPDATE forms SET routing_updated_by_user_id = :user WHERE id = :id"),
                {"id": surrogate_form, "user": user_id},
            )
            connection.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
            assert (
                connection.execute(
                    text("SELECT routing_updated_by_user_id FROM forms WHERE id = :id"),
                    {"id": surrogate_form},
                ).scalar_one()
                is None
            )

            submission_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO form_submissions (id, organization_id, form_id, answers_json) VALUES (:id, :org, :form, '{}'::jsonb)"
                ),
                {"id": submission_id, "org": org_id, "form": surrogate_form},
            )
            for assignment in (
                "match_status = 'routing_review'",
                "routing_review_step = 'match'",
                "match_status = 'routing_review', routing_review_step = 'unknown'",
            ):
                with pytest.raises(IntegrityError), connection.begin_nested():
                    connection.execute(
                        text(f"UPDATE form_submissions SET {assignment} WHERE id = :id"),
                        {"id": submission_id},
                    )
            connection.execute(
                text(
                    "UPDATE form_submissions SET match_status = 'routing_review', routing_review_step = 'match' WHERE id = :id"
                ),
                {"id": submission_id},
            )
            user_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Task owner')"
                ),
                {"id": user_id, "email": f"{user_id}@example.com"},
            )
            insert_task = text(
                "INSERT INTO tasks (id, organization_id, form_submission_id, created_by_user_id, owner_type, owner_id, title, task_type, status) VALUES (:id, :org, :submission, :user, 'user', :user, 'Review', 'review', :status)"
            )
            params = {
                "id": uuid4(),
                "org": org_id,
                "submission": submission_id,
                "user": user_id,
                "status": "pending",
            }
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(insert_task, {**params, "org": other_org_id})
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(insert_task, {**params, "submission": uuid4()})
            connection.execute(insert_task, params)
            for status in ("pending", "in_progress"):
                with pytest.raises(IntegrityError), connection.begin_nested():
                    connection.execute(insert_task, {**params, "id": uuid4(), "status": status})
            connection.execute(
                text("UPDATE tasks SET status = 'completed', is_completed = true WHERE id = :id"),
                {"id": params["id"]},
            )
            connection.execute(insert_task, {**params, "id": uuid4(), "status": "in_progress"})
            connection.execute(
                text("DELETE FROM form_submissions WHERE id = :id"), {"id": submission_id}
            )
            assert (
                connection.execute(
                    text("SELECT count(*) FROM tasks WHERE form_submission_id = :id"),
                    {"id": submission_id},
                ).scalar_one()
                == 0
            )
        finally:
            transaction.rollback()
