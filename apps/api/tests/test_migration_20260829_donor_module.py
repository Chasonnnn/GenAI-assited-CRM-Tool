"""Deployment-safety rehearsal for removing the donor schema chain."""

from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from sqlalchemy import event, inspect, text

from alembic import command

API_ROOT = Path(__file__).resolve().parents[1]
PRE_DONOR_REVISION = "20260824_1200"


def _alembic_config(connection) -> Config:
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


@contextmanager
def _record_sql(connection):
    statements: list[str] = []

    def capture_statement(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    event.listen(connection, "before_cursor_execute", capture_statement)
    try:
        yield statements
    finally:
        event.remove(connection, "before_cursor_execute", capture_statement)


def _assert_exclusive_lock(statements: list[str], *table_names: str) -> None:
    normalized = [" ".join(statement.lower().split()) for statement in statements]
    assert any(
        statement.startswith("lock table ")
        and statement.endswith(" in exclusive mode")
        and all(table_name in statement for table_name in table_names)
        for statement in normalized
    )


def _insert_donor_fixture(connection, *, label: str) -> dict[str, UUID]:
    user_id = uuid4()
    org_id = uuid4()
    pipeline_id = uuid4()
    stage_id = uuid4()
    donor_id = uuid4()
    connection.execute(
        text("INSERT INTO users (id, email, display_name) VALUES (:id, :email, :display_name)"),
        {
            "id": user_id,
            "email": f"{label}-{uuid4().hex}@example.com",
            "display_name": f"{label} User",
        },
    )
    connection.execute(
        text("INSERT INTO organizations (id, name, slug) VALUES (:id, :name, :slug)"),
        {
            "id": org_id,
            "name": f"{label} Organization",
            "slug": f"{label.lower()}-{uuid4().hex}",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO pipelines (
                id, organization_id, entity_type, name, is_default,
                current_version, feature_config
            ) VALUES (
                :id, :organization_id, 'egg_donor', :name, TRUE,
                1, '{}'::jsonb
            )
            """
        ),
        {
            "id": pipeline_id,
            "organization_id": org_id,
            "name": f"{label} Donors",
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO pipeline_stages (
                id, pipeline_id, stage_key, slug, stage_type, label,
                color, "order", is_active, is_intake_stage
            ) VALUES (
                :id, :pipeline_id, 'new', 'new', 'intake', 'New',
                '#3B82F6', 1, TRUE, TRUE
            )
            """
        ),
        {"id": stage_id, "pipeline_id": pipeline_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO donors (
                id, organization_id, donor_number, donor_type, full_name,
                email, email_hash, stage_id, is_archived
            ) VALUES (
                :id, :organization_id, :donor_number, 'egg', :full_name,
                'encrypted-email', :email_hash, :stage_id, TRUE
            )
            """
        ),
        {
            "id": donor_id,
            "organization_id": org_id,
            "donor_number": f"D{uuid4().int % 900_000_000 + 100_000_000:09d}",
            "full_name": f"{label} Donor",
            "email_hash": uuid4().hex + uuid4().hex,
            "stage_id": stage_id,
        },
    )
    return {
        "user_id": user_id,
        "org_id": org_id,
        "pipeline_id": pipeline_id,
        "stage_id": stage_id,
        "donor_id": donor_id,
    }


def _insert_legal_hold(
    connection,
    *,
    org_id: UUID,
    entity_type: str | None,
    entity_id: UUID | None,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO legal_holds (
                organization_id, entity_type, entity_id, reason
            ) VALUES (
                :organization_id, :entity_type, :entity_id,
                'Donor migration regression hold'
            )
            """
        ),
        {
            "organization_id": org_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
        },
    )


def _insert_donor_campaign_snapshot_fixture(
    connection,
    *,
    campaign_status: str,
    run_status: str,
    recipient_status: str,
) -> dict[str, UUID]:
    org_id = uuid4()
    template_id = uuid4()
    campaign_id = uuid4()
    run_id = uuid4()
    donor_id = uuid4()
    connection.execute(
        text(
            "INSERT INTO organizations (id, name, slug) "
            "VALUES (:id, 'Campaign Snapshot Work', :slug)"
        ),
        {"id": org_id, "slug": f"campaign-snapshot-work-{uuid4().hex}"},
    )
    connection.execute(
        text(
            """
            INSERT INTO email_templates (
                id, organization_id, name, subject, body, is_active,
                current_version
            ) VALUES (
                :id, :organization_id, 'Donor work template',
                'Hello donor', '<p>Donor body</p>', TRUE, 1
            )
            """
        ),
        {"id": template_id, "organization_id": org_id},
    )
    connection.execute(
        text(
            """
            INSERT INTO campaigns (
                id, organization_id, name, channel, email_template_id,
                recipient_type, filter_criteria, status
            ) VALUES (
                :id, :organization_id, 'Donor campaign work', 'email',
                :template_id, 'egg_donor', '{}'::jsonb, :status
            )
            """
        ),
        {
            "id": campaign_id,
            "organization_id": org_id,
            "template_id": template_id,
            "status": campaign_status,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO campaign_runs (
                id, organization_id, campaign_id, status,
                total_count, sent_count, delivered_count, failed_count,
                skipped_count, opened_count, clicked_count
            ) VALUES (
                :id, :organization_id, :campaign_id, :status,
                1, 0, 0, 0, 0, 0, 0
            )
            """
        ),
        {
            "id": run_id,
            "organization_id": org_id,
            "campaign_id": campaign_id,
            "status": run_status,
        },
    )
    connection.execute(
        text(
            """
            INSERT INTO campaign_recipients (
                run_id, entity_type, entity_id, recipient_email,
                recipient_name, donor_launch_snapshot, status,
                send_revision, open_count, click_count
            ) VALUES (
                :run_id, 'egg_donor', :donor_id, 'work@example.com',
                'Work Donor', CAST(:snapshot AS jsonb), :status,
                0, 0, 0
            )
            """
        ),
        {
            "run_id": run_id,
            "donor_id": donor_id,
            "snapshot": (
                '{"version":1,"recipient_email":"work@example.com",'
                '"recipient_name":"Work Donor","subject":"Hello donor",'
                '"body":"<p>Donor body</p>"}'
            ),
            "status": recipient_status,
        },
    )
    return {
        "org_id": org_id,
        "campaign_id": campaign_id,
        "run_id": run_id,
        "donor_id": donor_id,
    }


def test_donor_module_migration_downgrades_without_residual_schema(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            command.downgrade(config, PRE_DONOR_REVISION)

            schema = inspect(connection)
            assert "donors" not in schema.get_table_names()
            assert "donor_status_history" not in schema.get_table_names()

            expected_removed_columns = {
                "tasks": {"donor_id"},
                "attachments": {"donor_id"},
                "automation_workflows": {"subject_type"},
                "workflow_executions": {"subject_type", "subject_id"},
                "meta_forms": {"lead_kind"},
                "meta_leads": {"converted_donor_id", "lead_kind"},
                "forms": {"lead_kind"},
                "published_intake_versions": {"lead_kind_snapshot"},
                "form_submissions": {"lead_kind", "donor_id"},
                "intake_leads": {"promoted_donor_id"},
                "campaign_recipients": {"donor_launch_snapshot"},
            }
            for table_name, removed_columns in expected_removed_columns.items():
                column_names = {
                    column["name"] for column in inspect(connection).get_columns(table_name)
                }
                assert column_names.isdisjoint(removed_columns)

            donor_pipeline_count = connection.scalar(
                text(
                    "SELECT count(*) FROM pipelines "
                    "WHERE entity_type IN ('egg_donor', 'sperm_donor')"
                )
            )
            donor_policy_count = connection.scalar(
                text(
                    "SELECT count(*) FROM data_retention_policies "
                    "WHERE entity_type IN ('donors', 'donor_leads')"
                )
            )
            assert donor_pipeline_count == 0
            assert donor_policy_count == 0
        finally:
            transaction.rollback()


@pytest.mark.parametrize("invalid_number", ["D10000", "D00001", "DABCDE"])
def test_donor_foundation_enforces_donor_number_floor(db_engine, invalid_number: str) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.downgrade(config, PRE_DONOR_REVISION)
            command.upgrade(config, "20260829_0100")
            fixture = _insert_donor_fixture(connection, label="Number Floor")
            savepoint = connection.begin_nested()
            try:
                with pytest.raises(Exception, match="ck_donors_number"):
                    connection.execute(
                        text(
                            """
                            INSERT INTO donors (
                                id, organization_id, donor_number, donor_type, full_name,
                                email, email_hash, stage_id, is_archived
                            ) VALUES (
                                :id, :organization_id, :donor_number, 'egg',
                                'Invalid Number Donor', 'encrypted-email', :email_hash,
                                :stage_id, TRUE
                            )
                            """
                        ),
                        {
                            "id": uuid4(),
                            "organization_id": fixture["org_id"],
                            "donor_number": invalid_number,
                            "email_hash": uuid4().hex + uuid4().hex,
                            "stage_id": fixture["stage_id"],
                        },
                    )
            finally:
                savepoint.rollback()
        finally:
            transaction.rollback()


def test_donor_foundation_downgrade_blocks_active_donor_legal_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            fixture = _insert_donor_fixture(connection, label="Foundation Hold")
            _insert_legal_hold(
                connection,
                org_id=fixture["org_id"],
                entity_type="donor",
                entity_id=fixture["donor_id"],
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="donor foundation.*legal hold"):
                    command.downgrade(config, PRE_DONOR_REVISION)
            _assert_exclusive_lock(
                statements,
                "legal_holds",
                "jobs",
                "email_deliveries",
                "message_deliveries",
            )
        finally:
            transaction.rollback()


def test_donor_task_downgrade_blocks_active_task_legal_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            fixture = _insert_donor_fixture(connection, label="Task Hold")
            task_id = uuid4()
            connection.execute(
                text(
                    """
                    INSERT INTO tasks (
                        id, organization_id, donor_id, created_by_user_id,
                        owner_type, owner_id, title
                    ) VALUES (
                        :id, :organization_id, :donor_id, :user_id,
                        'user', :user_id, 'Held donor task'
                    )
                    """
                ),
                {
                    "id": task_id,
                    "organization_id": fixture["org_id"],
                    "donor_id": fixture["donor_id"],
                    "user_id": fixture["user_id"],
                },
            )
            _insert_legal_hold(
                connection,
                org_id=fixture["org_id"],
                entity_type="task",
                entity_id=task_id,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="donor tasks.*legal hold"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(statements, "legal_holds", "tasks", "jobs")
        finally:
            transaction.rollback()


def test_donor_workflow_downgrade_blocks_canonical_note_legal_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            fixture = _insert_donor_fixture(connection, label="Workflow Note Hold")
            note_id = uuid4()
            workflow_id = uuid4()
            execution_id = uuid4()
            connection.execute(
                text(
                    """
                    INSERT INTO entity_notes (
                        id, organization_id, entity_type, entity_id, author_id, content
                    ) VALUES (
                        :id, :organization_id, 'donor', :donor_id, :user_id,
                        'Held workflow donor note'
                    )
                    """
                ),
                {
                    "id": note_id,
                    "organization_id": fixture["org_id"],
                    "donor_id": fixture["donor_id"],
                    "user_id": fixture["user_id"],
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO automation_workflows (
                        id, organization_id, name, icon, schema_version,
                        subject_type, trigger_type, trigger_config, conditions,
                        condition_logic, actions, is_enabled, run_count, scope
                    ) VALUES (
                        :id, :organization_id, 'Held donor workflow', 'workflow', 1,
                        'egg_donor', 'donor_created', '{}'::jsonb, '[]'::jsonb,
                        'AND', '[]'::jsonb, TRUE, 0, 'org'
                    )
                    """
                ),
                {"id": workflow_id, "organization_id": fixture["org_id"]},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO workflow_executions (
                        id, organization_id, workflow_id, event_id, depth,
                        event_source, entity_type, entity_id, subject_type,
                        subject_id, trigger_event, matched_conditions,
                        actions_executed, status
                    ) VALUES (
                        :id, :organization_id, :workflow_id, :event_id, 0,
                        'user', 'note', :note_id, 'egg_donor',
                        :donor_id, '{}'::jsonb, TRUE, '[]'::jsonb, 'completed'
                    )
                    """
                ),
                {
                    "id": execution_id,
                    "organization_id": fixture["org_id"],
                    "workflow_id": workflow_id,
                    "event_id": uuid4(),
                    "note_id": note_id,
                    "donor_id": fixture["donor_id"],
                },
            )
            _insert_legal_hold(
                connection,
                org_id=fixture["org_id"],
                entity_type="entity_notes",
                entity_id=note_id,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="donor workflows.*legal hold"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(
                statements,
                "legal_holds",
                "workflow_executions",
                "jobs",
                "email_deliveries",
            )
        finally:
            transaction.rollback()


def test_donor_meta_routing_downgrade_blocks_active_meta_lead_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            org_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Meta Routing Hold', :slug)"
                ),
                {"id": org_id, "slug": f"meta-routing-hold-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO meta_forms (
                        organization_id, page_id, form_external_id, form_name,
                        lead_kind, mapping_status
                    ) VALUES (
                        :organization_id, 'page-1', 'held-donor-form',
                        'Held Donor Form', 'egg_donor', 'mapped'
                    )
                    """
                ),
                {"organization_id": org_id},
            )
            meta_lead_id = connection.scalar(
                text(
                    """
                    INSERT INTO meta_leads (
                        organization_id, meta_lead_id, meta_form_id, meta_page_id
                    ) VALUES (
                        :organization_id, 'held-donor-lead',
                        'held-donor-form', 'page-1'
                    )
                    RETURNING id
                    """
                ),
                {"organization_id": org_id},
            )
            _insert_legal_hold(
                connection,
                org_id=org_id,
                entity_type="meta_lead",
                entity_id=meta_lead_id,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="donor Meta routing.*legal hold"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(
                statements,
                "legal_holds",
                "meta_forms",
                "meta_leads",
            )
        finally:
            transaction.rollback()


def test_hosted_donor_form_downgrade_blocks_active_submission_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            fixture = _insert_donor_fixture(connection, label="Submission Hold")
            form_id = uuid4()
            submission_id = uuid4()
            connection.execute(
                text(
                    """
                    INSERT INTO forms (
                        id, organization_id, name, purpose, lead_kind
                    ) VALUES (
                        :id, :organization_id, 'Held donor form',
                        'lead_capture', 'egg_donor'
                    )
                    """
                ),
                {"id": form_id, "organization_id": fixture["org_id"]},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO form_submissions (
                        id, organization_id, form_id, donor_id, lead_kind,
                        answers_json
                    ) VALUES (
                        :id, :organization_id, :form_id, :donor_id,
                        'egg_donor', '{}'::jsonb
                    )
                    """
                ),
                {
                    "id": submission_id,
                    "organization_id": fixture["org_id"],
                    "form_id": form_id,
                    "donor_id": fixture["donor_id"],
                },
            )
            _insert_legal_hold(
                connection,
                org_id=fixture["org_id"],
                entity_type="form_submission",
                entity_id=submission_id,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="hosted donor forms.*legal hold"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(
                statements,
                "legal_holds",
                "forms",
                "form_submissions",
                "form_submission_files",
            )
        finally:
            transaction.rollback()


def test_donor_meta_snapshot_downgrade_blocks_active_meta_lead_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            org_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Meta Snapshot Hold', :slug)"
                ),
                {"id": org_id, "slug": f"meta-snapshot-hold-{uuid4().hex}"},
            )
            meta_lead_id = connection.scalar(
                text(
                    """
                    INSERT INTO meta_leads (
                        organization_id, meta_lead_id, meta_page_id, lead_kind
                    ) VALUES (
                        :organization_id, 'held-snapshot-lead',
                        'page-1', 'sperm_donor'
                    )
                    RETURNING id
                    """
                ),
                {"organization_id": org_id},
            )
            _insert_legal_hold(
                connection,
                org_id=org_id,
                entity_type="meta_lead",
                entity_id=meta_lead_id,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="donor Meta snapshots.*legal hold"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(statements, "legal_holds", "meta_leads")
        finally:
            transaction.rollback()


def test_donor_campaign_snapshot_downgrade_blocks_active_donor_hold(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            org_id = uuid4()
            donor_id = uuid4()
            template_id = uuid4()
            campaign_id = uuid4()
            run_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Campaign Snapshot Hold', :slug)"
                ),
                {"id": org_id, "slug": f"campaign-snapshot-hold-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO email_templates (
                        id, organization_id, name, subject, body, is_active,
                        current_version
                    ) VALUES (
                        :id, :organization_id, 'Donor snapshot template',
                        'Hello donor', '<p>Donor body</p>', TRUE, 1
                    )
                    """
                ),
                {"id": template_id, "organization_id": org_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaigns (
                        id, organization_id, name, channel, email_template_id,
                        recipient_type, filter_criteria, status
                    ) VALUES (
                        :id, :organization_id, 'Held donor campaign', 'email',
                        :template_id, 'egg_donor', '{}'::jsonb, 'failed'
                    )
                    """
                ),
                {
                    "id": campaign_id,
                    "organization_id": org_id,
                    "template_id": template_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_runs (
                        id, organization_id, campaign_id, status,
                        total_count, sent_count, delivered_count, failed_count,
                        skipped_count, opened_count, clicked_count
                    ) VALUES (
                        :id, :organization_id, :campaign_id, 'failed',
                        1, 0, 0, 1, 0, 0, 0
                    )
                    """
                ),
                {
                    "id": run_id,
                    "organization_id": org_id,
                    "campaign_id": campaign_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_recipients (
                        run_id, entity_type, entity_id, recipient_email,
                        recipient_name, donor_launch_snapshot, status,
                        send_revision, open_count, click_count
                    ) VALUES (
                        :run_id, 'egg_donor', :donor_id, 'held@example.com',
                        'Held Donor',
                        CAST(:snapshot AS jsonb),
                        'failed', 0, 0, 0
                    )
                    """
                ),
                {
                    "run_id": run_id,
                    "donor_id": donor_id,
                    "snapshot": (
                        '{"version":1,"recipient_email":"held@example.com",'
                        '"recipient_name":"Held Donor","subject":"Hello donor",'
                        '"body":"<p>Donor body</p>"}'
                    ),
                },
            )
            _insert_legal_hold(
                connection,
                org_id=org_id,
                entity_type="donor",
                entity_id=donor_id,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="launch snapshots.*legal hold"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(
                statements,
                "legal_holds",
                "campaign_runs",
                "campaign_recipients",
            )
        finally:
            transaction.rollback()


@pytest.mark.parametrize(
    ("campaign_status", "run_status", "recipient_status"),
    [
        ("sending", "running", "delivered"),
        ("failed", "failed", "pending"),
        ("failed", "failed", "failed"),
    ],
)
def test_donor_campaign_snapshot_downgrade_blocks_active_or_retryable_work(
    db_engine,
    campaign_status: str,
    run_status: str,
    recipient_status: str,
) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            _insert_donor_campaign_snapshot_fixture(
                connection,
                campaign_status=campaign_status,
                run_status=run_status,
                recipient_status=recipient_status,
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="campaign work is active or retryable"):
                    command.downgrade(config, "20260824_1200")
            _assert_exclusive_lock(
                statements,
                "campaigns",
                "campaign_runs",
                "campaign_recipients",
            )
        finally:
            transaction.rollback()


def test_donor_campaign_snapshot_downgrade_allows_terminal_unheld_work(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            _insert_donor_campaign_snapshot_fixture(
                connection,
                campaign_status="completed",
                run_status="completed",
                recipient_status="delivered",
            )

            command.downgrade(config, "20260824_1200")

            assert "donor_launch_snapshot" not in {
                column["name"] for column in inspect(connection).get_columns("campaign_recipients")
            }
        finally:
            transaction.rollback()


def test_donor_campaign_downgrade_blocks_leased_message_delivery(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            org_id = uuid4()
            settings_id = uuid4()
            route_id = uuid4()
            contact_id = uuid4()
            conversation_id = uuid4()
            message_id = uuid4()
            delivery_id = uuid4()
            template_id = uuid4()
            campaign_id = uuid4()
            run_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Leased Message Rollback', :slug)"
                ),
                {"id": org_id, "slug": f"leased-message-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    "INSERT INTO twilio_settings (id, organization_id) "
                    "VALUES (:id, :organization_id)"
                ),
                {"id": settings_id, "organization_id": org_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO twilio_routes (
                        id, settings_id, organization_id, purpose
                    ) VALUES (
                        :id, :settings_id, :organization_id, 'operational'
                    )
                    """
                ),
                {
                    "id": route_id,
                    "settings_id": settings_id,
                    "organization_id": org_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO messaging_contacts (
                        id, organization_id, phone_e164, phone_hash, phone_last4
                    ) VALUES (
                        :id, :organization_id, 'encrypted-phone', :phone_hash, '0123'
                    )
                    """
                ),
                {
                    "id": contact_id,
                    "organization_id": org_id,
                    "phone_hash": "a" * 64,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO messaging_conversations (
                        id, organization_id, contact_id, route_id
                    ) VALUES (
                        :id, :organization_id, :contact_id, :route_id
                    )
                    """
                ),
                {
                    "id": conversation_id,
                    "organization_id": org_id,
                    "contact_id": contact_id,
                    "route_id": route_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO messages (
                        id, organization_id, conversation_id, contact_id, route_id,
                        purpose, direction, body_encrypted, from_phone_hash,
                        from_phone_last4, to_phone_hash, to_phone_last4
                    ) VALUES (
                        :id, :organization_id, :conversation_id, :contact_id, :route_id,
                        'operational', 'outbound', 'encrypted-message', :from_hash,
                        '0900', :to_hash, '0123'
                    )
                    """
                ),
                {
                    "id": message_id,
                    "organization_id": org_id,
                    "conversation_id": conversation_id,
                    "contact_id": contact_id,
                    "route_id": route_id,
                    "from_hash": "b" * 64,
                    "to_hash": "a" * 64,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO message_deliveries (
                        id, organization_id, message_id, contact_id, route_id,
                        purpose, source_type, idempotency_key, payload_fingerprint,
                        status, attempt_count, max_attempts, lease_token,
                        lease_owner, lease_expires_at
                    ) VALUES (
                        :id, :organization_id, :message_id, :contact_id, :route_id,
                        'operational', 'campaign', :idempotency_key, :fingerprint,
                        'leased', 1, 5, :lease_token,
                        'migration-message-race-test', now() + interval '5 minutes'
                    )
                    """
                ),
                {
                    "id": delivery_id,
                    "organization_id": org_id,
                    "message_id": message_id,
                    "contact_id": contact_id,
                    "route_id": route_id,
                    "idempotency_key": f"migration-message-lease/{message_id}",
                    "fingerprint": "c" * 64,
                    "lease_token": uuid4(),
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO message_templates (
                        id, organization_id, template_key, version, name, purpose,
                        body_encrypted, content_hash, status
                    ) VALUES (
                        :id, :organization_id, :template_key, 1,
                        'Donor rollback template', 'operational',
                        'encrypted-template', :content_hash, 'published'
                    )
                    """
                ),
                {
                    "id": template_id,
                    "organization_id": org_id,
                    "template_key": uuid4(),
                    "content_hash": "d" * 64,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaigns (
                        id, organization_id, name, channel,
                        message_template_version_id, recipient_type,
                        filter_criteria, status
                    ) VALUES (
                        :id, :organization_id, 'Leased donor message campaign',
                        'messaging', :template_id, 'egg_donor', '{}'::jsonb, 'sending'
                    )
                    """
                ),
                {
                    "id": campaign_id,
                    "organization_id": org_id,
                    "template_id": template_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_runs (
                        id, organization_id, campaign_id, status,
                        message_template_version_id, total_count, sent_count,
                        delivered_count, failed_count, skipped_count,
                        opened_count, clicked_count
                    ) VALUES (
                        :id, :organization_id, :campaign_id, 'running',
                        :template_id, 1, 0, 0, 0, 0, 0, 0
                    )
                    """
                ),
                {
                    "id": run_id,
                    "organization_id": org_id,
                    "campaign_id": campaign_id,
                    "template_id": template_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO campaign_recipients (
                        run_id, entity_type, entity_id, recipient_phone_last4,
                        status, message_delivery_id, send_revision,
                        open_count, click_count
                    ) VALUES (
                        :run_id, 'egg_donor', :entity_id, '0123',
                        'pending', :delivery_id, 0, 0, 0
                    )
                    """
                ),
                {
                    "run_id": run_id,
                    "entity_id": uuid4(),
                    "delivery_id": delivery_id,
                },
            )

            with _record_sql(connection) as statements:
                with pytest.raises(Exception, match="donor message delivery is leased"):
                    command.downgrade(config, PRE_DONOR_REVISION)
            _assert_exclusive_lock(
                statements,
                "jobs",
                "message_deliveries",
                "campaign_recipients",
            )
        finally:
            transaction.rollback()


