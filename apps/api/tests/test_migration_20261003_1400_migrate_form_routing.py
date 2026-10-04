"""Data migration preserves routing intent, tenant boundaries, and pending reviews."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from alembic import command

PREVIOUS = "20261003_1310_form_module_routing"
REVISION = "20261003_1400_migrate_form_routing"
MATCH = "auto_match_submission"
CREATE = "create_intake_lead"
NOTICE = {
    "action_type": "send_notification",
    "title": "Application received",
    "recipients": "owner",
}
RECORD_UPDATE = {"action_type": "update_field", "field": "is_priority", "value": True}


def _org(connection):
    org, user = uuid4(), uuid4()
    connection.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, 'Routing migration', :slug)"),
        {"id": org, "slug": org.hex},
    )
    connection.execute(
        text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, 'Reviewer')"),
        {"id": user, "email": f"{user}@example.com"},
    )
    connection.execute(
        text(
            "INSERT INTO memberships (id, organization_id, user_id, role, is_active) VALUES (:id, :org, :user, 'admin', TRUE)"
        ),
        {"id": uuid4(), "org": org, "user": user},
    )
    return org, user


def _form(connection, org, user, kind="surrogate"):
    form = uuid4()
    connection.execute(
        text("""
        INSERT INTO forms (id, organization_id, name, lead_kind, created_by_user_id,
            routing_exact_match, routing_no_match, routing_lead_source, routing_auto_create_donor)
        VALUES (:id, :org, 'Application', :kind, :user, :match, :create, :source, :donor)
    """),
        {
            "id": form,
            "org": org,
            "user": user,
            "kind": kind,
            "match": "review" if kind == "surrogate" else "auto",
            "create": "review" if kind == "surrogate" else "auto",
            "source": None if kind == "surrogate" else "website",
            "donor": kind != "surrogate",
        },
    )
    return form


def _workflow(
    connection, org, form, actions, *, generated=False, conditions=None, enabled=True, kind=None
):
    workflow = uuid4()
    config = {"form_id": str(form)} if form else {}
    if kind:
        config["lead_kind"] = kind
    connection.execute(
        text("""
        INSERT INTO automation_workflows (id, organization_id, name, icon, schema_version, run_count, scope, subject_type, trigger_type,
            trigger_config, conditions, condition_logic, actions, is_enabled, is_system_workflow, system_key)
        VALUES (:id, :org, :name, 'workflow', 1, 0, 'org', 'form_submission', 'form_submitted', CAST(:config AS jsonb),
            CAST(:conditions AS jsonb), 'AND', CAST(:actions AS jsonb), :enabled, :generated, :key)
    """),
        {
            "id": workflow,
            "org": org,
            "name": f"Route {workflow}",
            "config": json.dumps(config),
            "conditions": json.dumps(conditions or []),
            "actions": json.dumps(actions),
            "enabled": enabled,
            "generated": generated,
            "key": f"shared_intake_routing:{form}" if generated else None,
        },
    )
    return workflow


def _settings(connection, form):
    return tuple(
        connection.execute(
            text(
                "SELECT routing_exact_match, routing_no_match, routing_lead_source, routing_auto_create_donor FROM forms WHERE id = :id"
            ),
            {"id": form},
        ).one()
    )


def test_upgrade_maps_routing_shapes_and_never_uses_foreign_form_bindings(db_engine, caplog):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            org, user = _org(connection)
            cases = [
                (
                    "egg_donor",
                    [{"action_type": CREATE, "requires_approval": True}],
                    {"generated": True},
                    ("review", "review", None, False),
                    True,
                ),
                (
                    "sperm_donor",
                    [{"action_type": CREATE}],
                    {},
                    ("review", "auto", None, False),
                    True,
                ),
                (
                    "surrogate",
                    [{"action_type": MATCH, "requires_approval": True}, RECORD_UPDATE, NOTICE],
                    {},
                    ("review", "off", None, False),
                    False,
                ),
                (
                    "surrogate",
                    [
                        {"action_type": MATCH, "requires_approval": True},
                        {"action_type": CREATE, "requires_approval": True},
                    ],
                    {"generated": True},
                    ("review", "review", None, False),
                    True,
                ),
                (
                    "egg_donor",
                    [
                        {"action_type": MATCH, "requires_approval": False},
                        {
                            "action_type": CREATE,
                            "requires_approval": False,
                            "source": "website",
                            "auto_promote": True,
                        },
                    ],
                    {"generated": True},
                    ("auto", "auto", "website", True),
                    True,
                ),
                (
                    "sperm_donor",
                    [
                        {"action_type": MATCH, "requires_approval": True},
                        {"action_type": CREATE, "source": "form_embed", "auto_promote": False},
                    ],
                    {},
                    ("review", "auto", "form_embed", False),
                    True,
                ),
                ("surrogate", [{"action_type": MATCH}], {}, ("auto", "off", None, False), True),
                (
                    "surrogate",
                    [
                        {"action_type": MATCH},
                        RECORD_UPDATE,
                        {"action_type": CREATE, "requires_approval": True},
                        NOTICE,
                    ],
                    {},
                    ("auto", "review", None, False),
                    False,
                ),
                (
                    "egg_donor",
                    [
                        {"action_type": MATCH},
                        {"action_type": CREATE, "source": "website", "auto_promote": True},
                        {
                            "action_type": "update_field",
                            "field": "education",
                            "value": "Graduate degree",
                        },
                    ],
                    {},
                    ("auto", "auto", "website", True),
                    False,
                ),
                (
                    "surrogate",
                    [{"action_type": MATCH}, {"action_type": CREATE}],
                    {
                        "conditions": [
                            {"field": "source_mode", "operator": "equals", "value": "shared"}
                        ]
                    },
                    ("auto", "auto", None, False),
                    False,
                ),
                (
                    "egg_donor",
                    [
                        {"action_type": MATCH},
                        {"action_type": CREATE, "source": "website", "auto_promote": True},
                    ],
                    {"generated": True, "enabled": False},
                    ("review", "off", "website", True),
                    True,
                ),
                (
                    "surrogate",
                    [{"action_type": MATCH}, {"action_type": CREATE}, NOTICE],
                    {"enabled": False},
                    ("review", "off", None, False),
                    False,
                ),
            ]
            records = []
            for kind, actions, options, expected, deleted in cases:
                form = _form(connection, org, user, kind)
                workflow = _workflow(connection, org, form, actions, **options)
                records.append(
                    (
                        form,
                        workflow,
                        expected,
                        deleted,
                        [a for a in actions if a["action_type"] not in {MATCH, CREATE}],
                        options.get("enabled", True),
                    )
                )
            broad_org, broad_user = _org(connection)
            broad_forms = [
                _form(connection, broad_org, broad_user, kind)
                for kind in ("surrogate", "egg_donor", "sperm_donor")
            ]
            broad_workflow = _workflow(
                connection,
                broad_org,
                None,
                [
                    {"action_type": MATCH},
                    {"action_type": CREATE, "requires_approval": True},
                    NOTICE,
                ],
                kind="egg_donor",
            )
            foreign_form = _form(connection, broad_org, broad_user)
            foreign_workflow = _workflow(
                connection, org, foreign_form, [{"action_type": MATCH}, {"action_type": CREATE}]
            )
            untouched = _workflow(connection, broad_org, foreign_form, [RECORD_UPDATE, NOTICE])
            conflict_form = _form(connection, org, user, "egg_donor")
            _workflow(
                connection,
                org,
                conflict_form,
                [
                    {"action_type": MATCH},
                    {"action_type": CREATE, "source": "website", "auto_promote": True},
                ],
            )
            _workflow(
                connection,
                org,
                conflict_form,
                [{"action_type": MATCH}, {"action_type": CREATE, "source": "form_embed"}],
                enabled=False,
            )
            with caplog.at_level("INFO", logger="alembic.runtime.migration"):
                command.upgrade(config, REVISION)
            assert (
                connection.execute(
                    text(
                        "SELECT current_setting('lock_timeout')::interval = interval '3 seconds' AND current_setting('statement_timeout')::interval = interval '60 seconds'"
                    )
                ).scalar_one()
                is True
            )
            for form, workflow, expected, deleted, remaining, enabled in records:
                assert _settings(connection, form) == expected
                row = connection.execute(
                    text(
                        "SELECT actions, is_enabled, is_system_workflow, system_key FROM automation_workflows WHERE organization_id = :org AND id = :id"
                    ),
                    {"org": org, "id": workflow},
                ).first()
                if deleted:
                    assert row is None
                else:
                    assert tuple(row) == (remaining, bool(remaining) and enabled, False, None)
                assert str(workflow) in caplog.text
            assert (
                f"Approval-gated record actions require review: workflow_id={records[2][1]}"
                in caplog.text
            )
            assert _settings(connection, broad_forms[0]) == ("review", "review", None, False)
            assert _settings(connection, broad_forms[1]) == ("auto", "review", None, False)
            assert _settings(connection, broad_forms[2]) == ("auto", "auto", "website", True)
            assert _settings(connection, foreign_form) == ("review", "review", None, False)
            assert _settings(connection, conflict_form) == ("review", "off", None, False)
            assert connection.execute(
                text(
                    "SELECT actions FROM automation_workflows WHERE id = :id AND organization_id = :org"
                ),
                {"id": broad_workflow, "org": broad_org},
            ).scalar_one() == [NOTICE]
            assert (
                connection.execute(
                    text(
                        "SELECT actions FROM automation_workflows WHERE id = :id AND organization_id = :org"
                    ),
                    {"id": foreign_workflow, "org": org},
                ).scalar_one()
                == []
            )
            assert tuple(
                connection.execute(
                    text(
                        "SELECT actions, is_enabled FROM automation_workflows WHERE id = :id AND organization_id = :org"
                    ),
                    {"id": untouched, "org": broad_org},
                ).one()
            ) == ([RECORD_UPDATE, NOTICE], True)
            # Already-upgraded deployments do not duplicate changes on a second upgrade.
            command.upgrade(config, REVISION)
        finally:
            transaction.rollback()


@pytest.mark.parametrize("has_reviewer", [True, False])
@pytest.mark.parametrize("timezone", ["UTC", "America/Los_Angeles"])
def test_upgrade_moves_paused_actions_to_submission_reviews(db_engine, has_reviewer, timezone):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            org, user = _org(connection)
            connection.execute(
                text("UPDATE organizations SET timezone = :timezone WHERE id = :org"),
                {"timezone": timezone, "org": org},
            )
            expected = []
            if not has_reviewer:
                connection.execute(
                    text("UPDATE memberships SET is_active = false WHERE organization_id = :org"),
                    {"org": org},
                )
            due = datetime(2026, 10, 6, 2, 30, tzinfo=UTC)
            local_due = datetime(2026, 10, 5, 19, 30) if timezone == "America/Los_Angeles" else due
            for action_type, step in ((MATCH, "match"), (CREATE, "create_lead")):
                form = _form(connection, org, user)
                action = {"action_type": action_type, "requires_approval": True}
                workflow = _workflow(connection, org, form, [action])
                submission, execution, task = uuid4(), uuid4(), uuid4()
                connection.execute(
                    text(
                        "INSERT INTO form_submissions (id, organization_id, form_id, answers_json, source_mode, match_status) VALUES (:id, :org, :form, '{}'::jsonb, 'shared', 'workflow_pending')"
                    ),
                    {"id": submission, "org": org, "form": form},
                )
                connection.execute(
                    text("""
                    INSERT INTO workflow_executions (id, organization_id, workflow_id, event_id, depth,
                        event_source, entity_type, entity_id, subject_type, subject_id, trigger_event,
                        matched_conditions, actions_executed, status, paused_at_action_index)
                    VALUES (:id, :org, :workflow, :event, 0, 'system', 'form_submission', :submission,
                        'form_submission', :submission, CAST(:event_data AS jsonb), TRUE, '[]'::jsonb, 'paused', 0)
                """),
                    {
                        "id": execution,
                        "org": org,
                        "workflow": workflow,
                        "event": uuid4(),
                        "submission": submission,
                        "event_data": json.dumps({"_form_submission_workflow_actions": [action]}),
                    },
                )
                connection.execute(
                    text("""
                    INSERT INTO tasks (id, organization_id, created_by_user_id, owner_type, owner_id,
                        title, task_type, status, workflow_execution_id, workflow_action_index,
                        workflow_action_type, workflow_action_payload, due_at)
                    VALUES (:id, :org, :user, 'user', :user, 'Approval', 'workflow_approval', 'pending',
                        :execution, 0, :action_type, CAST(:action AS jsonb), :due)
                """),
                    {
                        "id": task,
                        "org": org,
                        "user": user,
                        "execution": execution,
                        "action_type": action_type,
                        "action": json.dumps(action),
                        "due": due,
                    },
                )
                connection.execute(
                    text(
                        "UPDATE workflow_executions SET paused_task_id = :task WHERE id = :id AND organization_id = :org"
                    ),
                    {"id": execution, "org": org, "task": task},
                )
                expected.append((submission, execution, task, workflow, step))
            command.upgrade(config, REVISION)
            for submission, execution, task, workflow, step in expected:
                assert tuple(
                    connection.execute(
                        text(
                            "SELECT match_status, routing_review_step FROM form_submissions WHERE id = :id AND organization_id = :org"
                        ),
                        {"id": submission, "org": org},
                    ).one()
                ) == ("routing_review", step)
                assert tuple(
                    connection.execute(
                        text(
                            "SELECT status, is_completed, completed_at IS NOT NULL FROM tasks WHERE id = :id AND organization_id = :org"
                        ),
                        {"id": task, "org": org},
                    ).one()
                ) == ("completed", True, True)
                assert tuple(
                    connection.execute(
                        text(
                            "SELECT status, paused_task_id, paused_at_action_index FROM workflow_executions WHERE id = :id AND organization_id = :org"
                        ),
                        {"id": execution, "org": org},
                    ).one()
                ) == ("canceled", None, None)
                assert tuple(
                    connection.execute(
                        text(
                            "SELECT actions, is_enabled FROM automation_workflows WHERE id = :id AND organization_id = :org"
                        ),
                        {"id": workflow, "org": org},
                    ).one()
                ) == ([], False)
                review = connection.execute(
                    text(
                        "SELECT owner_id, due_at, status, title, due_date, due_time FROM tasks WHERE form_submission_id = :id AND organization_id = :org AND task_type = 'review'"
                    ),
                    {"id": submission, "org": org},
                ).first()
                if has_reviewer:
                    assert tuple(review) == (
                        user,
                        due,
                        "pending",
                        "Review submission: Application",
                        local_due.date(),
                        local_due.time(),
                    )
                else:
                    assert review is None
                # A resume job already queued before migration cannot run the retired payload.
                from app.db.models import Task
                from app.services.workflow_engine import engine

                with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
                    engine.continue_execution(db, execution, db.get(Task, task), "approved")
                assert tuple(
                    connection.execute(
                        text("""
                            SELECT match_status, routing_review_step, intake_lead_id
                            FROM form_submissions WHERE id = :id AND organization_id = :org
                        """),
                        {"id": submission, "org": org},
                    ).one()
                ) == ("routing_review", step, None)
            command.upgrade(config, REVISION)
            assert connection.execute(
                text(
                    "SELECT count(*) FROM tasks WHERE organization_id = :org AND task_type = 'review'"
                ),
                {"org": org},
            ).scalar_one() == (2 if has_reviewer else 0)
        finally:
            transaction.rollback()


@pytest.mark.parametrize("generated", [False, True])
def test_upgrade_preserves_routing_authority(db_engine, generated):
    from types import SimpleNamespace

    from app.services.workflow_execution_authority import configuration_digest

    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            expected = []
            for version, grant_type in (
                (1, "missing"),
                (2, "missing"),
                (2, "current"),
                (2, "stale"),
                (2, "foreign"),
            ):
                org, user = _org(connection)
                connection.execute(
                    text("""
                        INSERT INTO organization_permission_policies (organization_id, version)
                        VALUES (:org, :version)
                    """),
                    {"org": org, "version": version},
                )
                for kind in ("surrogate", "egg_donor", "sperm_donor"):
                    donor = kind != "surrogate"
                    form = _form(connection, org, user, kind)
                    actions = [
                        {"action_type": MATCH, "requires_approval": not donor},
                        {
                            "action_type": CREATE,
                            "requires_approval": not donor,
                            **({"source": "website", "auto_promote": True} if donor else {}),
                        },
                    ]
                    workflow = _workflow(connection, org, form, actions, generated=generated)
                    if grant_type != "missing":
                        row = (
                            connection.execute(
                                text(
                                    "SELECT * FROM automation_workflows WHERE id = :id AND organization_id = :org"
                                ),
                                {"id": workflow, "org": org},
                            )
                            .mappings()
                            .one()
                        )
                        grant = {
                            "organization_id": str(uuid4() if grant_type == "foreign" else org),
                            "configuration_digest": "stale"
                            if grant_type == "stale"
                            else configuration_digest(SimpleNamespace(**row)),
                        }
                        connection.execute(
                            text("""
                                UPDATE automation_workflows SET execution_authority = CAST(:grant AS jsonb)
                                WHERE id = :id AND organization_id = :org
                            """),
                            {"id": workflow, "org": org, "grant": json.dumps(grant)},
                        )
                    paused = version == 2 and grant_type != "current"
                    expected.append(
                        (
                            form,
                            (
                                "review" if paused or not donor else "auto",
                                "off" if paused else "auto" if donor else "review",
                                "website" if donor else None,
                                donor,
                            ),
                        )
                    )
            command.upgrade(config, REVISION)
            for form, settings in expected:
                assert _settings(connection, form) == settings
        finally:
            transaction.rollback()


def test_upgrade_does_not_follow_cross_organization_execution_relationships(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = Config()
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        config.attributes["connection"] = connection
        try:
            command.downgrade(config, PREVIOUS)
            org, user = _org(connection)
            foreign_org, foreign_user = _org(connection)
            form = _form(connection, org, user)
            foreign_form = _form(connection, foreign_org, foreign_user)
            workflow = _workflow(connection, org, form, [{"action_type": MATCH}])
            submission, execution, task = uuid4(), uuid4(), uuid4()
            connection.execute(
                text(
                    "INSERT INTO form_submissions (id, organization_id, form_id, answers_json, source_mode, match_status) VALUES (:id, :org, :form, '{}'::jsonb, 'shared', 'workflow_pending')"
                ),
                {"id": submission, "org": foreign_org, "form": foreign_form},
            )
            connection.execute(
                text("""
                INSERT INTO workflow_executions (id, organization_id, workflow_id, event_id, depth,
                    event_source, entity_type, entity_id, trigger_event, matched_conditions, actions_executed,
                    status, paused_at_action_index)
                VALUES (:id, :org, :workflow, :event, 0, 'system', 'form_submission', :submission,
                    '{}'::jsonb, TRUE, '[]'::jsonb, 'paused', 0)
            """),
                {
                    "id": execution,
                    "org": foreign_org,
                    "workflow": workflow,
                    "event": uuid4(),
                    "submission": submission,
                },
            )
            connection.execute(
                text("""
                INSERT INTO tasks (id, organization_id, created_by_user_id, owner_type, owner_id,
                    title, task_type, status, workflow_execution_id, workflow_action_index, workflow_action_type)
                VALUES (:id, :org, :user, 'user', :user, 'Approval', 'workflow_approval', 'pending', :execution, 0, :action)
            """),
                {
                    "id": task,
                    "org": foreign_org,
                    "user": foreign_user,
                    "execution": execution,
                    "action": MATCH,
                },
            )
            connection.execute(
                text(
                    "UPDATE workflow_executions SET paused_task_id = :task WHERE id = :id AND organization_id = :org"
                ),
                {"id": execution, "org": foreign_org, "task": task},
            )
            command.upgrade(config, REVISION)
            assert tuple(
                connection.execute(
                    text(
                        "SELECT status, paused_task_id FROM workflow_executions WHERE id = :id AND organization_id = :org"
                    ),
                    {"id": execution, "org": foreign_org},
                ).one()
            ) == ("paused", task)
            assert (
                connection.execute(
                    text("SELECT status FROM tasks WHERE id = :id AND organization_id = :org"),
                    {"id": task, "org": foreign_org},
                ).scalar_one()
                == "pending"
            )
            assert tuple(
                connection.execute(
                    text(
                        "SELECT match_status, routing_review_step FROM form_submissions WHERE id = :id AND organization_id = :org"
                    ),
                    {"id": submission, "org": foreign_org},
                ).one()
            ) == ("workflow_pending", None)
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM tasks WHERE organization_id = :org AND task_type = 'review'"
                    ),
                    {"org": foreign_org},
                ).scalar_one()
                == 0
            )
            assert tuple(
                connection.execute(
                    text(
                        "SELECT actions, is_enabled FROM automation_workflows WHERE id = :id AND organization_id = :org"
                    ),
                    {"id": workflow, "org": org},
                ).one()
            ) == ([], False)
        finally:
            transaction.rollback()


def _config(connection):
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    config.attributes["connection"] = connection
    return config


def _paused(connection, org, user, form, workflow, action, *, match_status, status, lead=None):
    submission, execution, task = uuid4(), uuid4(), uuid4()
    connection.execute(
        text(
            "INSERT INTO form_submissions (id, organization_id, form_id, answers_json, source_mode, match_status, status, intake_lead_id) "
            "VALUES (:id, :org, :form, '{}'::jsonb, 'shared', :ms, :st, :lead)"
        ),
        {
            "id": submission,
            "org": org,
            "form": form,
            "ms": match_status,
            "st": status,
            "lead": lead,
        },
    )
    connection.execute(
        text("""
        INSERT INTO workflow_executions (id, organization_id, workflow_id, event_id, depth,
            event_source, entity_type, entity_id, subject_type, subject_id, trigger_event,
            matched_conditions, actions_executed, status, paused_at_action_index)
        VALUES (:id, :org, :workflow, :event, 0, 'system', 'form_submission', :submission,
            'form_submission', :submission, CAST(:event_data AS jsonb), TRUE, '[]'::jsonb, 'paused', 0)
    """),
        {
            "id": execution,
            "org": org,
            "workflow": workflow,
            "event": uuid4(),
            "submission": submission,
            "event_data": json.dumps({"_form_submission_workflow_actions": [action]}),
        },
    )
    connection.execute(
        text("""
        INSERT INTO tasks (id, organization_id, created_by_user_id, owner_type, owner_id,
            title, task_type, status, workflow_execution_id, workflow_action_index,
            workflow_action_type, workflow_action_payload)
        VALUES (:id, :org, :user, 'user', :user, 'Approval', 'workflow_approval', 'pending',
            :execution, 0, :action_type, CAST(:action AS jsonb))
    """),
        {
            "id": task,
            "org": org,
            "user": user,
            "execution": execution,
            "action_type": action["action_type"],
            "action": json.dumps(action),
        },
    )
    connection.execute(
        text("UPDATE workflow_executions SET paused_task_id = :task WHERE id = :id"),
        {"id": execution, "task": task},
    )
    return submission, execution, task


@pytest.fixture
def migration_connection(db_engine):
    with db_engine.connect() as connection:
        transaction = connection.begin()
        try:
            command.downgrade(_config(connection), PREVIOUS)
            yield connection
        finally:
            transaction.rollback()


def _record(connection, org, user, *, donor=False):
    pipeline, stage, record = uuid4(), uuid4(), uuid4()
    connection.execute(
        text("""
        INSERT INTO pipelines (id, organization_id, entity_type, name, is_default, current_version)
        VALUES (:id, :org, :kind, 'Applications', TRUE, 1)
    """),
        {"id": pipeline, "org": org, "kind": "egg_donor" if donor else "surrogate"},
    )
    connection.execute(
        text("""
        INSERT INTO pipeline_stages (id, pipeline_id, stage_key, slug, stage_type, label, color, "order", is_active)
        VALUES (:id, :pipeline, 'new', 'new', 'intake', 'New', '#3B82F6', 1, TRUE)
    """),
        {"id": stage, "pipeline": pipeline},
    )
    params = {"id": record, "org": org, "stage": stage, "user": user, "hash": uuid4().hex}
    if donor:
        connection.execute(
            text("""
            INSERT INTO donors (id, organization_id, donor_number, donor_type, full_name, email, email_hash, stage_id)
            VALUES (:id, :org, 'D10001', 'egg', 'Applicant', 'encrypted', :hash, :stage)
        """),
            params,
        )
    else:
        connection.execute(
            text("""
            INSERT INTO surrogates (id, organization_id, surrogate_number, stage_id, status_label,
                owner_type, owner_id, full_name, email, email_hash)
            VALUES (:id, :org, 'S10001', :stage, 'New', 'user', :user, 'Applicant', 'encrypted', :hash)
        """),
            params,
        )
    return record


@pytest.mark.parametrize("action_type", [MATCH, CREATE])
@pytest.mark.parametrize(
    "state",
    [
        "lead",
        "lead_pending",
        "rejected",
        "approved",
        "linked",
        "surrogate",
        "donor",
        "foreign_donor",
        "candidates",
        "ambiguous",
    ],
)
def test_paused_routing_preserves_resolved_submissions(
    migration_connection, action_type, state, caplog
):
    connection = migration_connection
    org, user = _org(connection)
    form = _form(connection, org, user)
    action = {"action_type": action_type, "requires_approval": True}
    workflow = _workflow(connection, org, form, [action], generated=True)
    lead = None
    if state in {"lead", "lead_pending"}:
        lead = uuid4()
        connection.execute(
            text("""
            INSERT INTO intake_leads (id, organization_id, source, lead_type, full_name, status)
            VALUES (:id, :org, 'website', 'surrogate', 'Applicant', 'pending_review')
        """),
            {"id": lead, "org": org},
        )
    match_status = (
        "lead_created" if state == "lead" else "linked" if state == "linked" else "ambiguous_review"
    )
    status = state if state in {"approved", "rejected"} else "pending_review"
    submission, execution, task = _paused(
        connection,
        org,
        user,
        form,
        workflow,
        action,
        match_status=match_status,
        status=status,
        lead=lead,
    )
    if state in {"surrogate", "donor", "foreign_donor", "candidates"}:
        record_org, record_user = _org(connection) if state == "foreign_donor" else (org, user)
        record = _record(connection, record_org, record_user, donor="donor" in state)
        if state == "candidates":
            connection.execute(
                text("""
                INSERT INTO form_submission_match_candidates (id, organization_id, submission_id, surrogate_id, reason)
                VALUES (:id, :org, :submission, :record, 'email')
            """),
                {"id": uuid4(), "org": org, "submission": submission, "record": record},
            )
        else:
            field = "donor_id" if "donor" in state else "surrogate_id"
            connection.execute(
                text(
                    f"UPDATE form_submissions SET {field} = :record WHERE organization_id = :org AND id = :id"
                ),
                {"record": record, "org": org, "id": submission},
            )
    before = (
        connection.execute(
            text("SELECT * FROM form_submissions WHERE id = :id"), {"id": submission}
        )
        .mappings()
        .one()
    )
    command.upgrade(_config(connection), REVISION)
    after = (
        connection.execute(
            text("SELECT * FROM form_submissions WHERE id = :id"), {"id": submission}
        )
        .mappings()
        .one()
    )
    eligible = state == "ambiguous" or (state == "candidates" and action_type == MATCH)
    if eligible:
        assert after["match_status"] == "routing_review"
        assert after["routing_review_step"] == ("match" if action_type == MATCH else "create_lead")
    else:
        assert dict(after) == dict(before)
    assert (
        connection.execute(
            text("SELECT status FROM workflow_executions WHERE id = :id"), {"id": execution}
        ).scalar_one()
        == "canceled"
    )
    assert (
        connection.execute(
            text("SELECT status FROM tasks WHERE id = :id"), {"id": task}
        ).scalar_one()
        == "completed"
    )
    assert connection.execute(
        text(
            "SELECT count(*) FROM tasks WHERE organization_id = :org AND form_submission_id = :id AND task_type = 'review'"
        ),
        {"org": org, "id": submission},
    ).scalar_one() == int(eligible)
    if state == "foreign_donor":
        assert "Cross-organization submission link skipped" in caplog.text
    if lead:
        # Promotion's existing bulk update must still satisfy the review-state CHECK.
        connection.execute(
            text(
                "UPDATE form_submissions SET match_status = 'linked', match_reason = 'lead_promoted_to_surrogate' WHERE organization_id = :org AND intake_lead_id = :lead"
            ),
            {"org": org, "lead": lead},
        )


@pytest.mark.parametrize(
    "status", ["partial", "failed", "success", "canceled", "running", "paused"]
)
@pytest.mark.parametrize("snapshot", [False, True])
@pytest.mark.parametrize("routing_only", [False, True])
def test_upgrade_preserves_execution_history_and_indices(
    migration_connection, status, snapshot, routing_only
):
    connection = migration_connection
    org, user = _org(connection)
    form = _form(connection, org, user, "egg_donor")
    actions = (
        [{"action_type": MATCH}, {"action_type": CREATE}]
        if routing_only
        else [{"action_type": MATCH}, NOTICE]
    )
    workflow = _workflow(connection, org, form, actions, generated=True)
    # An approval already waiting at a retained action keeps its original index.
    submission, execution, task = _paused(
        connection,
        org,
        user,
        form,
        workflow,
        NOTICE,
        match_status="linked",
        status="pending_review",
    )
    event = {"_form_submission_workflow_actions": actions} if snapshot else {}
    results = [{"success": True, "action_type": MATCH}, {"success": False, "error": "failure"}]
    connection.execute(
        text("""
        UPDATE workflow_executions SET status = :status, trigger_event = CAST(:event AS jsonb),
            actions_executed = CAST(:results AS jsonb), paused_at_action_index = 1 WHERE id = :id
    """),
        {
            "id": execution,
            "status": status,
            "event": json.dumps(event),
            "results": json.dumps(results),
        },
    )
    connection.execute(
        text("UPDATE tasks SET workflow_action_index = 1 WHERE id = :id"), {"id": task}
    )
    command.upgrade(_config(connection), REVISION)
    row = connection.execute(
        text(
            "SELECT status, trigger_event, actions_executed, paused_at_action_index, paused_task_id FROM workflow_executions WHERE id = :id"
        ),
        {"id": execution},
    ).one()
    expected_event = (
        {"_form_submission_workflow_actions": actions}
        if snapshot or status in {"running", "paused"}
        else {}
    )
    assert tuple(row) == (status, expected_event, results, 1, task)
    assert (
        connection.execute(
            text("SELECT workflow_action_index FROM tasks WHERE id = :id"), {"id": task}
        ).scalar_one()
        == 1
    )
    assert (
        connection.execute(
            text("SELECT status FROM tasks WHERE id = :id"), {"id": task}
        ).scalar_one()
        == "pending"
    )
    row = connection.execute(
        text(
            "SELECT actions, is_enabled, system_key, is_system_workflow FROM automation_workflows WHERE id = :id"
        ),
        {"id": workflow},
    ).one()
    assert tuple(row) == (
        [] if routing_only else [NOTICE],
        not routing_only,
        f"shared_intake_routing:{form}" if routing_only else None,
        routing_only,
    )


@pytest.mark.parametrize(
    "shape", ["custom", "deleted", "old_kind", "invalid", "foreign", "personal", "non_form"]
)
@pytest.mark.parametrize("kind", ["surrogate", "egg_donor", "sperm_donor"])
def test_published_unmapped_forms_stay_paused_and_invalid_routes_are_stripped(
    migration_connection, shape, kind, caplog
):
    connection = migration_connection
    org, user = _org(connection)
    form = _form(connection, org, user, kind)
    connection.execute(text("UPDATE forms SET status = 'published' WHERE id = :id"), {"id": form})
    actions = (
        [NOTICE] if shape == "custom" else [{"action_type": MATCH}, {"action_type": CREATE}, NOTICE]
    )
    target = "bad-uuid" if shape == "invalid" else form
    if shape == "foreign":
        foreign_org, foreign_user = _org(connection)
        target = _form(connection, foreign_org, foreign_user, kind)
    workflow = (
        None
        if shape == "deleted"
        else _workflow(
            connection,
            org,
            target,
            actions,
            kind=("egg_donor" if kind == "surrogate" else "surrogate")
            if shape == "old_kind"
            else kind,
            generated=shape == "old_kind",
        )
    )
    if shape == "personal":
        connection.execute(
            text(
                "UPDATE automation_workflows SET scope = 'personal', owner_user_id = :user WHERE id = :id"
            ),
            {"user": user, "id": workflow},
        )
    if shape == "non_form":
        connection.execute(
            text(
                "UPDATE automation_workflows SET subject_type = 'surrogate', trigger_type = 'surrogate_created' WHERE id = :id"
            ),
            {"id": workflow},
        )
    command.upgrade(_config(connection), REVISION)
    donor = kind != "surrogate"
    assert _settings(connection, form) == ("review", "off", "website" if donor else None, donor)
    if workflow:
        assert connection.execute(
            text("SELECT actions FROM automation_workflows WHERE id = :id"), {"id": workflow}
        ).scalar_one() == [NOTICE]
    if shape == "foreign":
        assert _settings(connection, target) == (
            ("auto", "auto", "website", True) if donor else ("review", "review", None, False)
        )
    if shape in {"old_kind", "invalid", "foreign", "personal", "non_form"}:
        assert str(workflow) in caplog.text