def test_donor_workflow_downgrade_blocks_leased_email_delivery(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            org_id = uuid4()
            job_id = uuid4()
            email_log_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Leased Email Rollback', :slug)"
                ),
                {"id": org_id, "slug": f"leased-email-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id, organization_id, job_type, payload, status
                    ) VALUES (
                        :id, :org_id, 'workflow_email',
                        jsonb_build_object(
                            'subject_type', 'egg_donor',
                            'subject_id', CAST(:subject_id AS text)
                        ),
                        'pending'
                    )
                    """
                ),
                {"id": job_id, "org_id": org_id, "subject_id": str(uuid4())},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO email_logs (
                        id, organization_id, job_id, recipient_email,
                        subject, body, status, source_type, source_id
                    ) VALUES (
                        :id, :org_id, :job_id, 'donor@example.com',
                        'Donor email', '<p>Donor email</p>', 'pending',
                        'workflow_job', :job_id
                    )
                    """
                ),
                {"id": email_log_id, "org_id": org_id, "job_id": job_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO email_deliveries (
                        organization_id, email_log_id, provider, provider_scope,
                        provider_account_id, idempotency_key, request_fingerprint,
                        status, attempt_count, max_attempts, lease_token,
                        lease_owner, lease_expires_at
                    ) VALUES (
                        :org_id, :email_log_id, 'resend', 'organization',
                        :provider_account_id, :idempotency_key, :fingerprint,
                        'leased', 1, 5, :lease_token,
                        'migration-race-test', now() + interval '5 minutes'
                    )
                    """
                ),
                {
                    "org_id": org_id,
                    "email_log_id": email_log_id,
                    "provider_account_id": f"organization:{org_id}",
                    "idempotency_key": f"migration-lease/{email_log_id}",
                    "fingerprint": "e" * 64,
                    "lease_token": uuid4(),
                },
            )

            with pytest.raises(Exception, match="donor email delivery is leased"):
                command.downgrade(config, "20260824_1200")
        finally:
            transaction.rollback()


def test_donor_task_downgrade_blocks_synced_google_task_erasure(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            org_id = uuid4()
            user_id = uuid4()
            pipeline_id = uuid4()
            stage_id = uuid4()
            donor_id = uuid4()
            task_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name) "
                    "VALUES (:id, :email, 'Google Rollback User')"
                ),
                {"id": user_id, "email": f"google-rollback-{uuid4().hex}@example.com"},
            )
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Google Rollback Organization', :slug)"
                ),
                {"id": org_id, "slug": f"google-rollback-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pipelines (
                        id, organization_id, entity_type, name, is_default,
                        current_version, feature_config
                    ) VALUES (
                        :id, :organization_id, 'egg_donor', 'Google Rollback Donors',
                        TRUE, 1, '{}'::jsonb
                    )
                    """
                ),
                {"id": pipeline_id, "organization_id": org_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pipeline_stages (
                        id, pipeline_id, stage_key, slug, stage_type, label,
                        color, "order", is_active, is_intake_stage
                    ) VALUES (
                        :id, :pipeline_id, 'new', 'new', 'intake', 'New',
                        '#3B82F6', 1, TRUE, TRUE
                    )
                    """
                ),
                {"id": stage_id, "pipeline_id": pipeline_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO donors (
                        id, organization_id, donor_number, donor_type, full_name,
                        email, email_hash, stage_id, is_archived
                    ) VALUES (
                        :id, :organization_id, 'D99003', 'egg',
                        'Google Rollback Donor', 'encrypted-email', :email_hash,
                        :stage_id, TRUE
                    )
                    """
                ),
                {
                    "id": donor_id,
                    "organization_id": org_id,
                    "email_hash": uuid4().hex + uuid4().hex,
                    "stage_id": stage_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO tasks (
                        id, organization_id, donor_id, created_by_user_id,
                        owner_type, owner_id, title, google_task_id,
                        google_task_list_id
                    ) VALUES (
                        :id, :organization_id, :donor_id, :user_id,
                        'user', :user_id, 'Synced rollback donor task',
                        'remote-task-1', 'remote-list-1'
                    )
                    """
                ),
                {
                    "id": task_id,
                    "organization_id": org_id,
                    "donor_id": donor_id,
                    "user_id": user_id,
                },
            )

            with pytest.raises(RuntimeError, match="Google-synced donor tasks remain"):
                command.downgrade(config, "20260824_1200")

            assert "donor_id" in {
                column["name"] for column in inspect(connection).get_columns("tasks")
            }
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM tasks WHERE id = :id"),
                    {"id": task_id},
                )
                == 1
            )
        finally:
            transaction.rollback()


@pytest.mark.parametrize("job_status", ["pending", "running", "failed"])
def test_donor_task_downgrade_blocks_unresolved_google_cleanup_jobs(
    db_engine,
    job_status,
) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "20260829_0100")
            org_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Google Cleanup Rollback', :slug)"
                ),
                {"id": org_id, "slug": f"google-cleanup-rollback-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO jobs (
                        organization_id, job_type, payload, status
                    ) VALUES (
                        :organization_id, 'google_task_remote_delete',
                        jsonb_build_object(
                            'user_id', CAST(:user_id AS text),
                            'google_task_id', 'orphaned-remote-task',
                            'google_task_list_id', 'orphaned-list'
                        ),
                        :status
                    )
                    """
                ),
                {
                    "organization_id": org_id,
                    "user_id": str(uuid4()),
                    "status": job_status,
                },
            )

            with pytest.raises(RuntimeError, match="Google task cleanup jobs remain unresolved"):
                command.downgrade(config, "20260824_1200")

            assert "donor_id" in {
                column["name"] for column in inspect(connection).get_columns("tasks")
            }
        finally:
            transaction.rollback()


def test_populated_donor_module_downgrade_removes_derived_task_and_note_pii(db_engine) -> None:
    with db_engine.connect() as connection:
        transaction = connection.begin()
        config = _alembic_config(connection)
        try:
            command.upgrade(config, "head")
            org_id = uuid4()
            user_id = uuid4()
            pipeline_id = uuid4()
            stage_id = uuid4()
            donor_id = uuid4()
            task_id = uuid4()
            notification_id = uuid4()
            note_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name) "
                    "VALUES (:id, :email, 'Rollback User')"
                ),
                {"id": user_id, "email": f"rollback-{uuid4().hex}@example.com"},
            )
            connection.execute(
                text(
                    "INSERT INTO organizations (id, name, slug) "
                    "VALUES (:id, 'Rollback Organization', :slug)"
                ),
                {"id": org_id, "slug": f"rollback-{uuid4().hex}"},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pipelines (
                        id, organization_id, entity_type, name, is_default,
                        current_version, feature_config
                    ) VALUES (
                        :id, :organization_id, 'egg_donor', 'Rollback Donors', TRUE,
                        1, '{}'::jsonb
                    )
                    """
                ),
                {"id": pipeline_id, "organization_id": org_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO pipeline_stages (
                        id, pipeline_id, stage_key, slug, stage_type, label,
                        color, "order", is_active, is_intake_stage
                    ) VALUES (
                        :id, :pipeline_id, 'new', 'new', 'intake', 'New',
                        '#3B82F6', 1, TRUE, TRUE
                    )
                    """
                ),
                {"id": stage_id, "pipeline_id": pipeline_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO donors (
                        id, organization_id, donor_number, donor_type, full_name,
                        email, email_hash, stage_id, is_archived
                    ) VALUES (
                        :id, :organization_id, 'D99002', 'egg', 'Rollback Donor',
                        'encrypted-email', :email_hash, :stage_id, TRUE
                    )
                    """
                ),
                {
                    "id": donor_id,
                    "organization_id": org_id,
                    "email_hash": uuid4().hex + uuid4().hex,
                    "stage_id": stage_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO tasks (
                        id, organization_id, donor_id, created_by_user_id,
                        owner_type, owner_id, title
                    ) VALUES (
                        :id, :organization_id, :donor_id, :user_id,
                        'user', :user_id, 'Rollback donor task'
                    )
                    """
                ),
                {
                    "id": task_id,
                    "organization_id": org_id,
                    "donor_id": donor_id,
                    "user_id": user_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO notifications (
                        id, organization_id, user_id, type, title, entity_type, entity_id
                    ) VALUES (
                        :id, :organization_id, :user_id, 'task_assigned',
                        'Rollback donor task', 'task', :task_id
                    )
                    """
                ),
                {
                    "id": notification_id,
                    "organization_id": org_id,
                    "user_id": user_id,
                    "task_id": task_id,
                },
            )
            connection.execute(
                text(
                    """
                    INSERT INTO entity_notes (
                        id, organization_id, entity_type, entity_id, author_id, content
                    ) VALUES (
                        :id, :organization_id, 'donor', :donor_id, :user_id,
                        'Rollback donor note'
                    )
                    """
                ),
                {
                    "id": note_id,
                    "organization_id": org_id,
                    "donor_id": donor_id,
                    "user_id": user_id,
                },
            )

            command.downgrade(config, PRE_DONOR_REVISION)

            assert (
                connection.scalar(
                    text("SELECT count(*) FROM notifications WHERE id = :id"),
                    {"id": notification_id},
                )
                == 0
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM entity_notes WHERE id = :id"),
                    {"id": note_id},
                )
                == 0
            )
            assert "donors" not in inspect(connection).get_table_names()
        finally:
            transaction.rollback()
