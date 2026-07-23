"""Tests for Resend webhook handler."""

import base64
import hashlib
import hmac
import time
import uuid

import pytest
from sqlalchemy import event


async def _post_signed_resend_event(
    client,
    *,
    webhook_id: str,
    webhook_secret: str,
    payload: dict,
):
    import json

    body = json.dumps(payload).encode("utf-8")
    timestamp = str(int(time.time()))
    msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
    response = await client.post(
        f"/webhooks/resend/{webhook_id}",
        content=body,
        headers={
            "Content-Type": "application/json",
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": signature,
        },
    )
    return response


def _queue_claimed_resend_delivery(db, organization_id, *, claimed_at):
    from datetime import timedelta

    from app.services.email_delivery_service import (
        DeliveryRoute,
        EmailSource,
        RenderedEmail,
        claim_due_deliveries,
        queue_rendered_email,
    )

    queued = queue_rendered_email(
        db,
        organization_id=organization_id,
        route=DeliveryRoute.ORGANIZATION_RESEND,
        provider_account_id=f"organization:{organization_id}",
        rendered_email=RenderedEmail(
            recipient_email="race@recipient.com",
            subject="Provider chronology",
            html="<p>Provider chronology</p>",
            text="Provider chronology",
            from_email="Surrogacy Force <care@example.com>",
        ),
        idempotency_key=f"provider-chronology/{uuid.uuid4()}",
        source=EmailSource(source_type="test"),
        schedule_at=claimed_at - timedelta(seconds=1),
        commit=False,
    )
    claim = claim_due_deliveries(
        db,
        worker_id="worker-a",
        now=claimed_at,
        lease_for=timedelta(minutes=2),
        limit=1,
    )[0]
    return queued, claim


def _generate_svix_signature(body: bytes, secret: str, timestamp: str) -> str:
    """Generate a valid Svix signature for testing."""
    msg_id = str(uuid.uuid4())
    signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"

    def _pad_b64(value: str) -> str:
        return value + "=" * (-len(value) % 4)

    # Handle whsec_ prefix (Svix uses base64 urlsafe)
    if secret.startswith("whsec_"):
        secret = secret[6:]
        try:
            secret_bytes = base64.urlsafe_b64decode(_pad_b64(secret))
        except Exception:
            secret_bytes = secret.encode("utf-8")
    else:
        try:
            secret_bytes = base64.b64decode(secret)
        except Exception:
            secret_bytes = secret.encode("utf-8")

    signature = hmac.new(
        secret_bytes,
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return msg_id, f"v1,{signature_b64}"


def _create_surrogate_for_email_activity(db, test_org, test_user, default_stage):
    from app.core.encryption import hash_email
    from app.db.enums import OwnerType
    from app.db.models import Surrogate
    from app.utils.normalization import normalize_email

    normalized_email = normalize_email(f"bounce-{uuid.uuid4().hex[:8]}@example.com")
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=test_org.id,
        surrogate_number=f"S{uuid.uuid4().hex[:5]}",
        stage_id=default_stage.id,
        status_label=default_stage.label,
        owner_type=OwnerType.USER.value,
        owner_id=test_user.id,
        full_name="Bounce Activity Surrogate",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
        created_by_user_id=test_user.id,
    )
    db.add(surrogate)
    db.flush()
    return surrogate


class TestResendWebhookSignature:
    """Test signature verification."""

    def test_verify_svix_signature_valid(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        secret = "test_secret_key_for_testing"
        timestamp = str(int(time.time()))

        msg_id, signature = _generate_svix_signature(body, secret, timestamp)

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": signature,
        }

        is_valid = _verify_svix_signature(body, headers, secret)
        assert is_valid is True

    def test_verify_svix_signature_invalid(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        timestamp = str(int(time.time()))

        headers = {
            "svix-id": str(uuid.uuid4()),
            "svix-timestamp": timestamp,
            "svix-signature": "v1,invalid_signature",
        }

        is_valid = _verify_svix_signature(body, headers, "correct_secret")
        assert is_valid is False

    def test_verify_svix_signature_missing_headers(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'

        # Missing svix-id
        headers = {
            "svix-timestamp": str(int(time.time())),
            "svix-signature": "v1,signature",
        }

        is_valid = _verify_svix_signature(body, headers, "secret")
        assert is_valid is False

    def test_verify_svix_signature_rejects_stale_timestamp(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        secret = "test_secret_key_for_testing"
        stale_timestamp = str(int(time.time()) - 3600)

        msg_id, signature = _generate_svix_signature(body, secret, stale_timestamp)

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": stale_timestamp,
            "svix-signature": signature,
        }

        is_valid = _verify_svix_signature(body, headers, secret)
        assert is_valid is False

    def test_verify_svix_signature_rejects_malformed_whsec_secret(self):
        from app.services.webhooks.resend import _verify_svix_signature

        body = b'{"type": "email.delivered", "data": {}}'
        malformed_secret = "whsec_invalid@secret!!"
        timestamp = str(int(time.time()))
        msg_id = str(uuid.uuid4())

        # Signature generated with raw malformed secret bytes (legacy/fail-open behavior).
        signed_payload = f"{msg_id}.{timestamp}.{body.decode('utf-8')}"
        raw_secret_bytes = malformed_secret.removeprefix("whsec_").encode("utf-8")
        signature = base64.b64encode(
            hmac.new(
                raw_secret_bytes,
                signed_payload.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        ).decode("utf-8")

        headers = {
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": f"v1,{signature}",
        }

        is_valid = _verify_svix_signature(body, headers, malformed_secret)
        assert is_valid is False


class TestResendWebhookHandler:
    """Test webhook event processing."""

    @pytest.fixture
    def setup_email_log(self, db, test_org):
        """Create an EmailLog for testing webhook events."""
        import base64

        from app.db.models import EmailLog
        from app.db.enums import EmailStatus
        from app.services import resend_settings_service

        # Create Resend settings
        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )
        webhook_secret_bytes = b"test_webhook_secret_for_resend"
        webhook_secret = "whsec_" + base64.urlsafe_b64encode(webhook_secret_bytes).decode(
            "utf-8"
        ).rstrip("=")
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            email_provider="resend",
            api_key="re_test_key",
            from_email="no-reply@example.com",
            verified_domain="example.com",
            webhook_signing_secret=webhook_secret,
        )

        db.refresh(settings)

        # Create an EmailLog
        email_log = EmailLog(
            organization_id=test_org.id,
            recipient_email="test@recipient.com",
            subject="Test Email",
            body="<p>Test body</p>",
            status=EmailStatus.SENT.value,
            external_id="resend_msg_123",  # Resend message ID
        )
        db.add(email_log)
        db.commit()
        db.refresh(email_log)

        return email_log, settings, webhook_secret

    @pytest.mark.asyncio
    async def test_webhook_unknown_webhook_id(self, db, test_org, client):
        """Test that unknown webhook IDs are silently accepted."""
        from app.services import resend_settings_service

        # Create settings to ensure they exist
        resend_settings_service.get_or_create_resend_settings(db, test_org.id, test_org.id)

        payload = {"type": "email.delivered", "data": {"email_id": "msg_123"}}

        response = await client.post(
            "/webhooks/resend/invalid-webhook-id",
            json=payload,
        )

        # Should return 200 even for invalid webhook ID
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_resend_webhook_admission_allows_provider_burst(self, client):
        """A normal provider burst must not inherit the low generic webhook ceiling."""
        responses = [
            await client.post(
                "/webhooks/resend/provider-burst",
                json={"type": "email.sent", "data": {"email_id": f"msg-{index}"}},
            )
            for index in range(101)
        ]

        assert all(response.status_code == 200 for response in responses)

    @pytest.mark.asyncio
    async def test_webhook_delivered_event(self, db, test_org, client, setup_email_log):
        """Test that delivered events update EmailLog."""
        import json

        email_log, settings, webhook_secret = setup_email_log

        payload = {
            "type": "email.delivered",
            "data": {"email_id": email_log.external_id},
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        # Refresh and check status
        db.refresh(email_log)
        assert email_log.resend_status == "delivered"
        assert email_log.delivered_at is not None

    @pytest.mark.asyncio
    async def test_webhook_rejects_missing_signature_when_secret_configured(
        self, db, test_org, client, setup_email_log
    ):
        """If a signing secret is configured, requests without Svix headers must be rejected."""
        import json

        email_log, settings, _webhook_secret = setup_email_log

        payload = {
            "type": "email.delivered",
            "data": {"email_id": email_log.external_id},
        }
        body = json.dumps(payload).encode("utf-8")

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_webhook_rejects_processing_when_signing_secret_is_not_configured(
        self, db, test_org, client
    ):
        """An unguessable URL is not a substitute for Svix signature verification."""
        from app.services import resend_settings_service

        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            json={"type": "email.delivered", "data": {"email_id": "msg_123"}},
        )

        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_webhook_delivered_updates_campaign_run_counts(
        self, db, test_org, test_user, client, setup_email_log
    ):
        """Delivered webhook should update campaign recipient + run delivered_count."""
        import json
        from uuid import uuid4

        from app.db.enums import CampaignStatus
        from app.db.models import Campaign, CampaignRun, CampaignRecipient, EmailTemplate

        email_log, settings, webhook_secret = setup_email_log

        template = EmailTemplate(
            id=uuid4(),
            organization_id=test_org.id,
            name="Webhook Campaign Template",
            subject="Hello",
            body="<p>Test body</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()

        campaign = Campaign(
            id=uuid4(),
            organization_id=test_org.id,
            name="Webhook Campaign",
            email_template_id=template.id,
            recipient_type="case",
            filter_criteria={},
            status="sending",
            created_by_user_id=test_user.id,
        )
        db.add(campaign)
        db.flush()

        run = CampaignRun(
            id=uuid4(),
            organization_id=test_org.id,
            campaign_id=campaign.id,
            status="running",
            total_count=1,
            sent_count=1,
            failed_count=0,
            skipped_count=0,
            opened_count=0,
            clicked_count=0,
        )
        db.add(run)
        db.flush()

        recipient = CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="test@recipient.com",
            status="sent",
            email_log_id=email_log.id,
            external_message_id=email_log.external_id,
        )
        db.add(recipient)
        db.commit()

        payload = {
            "type": "email.delivered",
            "data": {"email_id": email_log.external_id},
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
        statements: list[str] = []

        def capture_sql(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        engine = db.get_bind()
        event.listen(engine, "before_cursor_execute", capture_sql)
        try:
            response = await client.post(
                f"/webhooks/resend/{settings.webhook_id}",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "svix-id": msg_id,
                    "svix-timestamp": timestamp,
                    "svix-signature": signature,
                },
            )
        finally:
            event.remove(engine, "before_cursor_execute", capture_sql)

        assert response.status_code == 200
        locking_selects = [
            statement.lower() for statement in statements if "for update" in statement.lower()
        ]
        run_lock_index = next(
            index
            for index, statement in enumerate(locking_selects)
            if "from campaign_runs" in statement
        )
        campaign_lock_index = next(
            index
            for index, statement in enumerate(locking_selects)
            if "from campaigns" in statement
        )
        email_lock_index = next(
            index
            for index, statement in enumerate(locking_selects)
            if "from email_logs" in statement
        )
        assert run_lock_index < campaign_lock_index < email_lock_index

        db.refresh(recipient)
        db.refresh(run)
        db.refresh(campaign)
        assert recipient.status == "delivered"
        assert run.delivered_count == 1
        assert run.sent_count == 1
        assert run.status == "completed"
        assert run.completed_at is not None
        assert campaign.status == CampaignStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_webhook_engagement_updates_campaign_run_counts(
        self, db, test_org, test_user, client, setup_email_log
    ):
        """First open and click events must be visible in campaign aggregates immediately."""
        import json
        from uuid import uuid4

        from app.db.models import Campaign, CampaignRecipient, CampaignRun, EmailTemplate

        email_log, settings, webhook_secret = setup_email_log
        template = EmailTemplate(
            id=uuid4(),
            organization_id=test_org.id,
            name="Webhook Engagement Template",
            subject="Hello",
            body="<p>Test body</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()
        campaign = Campaign(
            id=uuid4(),
            organization_id=test_org.id,
            name="Webhook Engagement Campaign",
            email_template_id=template.id,
            recipient_type="case",
            filter_criteria={},
            status="sending",
            created_by_user_id=test_user.id,
        )
        db.add(campaign)
        db.flush()
        run = CampaignRun(
            id=uuid4(),
            organization_id=test_org.id,
            campaign_id=campaign.id,
            status="running",
            total_count=1,
            sent_count=1,
            failed_count=0,
            skipped_count=0,
            opened_count=0,
            clicked_count=0,
        )
        db.add(run)
        db.flush()
        recipient = CampaignRecipient(
            id=uuid4(),
            run_id=run.id,
            entity_type="case",
            entity_id=uuid4(),
            recipient_email="test@recipient.com",
            status="sent",
            email_log_id=email_log.id,
            external_message_id=email_log.external_id,
        )
        db.add(recipient)
        db.commit()

        async def post_event(event_type: str, created_at: str):
            payload = {
                "type": event_type,
                "created_at": created_at,
                "data": {"email_id": email_log.external_id},
            }
            body = json.dumps(payload).encode("utf-8")
            timestamp = str(int(time.time()))
            msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
            return await client.post(
                f"/webhooks/resend/{settings.webhook_id}",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "svix-id": msg_id,
                    "svix-timestamp": timestamp,
                    "svix-signature": signature,
                },
            )

        opened = await post_event("email.opened", "2026-07-21T14:04:00.000Z")
        clicked = await post_event("email.clicked", "2026-07-21T14:05:00.000Z")

        assert opened.status_code == 200
        assert clicked.status_code == 200
        db.refresh(email_log)
        db.refresh(recipient)
        db.refresh(run)
        assert email_log.open_count == 1
        assert email_log.click_count == 1
        assert recipient.open_count == 1
        assert recipient.click_count == 1
        assert run.opened_count == 1
        assert run.clicked_count == 1

    @pytest.mark.asyncio
    async def test_webhook_bounced_hard_adds_suppression(
        self, db, test_org, client, setup_email_log
    ):
        """Test that hard bounces add email to suppression list."""
        import json
        from app.db.models import EmailSuppression

        email_log, settings, webhook_secret = setup_email_log

        payload = {
            "type": "email.bounced",
            "data": {
                "email_id": email_log.external_id,
                "bounce": {"type": "hard"},
            },
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        # Check suppression was added
        suppression = (
            db.query(EmailSuppression)
            .filter(
                EmailSuppression.organization_id == test_org.id,
                EmailSuppression.email == email_log.recipient_email.lower(),
            )
            .first()
        )
        assert suppression is not None
        assert suppression.reason == "bounced"

    @pytest.mark.asyncio
    async def test_webhook_bounced_logs_surrogate_activity_event(
        self, db, test_org, test_user, default_stage, client, setup_email_log
    ):
        """Bounced event should append an email_bounced activity for linked surrogates."""
        import json
        from app.db.enums import SurrogateActivityType
        from app.db.models import SurrogateActivityLog

        email_log, settings, webhook_secret = setup_email_log
        surrogate = _create_surrogate_for_email_activity(db, test_org, test_user, default_stage)
        email_log.surrogate_id = surrogate.id
        db.commit()

        payload = {
            "type": "email.bounced",
            "data": {
                "email_id": email_log.external_id,
                "bounce": {"type": "hard"},
            },
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )
        assert response.status_code == 200

        activity = (
            db.query(SurrogateActivityLog)
            .filter(
                SurrogateActivityLog.organization_id == test_org.id,
                SurrogateActivityLog.surrogate_id == surrogate.id,
                SurrogateActivityLog.activity_type == SurrogateActivityType.EMAIL_BOUNCED.value,
                SurrogateActivityLog.details["email_log_id"].astext == str(email_log.id),
            )
            .first()
        )

        assert activity is not None
        assert activity.details.get("provider") == "resend"
        assert activity.details.get("reason") == "bounced"
        assert activity.details.get("bounce_type") == "hard"

    @pytest.mark.asyncio
    async def test_webhook_bounced_downgrades_workflow_execution_status(
        self, db, test_org, test_user, client, setup_email_log
    ):
        """Bounced workflow email should downgrade execution status from success."""
        import json
        from uuid import uuid4

        from app.db.enums import JobStatus, JobType, WorkflowEventSource, WorkflowExecutionStatus
        from app.db.models import AutomationWorkflow, Job, WorkflowExecution

        email_log, settings, webhook_secret = setup_email_log

        workflow = AutomationWorkflow(
            id=uuid4(),
            organization_id=test_org.id,
            name="Workflow bounce regression",
            trigger_type="surrogate_created",
            trigger_config={},
            conditions=[],
            condition_logic="AND",
            actions=[{"action_type": "send_email", "template_id": str(uuid4())}],
            is_enabled=True,
            is_system_workflow=False,
            created_by_user_id=test_user.id,
        )
        db.add(workflow)
        db.flush()

        execution_id = uuid4()
        job = Job(
            id=uuid4(),
            organization_id=test_org.id,
            job_type=JobType.WORKFLOW_EMAIL.value,
            payload={"workflow_execution_id": str(execution_id)},
            status=JobStatus.COMPLETED.value,
            attempts=1,
            max_attempts=3,
        )
        db.add(job)
        db.flush()

        execution = WorkflowExecution(
            id=execution_id,
            organization_id=test_org.id,
            workflow_id=workflow.id,
            event_id=uuid4(),
            depth=0,
            event_source=WorkflowEventSource.USER.value,
            entity_type="surrogate",
            entity_id=uuid4(),
            trigger_event={"source": "test"},
            matched_conditions=True,
            actions_executed=[
                {
                    "success": True,
                    "action_type": "send_email",
                    "job_ids": [str(job.id)],
                }
            ],
            status=WorkflowExecutionStatus.SUCCESS.value,
        )
        db.add(execution)
        email_log.job_id = job.id
        db.commit()

        payload = {
            "type": "email.bounced",
            "data": {
                "email_id": email_log.external_id,
                "bounce": {"type": "hard"},
            },
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )
        assert response.status_code == 200

        db.refresh(execution)
        assert execution.status == WorkflowExecutionStatus.PARTIAL.value
        assert "bounced" in (execution.error_message or "")

    @pytest.mark.asyncio
    async def test_webhook_complained_adds_suppression(self, db, test_org, client, setup_email_log):
        """Test that complaints add email to suppression list."""
        import json
        from app.db.models import EmailSuppression

        email_log, settings, webhook_secret = setup_email_log

        payload = {
            "type": "email.complained",
            "data": {"email_id": email_log.external_id},
        }

        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        # Check suppression was added
        suppression = (
            db.query(EmailSuppression)
            .filter(
                EmailSuppression.organization_id == test_org.id,
                EmailSuppression.email == email_log.recipient_email.lower(),
            )
            .first()
        )
        assert suppression is not None
        assert suppression.reason == "complaint"

    @pytest.mark.asyncio
    async def test_webhook_complaint_escalates_existing_opt_out_suppression(
        self, db, test_org, client, setup_email_log
    ):
        """A lower-severity row cannot hide later complaint evidence."""
        import json

        from app.db.models import EmailSuppression

        email_log, settings, webhook_secret = setup_email_log
        suppression = EmailSuppression(
            organization_id=test_org.id,
            email=email_log.recipient_email,
            reason="opt_out",
            source_type="unsubscribe",
        )
        db.add(suppression)
        db.commit()

        payload = {
            "type": "email.complained",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {"email_id": email_log.external_id},
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        db.refresh(suppression)
        assert suppression.reason == "complaint"
        assert suppression.source_type == "email_log"
        assert suppression.source_id == email_log.id

    @pytest.mark.asyncio
    async def test_webhook_duplicate_svix_event_is_processed_once(
        self, db, test_org, client, setup_email_log
    ):
        """Resend is at-least-once; replaying one event must not inflate engagement."""
        import json

        from app.db.models import ResendWebhookEvent

        email_log, settings, webhook_secret = setup_email_log
        payload = {
            "type": "email.opened",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {"email_id": email_log.external_id},
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
        headers = {
            "Content-Type": "application/json",
            "svix-id": msg_id,
            "svix-timestamp": timestamp,
            "svix-signature": signature,
        }

        first = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers=headers,
        )
        second = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        db.refresh(email_log)
        assert email_log.open_count == 1
        assert email_log.opened_at.isoformat() == "2026-07-21T14:03:00+00:00"
        assert (
            db.query(ResendWebhookEvent)
            .filter(
                ResendWebhookEvent.organization_id == test_org.id,
                ResendWebhookEvent.provider_event_id == msg_id,
            )
            .count()
            == 1
        )

    @pytest.mark.asyncio
    async def test_organization_webhook_prefers_signed_correlation_tags(
        self,
        db,
        test_org,
        client,
        setup_email_log,
    ):
        """Correlation tags disambiguate provider ids before the legacy lookup."""
        import json

        from app.db.enums import EmailStatus
        from app.db.models import EmailLog

        legacy_match, settings, webhook_secret = setup_email_log
        tagged_match = EmailLog(
            organization_id=test_org.id,
            recipient_email="tagged@recipient.com",
            subject="Tagged email",
            body="<p>Tagged body</p>",
            status=EmailStatus.SENT.value,
            external_id=None,
        )
        db.add(tagged_match)
        db.commit()

        payload = {
            "type": "email.delivered",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {
                "email_id": legacy_match.external_id,
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(tagged_match.id),
                },
            },
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        db.refresh(legacy_match)
        db.refresh(tagged_match)
        assert legacy_match.resend_status is None
        assert tagged_match.external_id == legacy_match.external_id
        assert tagged_match.resend_status == "delivered"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("event_type", "expected_resend_status", "expected_email_status"),
        [
            ("email.delivered", "delivered", "sent"),
            ("email.bounced", "bounced", "failed"),
        ],
    )
    async def test_verified_webhook_before_provider_response_remains_canonical(
        self,
        db,
        test_org,
        client,
        setup_email_log,
        event_type,
        expected_resend_status,
        expected_email_status,
    ):
        from datetime import datetime, timedelta, timezone

        from app.db.enums import EmailDeliveryAttemptOutcome, EmailDeliveryStatus
        from app.db.models import EmailDeliveryAttempt
        from app.services.email_delivery_service import record_delivery_success

        _existing_log, settings, webhook_secret = setup_email_log
        claimed_at = datetime.now(timezone.utc)
        queued, claim = _queue_claimed_resend_delivery(
            db,
            test_org.id,
            claimed_at=claimed_at,
        )
        provider_message_id = f"webhook-first-{uuid.uuid4().hex}"
        event_created_at = claimed_at + timedelta(seconds=1)
        response = await _post_signed_resend_event(
            client,
            webhook_id=settings.webhook_id,
            webhook_secret=webhook_secret,
            payload={
                "type": event_type,
                "created_at": event_created_at.isoformat(),
                "data": {
                    "email_id": provider_message_id,
                    "bounce": {"type": "Permanent"},
                    "tags": {
                        "organization_id": str(test_org.id),
                        "email_log_id": str(queued.email_log.id),
                    },
                },
            },
        )
        assert response.status_code == 200

        delivery = record_delivery_success(
            db,
            claim=claim,
            provider_message_id=provider_message_id,
            now=claimed_at + timedelta(seconds=2),
        )

        db.expire_all()
        email_log = db.get(type(queued.email_log), queued.email_log.id)
        attempt = (
            db.query(EmailDeliveryAttempt)
            .filter(EmailDeliveryAttempt.delivery_id == delivery.id)
            .one()
        )
        assert delivery.status == EmailDeliveryStatus.SENT.value
        assert delivery.provider_message_id == provider_message_id
        assert attempt.outcome == EmailDeliveryAttemptOutcome.SUCCEEDED.value
        assert attempt.provider_message_id == provider_message_id
        assert email_log.external_id == provider_message_id
        assert email_log.resend_status == expected_resend_status
        assert email_log.status == expected_email_status
        assert email_log.resend_status_at == event_created_at

    @pytest.mark.asyncio
    async def test_ambiguous_provider_response_after_verified_webhook_resolves_delivery(
        self,
        db,
        test_org,
        client,
        setup_email_log,
    ):
        from datetime import datetime, timedelta, timezone

        from app.db.enums import EmailDeliveryAttemptOutcome, EmailDeliveryStatus
        from app.db.models import EmailDeliveryAttempt
        from app.services.email_delivery_service import (
            record_delivery_reconciliation_required,
        )

        _existing_log, settings, webhook_secret = setup_email_log
        claimed_at = datetime.now(timezone.utc)
        queued, claim = _queue_claimed_resend_delivery(
            db,
            test_org.id,
            claimed_at=claimed_at,
        )
        provider_message_id = f"verified-before-timeout-{uuid.uuid4().hex}"
        response = await _post_signed_resend_event(
            client,
            webhook_id=settings.webhook_id,
            webhook_secret=webhook_secret,
            payload={
                "type": "email.delivered",
                "created_at": (claimed_at + timedelta(seconds=1)).isoformat(),
                "data": {
                    "email_id": provider_message_id,
                    "tags": {
                        "organization_id": str(test_org.id),
                        "email_log_id": str(queued.email_log.id),
                    },
                },
            },
        )
        assert response.status_code == 200

        delivery = record_delivery_reconciliation_required(
            db,
            claim=claim,
            error_type="transport_error",
            error_message="Connection dropped before the response was read",
            now=claimed_at + timedelta(seconds=2),
        )

        db.expire_all()
        email_log = db.get(type(queued.email_log), queued.email_log.id)
        attempt = (
            db.query(EmailDeliveryAttempt)
            .filter(EmailDeliveryAttempt.delivery_id == delivery.id)
            .one()
        )
        assert delivery.status == EmailDeliveryStatus.SENT.value
        assert delivery.provider_message_id == provider_message_id
        assert delivery.last_error is None
        assert email_log.external_id == provider_message_id
        assert email_log.resend_status == "delivered"
        assert email_log.status == "sent"
        assert attempt.outcome == EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
        assert attempt.error_type == "transport_error"

    @pytest.mark.asyncio
    async def test_verified_webhook_resolves_reconciliation_required_delivery(
        self,
        db,
        test_org,
        client,
        setup_email_log,
    ):
        from datetime import datetime, timedelta, timezone

        from app.db.enums import EmailDeliveryAttemptOutcome, EmailDeliveryStatus
        from app.db.models import EmailDeliveryAttempt
        from app.services.email_delivery_service import (
            record_delivery_reconciliation_required,
        )

        _existing_log, settings, webhook_secret = setup_email_log
        claimed_at = datetime.now(timezone.utc)
        queued, claim = _queue_claimed_resend_delivery(
            db,
            test_org.id,
            claimed_at=claimed_at,
        )
        delivery = record_delivery_reconciliation_required(
            db,
            claim=claim,
            error_type="transport_error",
            error_message="Connection dropped before the response was read",
            now=claimed_at + timedelta(seconds=1),
        )
        assert delivery.status == EmailDeliveryStatus.RECONCILIATION_REQUIRED.value

        provider_message_id = f"reconciled-by-webhook-{uuid.uuid4().hex}"
        response = await _post_signed_resend_event(
            client,
            webhook_id=settings.webhook_id,
            webhook_secret=webhook_secret,
            payload={
                "type": "email.delivered",
                "created_at": (claimed_at + timedelta(seconds=2)).isoformat(),
                "data": {
                    "email_id": provider_message_id,
                    "tags": {
                        "organization_id": str(test_org.id),
                        "email_log_id": str(queued.email_log.id),
                    },
                },
            },
        )
        assert response.status_code == 200

        db.expire_all()
        delivery = db.get(type(delivery), delivery.id)
        email_log = db.get(type(queued.email_log), queued.email_log.id)
        attempt = (
            db.query(EmailDeliveryAttempt)
            .filter(EmailDeliveryAttempt.delivery_id == delivery.id)
            .one()
        )
        assert delivery.status == EmailDeliveryStatus.SENT.value
        assert delivery.provider_message_id == provider_message_id
        assert delivery.last_error is None
        assert email_log.external_id == provider_message_id
        assert email_log.resend_status == "delivered"
        assert email_log.status == "sent"
        assert attempt.outcome == EmailDeliveryAttemptOutcome.TERMINAL_ERROR.value
        assert attempt.error_type == "transport_error"
        assert attempt.provider_message_id is None

    @pytest.mark.asyncio
    async def test_conflicting_provider_response_does_not_overwrite_verified_webhook_identity(
        self,
        db,
        test_org,
        client,
        setup_email_log,
    ):
        from datetime import datetime, timedelta, timezone

        from app.db.enums import EmailDeliveryAttemptOutcome, EmailDeliveryStatus
        from app.db.models import EmailDeliveryAttempt
        from app.services.email_delivery_service import (
            EmailDeliveryConflict,
            record_delivery_success,
        )

        _existing_log, settings, webhook_secret = setup_email_log
        claimed_at = datetime.now(timezone.utc)
        queued, claim = _queue_claimed_resend_delivery(
            db,
            test_org.id,
            claimed_at=claimed_at,
        )
        verified_provider_message_id = f"verified-id-{uuid.uuid4().hex}"
        response = await _post_signed_resend_event(
            client,
            webhook_id=settings.webhook_id,
            webhook_secret=webhook_secret,
            payload={
                "type": "email.delivered",
                "created_at": (claimed_at + timedelta(seconds=1)).isoformat(),
                "data": {
                    "email_id": verified_provider_message_id,
                    "tags": {
                        "organization_id": str(test_org.id),
                        "email_log_id": str(queued.email_log.id),
                    },
                },
            },
        )
        assert response.status_code == 200

        with pytest.raises(EmailDeliveryConflict, match="provider message id"):
            record_delivery_success(
                db,
                claim=claim,
                provider_message_id=f"conflicting-id-{uuid.uuid4().hex}",
                now=claimed_at + timedelta(seconds=2),
            )

        db.expire_all()
        delivery = db.get(type(queued.delivery), queued.delivery.id)
        email_log = db.get(type(queued.email_log), queued.email_log.id)
        attempt = (
            db.query(EmailDeliveryAttempt)
            .filter(EmailDeliveryAttempt.delivery_id == delivery.id)
            .one()
        )
        assert delivery.status == EmailDeliveryStatus.LEASED.value
        assert delivery.provider_message_id == verified_provider_message_id
        assert email_log.external_id == verified_provider_message_id
        assert email_log.resend_status == "delivered"
        assert attempt.outcome == EmailDeliveryAttemptOutcome.IN_PROGRESS.value
        assert attempt.provider_message_id is None

    @pytest.mark.asyncio
    async def test_reconcile_job_uses_tags_after_email_log_commit_race(
        self,
        db,
        test_org,
        client,
        setup_email_log,
    ):
        """A later-created log is correlated without waiting for external-id projection."""
        import json

        from app.db.enums import EmailStatus
        from app.db.models import EmailLog, Job, ResendWebhookEvent
        from app.jobs.handlers.resend import process_resend_event_reconcile

        _existing_log, settings, webhook_secret = setup_email_log
        future_email_log_id = uuid.uuid4()
        provider_message_id = f"race_msg_{uuid.uuid4().hex}"
        payload = {
            "type": "email.delivered",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {
                "email_id": provider_message_id,
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(future_email_log_id),
                },
            },
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )
        assert response.status_code == 200

        event = (
            db.query(ResendWebhookEvent)
            .filter(
                ResendWebhookEvent.organization_id == test_org.id,
                ResendWebhookEvent.provider_event_id == msg_id,
            )
            .one()
        )
        reconcile_job = (
            db.query(Job)
            .filter(
                Job.organization_id == test_org.id,
                Job.job_type == "resend_event_reconcile",
                Job.payload["event_id"].astext == str(event.id),
            )
            .one()
        )
        committed_email_log = EmailLog(
            id=future_email_log_id,
            organization_id=test_org.id,
            recipient_email="race@recipient.com",
            subject="Race recovery",
            body="<p>Race recovery</p>",
            status=EmailStatus.SENT.value,
            external_id=None,
        )
        db.add(committed_email_log)
        db.commit()

        await process_resend_event_reconcile(db, reconcile_job)

        db.refresh(committed_email_log)
        db.refresh(event)
        assert committed_email_log.external_id == provider_message_id
        assert committed_email_log.resend_status == "delivered"
        assert event.email_log_id == committed_email_log.id
        assert event.processed_at is not None

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("event_type", "expected_resend_status", "expected_status"),
        [
            ("email.scheduled", "scheduled", "sent"),
            ("email.sent", "sent", "sent"),
            ("email.delivery_delayed", "delivery_delayed", "sent"),
            ("email.failed", "failed", "failed"),
            ("email.suppressed", "suppressed", "skipped"),
        ],
    )
    async def test_webhook_tracks_current_delivery_lifecycle_events(
        self,
        db,
        test_org,
        client,
        setup_email_log,
        event_type,
        expected_resend_status,
        expected_status,
    ):
        import json

        email_log, settings, webhook_secret = setup_email_log
        event_created_at = "2026-07-21T14:03:00.000Z"
        payload = {
            "type": event_type,
            "created_at": event_created_at,
            "data": {
                "email_id": email_log.external_id,
                "error": {"message": "Provider rejected the message"},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        db.refresh(email_log)
        assert email_log.resend_status == expected_resend_status
        assert email_log.status == expected_status
        assert email_log.resend_status_at.isoformat() == "2026-07-21T14:03:00+00:00"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("event_type", "expected_status", "expected_error"),
        [
            ("email.failed", "failed", "Provider rejected the message"),
            ("email.suppressed", "skipped", "Provider rejected the message"),
            ("email.bounced", "failed", "bounced"),
        ],
    )
    async def test_terminal_webhook_projects_linked_appointment_email(
        self,
        db,
        test_org,
        test_user,
        client,
        setup_email_log,
        event_type,
        expected_status,
        expected_error,
    ):
        import json
        from datetime import datetime, timedelta, timezone
        from uuid import uuid4

        from app.db.enums import AppointmentStatus, MeetingMode
        from app.db.models import Appointment, AppointmentEmailLog, AppointmentType

        email_log, settings, webhook_secret = setup_email_log
        accepted_at = datetime(2026, 7, 21, 14, 0, tzinfo=timezone.utc)
        email_log.sent_at = accepted_at
        appointment_type = AppointmentType(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            slug=f"webhook-appointment-{uuid4().hex[:8]}",
            name="Webhook Appointment",
            duration_minutes=30,
            meeting_mode=MeetingMode.ZOOM.value,
            is_active=True,
        )
        appointment = Appointment(
            id=uuid4(),
            organization_id=test_org.id,
            user_id=test_user.id,
            appointment_type_id=appointment_type.id,
            client_name="Webhook Client",
            client_email=email_log.recipient_email,
            client_phone="555-123-4567",
            client_timezone="America/New_York",
            scheduled_start=accepted_at + timedelta(days=2),
            scheduled_end=accepted_at + timedelta(days=2, minutes=30),
            duration_minutes=30,
            meeting_mode=MeetingMode.ZOOM.value,
            status=AppointmentStatus.CONFIRMED.value,
        )
        appointment_log = AppointmentEmailLog(
            id=uuid4(),
            organization_id=test_org.id,
            appointment_id=appointment.id,
            email_type="confirmed",
            recipient_email=email_log.recipient_email,
            subject=email_log.subject,
            occurrence_key=f"appointment-email/{appointment.id}/confirmed/{accepted_at.isoformat()}",
            email_log_id=email_log.id,
            status="sent",
            sent_at=accepted_at,
            external_message_id=email_log.external_id,
        )
        email_log.source_type = "appointment_email"
        email_log.source_id = appointment_log.id
        db.add_all([appointment_type, appointment, appointment_log])
        db.commit()

        payload = {
            "type": event_type,
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {
                "email_id": email_log.external_id,
                "error": {"message": "Provider rejected the message"},
                "bounce": {"type": "Permanent"},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        db.refresh(appointment_log)
        assert appointment_log.status == expected_status
        assert appointment_log.error == expected_error
        assert appointment_log.external_message_id == email_log.external_id
        assert appointment_log.sent_at == accepted_at

    @pytest.mark.asyncio
    async def test_webhook_does_not_regress_delivery_state_from_an_older_event(
        self, db, test_org, client, setup_email_log
    ):
        """Resend does not guarantee delivery order, so older events cannot regress state."""
        import json

        email_log, settings, webhook_secret = setup_email_log
        timestamp = str(int(time.time()))

        async def post_event(event_type: str, created_at: str):
            payload = {
                "type": event_type,
                "created_at": created_at,
                "data": {"email_id": email_log.external_id},
            }
            body = json.dumps(payload).encode("utf-8")
            msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
            return await client.post(
                f"/webhooks/resend/{settings.webhook_id}",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "svix-id": msg_id,
                    "svix-timestamp": timestamp,
                    "svix-signature": signature,
                },
            )

        delivered = await post_event("email.delivered", "2026-07-21T14:04:00.000Z")
        stale_sent = await post_event("email.sent", "2026-07-21T14:03:00.000Z")

        assert delivered.status_code == 200
        assert stale_sent.status_code == 200
        db.refresh(email_log)
        assert email_log.resend_status == "delivered"
        assert email_log.status == "sent"
        assert email_log.resend_status_at.isoformat() == "2026-07-21T14:04:00+00:00"

    @pytest.mark.asyncio
    async def test_webhook_preserves_permanent_bounce_type_and_suppresses(
        self, db, test_org, client, setup_email_log
    ):
        """Current Resend bounce labels remain auditable while permanent bounces suppress."""
        import json

        from app.db.models import EmailSuppression

        email_log, settings, webhook_secret = setup_email_log
        payload = {
            "type": "email.bounced",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {
                "email_id": email_log.external_id,
                "bounce": {"type": "Permanent"},
            },
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        db.refresh(email_log)
        assert email_log.bounce_type == "Permanent"
        assert (
            db.query(EmailSuppression)
            .filter(
                EmailSuppression.organization_id == test_org.id,
                EmailSuppression.email == email_log.recipient_email.lower(),
            )
            .count()
            == 1
        )

    @pytest.mark.asyncio
    async def test_webhook_unknown_email_is_durably_accepted_for_reconciliation(
        self, db, test_org, client
    ):
        """Signed events survive the send/commit race without consuming provider retries."""
        import json

        from app.db.models import Job, ResendWebhookEvent
        from app.services import resend_settings_service

        settings = resend_settings_service.get_or_create_resend_settings(
            db, test_org.id, test_org.id
        )
        webhook_secret_bytes = b"unknown_email_log_webhook_secret"
        webhook_secret = "whsec_" + base64.urlsafe_b64encode(webhook_secret_bytes).decode(
            "utf-8"
        ).rstrip("=")
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_org.id,
            webhook_signing_secret=webhook_secret,
        )

        payload = {
            "type": "email.delivered",
            "data": {"email_id": "nonexistent_msg_id"},
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
        response = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200

        event = (
            db.query(ResendWebhookEvent)
            .filter(
                ResendWebhookEvent.organization_id == test_org.id,
                ResendWebhookEvent.provider_event_id == msg_id,
            )
            .one()
        )
        assert event.email_log_id is None
        assert event.processed_at is None

        reconcile_job = (
            db.query(Job)
            .filter(
                Job.organization_id == test_org.id,
                Job.job_type == "resend_event_reconcile",
                Job.payload["event_id"].astext == str(event.id),
            )
            .one()
        )
        assert reconcile_job.status == "pending"

        from datetime import datetime, timedelta, timezone

        from app.db.enums import JobStatus
        from app.jobs.handlers.resend import process_resend_event_reconcile
        from app.services import job_service

        reconcile_job.status = JobStatus.RUNNING.value
        reconcile_job.attempts = 5
        db.commit()
        retry_started_at = datetime.now(timezone.utc)

        with pytest.raises(RuntimeError, match="correlation pending"):
            await process_resend_event_reconcile(db, reconcile_job)
        job_service.mark_job_failed(
            db,
            reconcile_job,
            "Resend event correlation pending",
        )

        assert reconcile_job.status == JobStatus.PENDING.value
        assert reconcile_job.run_at >= retry_started_at + timedelta(seconds=70)

        reconcile_job.status = JobStatus.FAILED.value
        reconcile_job.attempts = reconcile_job.max_attempts
        reconcile_job.last_error = "Reconciliation window exhausted"
        db.commit()

        duplicate = await client.post(
            f"/webhooks/resend/{settings.webhook_id}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert duplicate.status_code == 200
        db.refresh(reconcile_job)
        assert reconcile_job.status == JobStatus.PENDING.value
        assert reconcile_job.attempts == 0
        assert reconcile_job.last_error is None

    @pytest.mark.asyncio
    async def test_platform_webhook_static_route_updates_native_email(
        self, db, test_org, client, monkeypatch
    ):
        """The static native-email webhook route must win over the tenant wildcard route."""
        import json

        from pydantic import SecretStr

        from app.core.config import settings as app_settings
        from app.db.enums import EmailStatus
        from app.db.models import EmailLog, Organization

        webhook_secret_bytes = b"platform_resend_webhook_secret"
        webhook_secret = "whsec_" + base64.urlsafe_b64encode(webhook_secret_bytes).decode(
            "utf-8"
        ).rstrip("=")
        monkeypatch.setattr(
            app_settings,
            "PLATFORM_RESEND_WEBHOOK_SECRET",
            SecretStr(webhook_secret),
        )

        email_log = EmailLog(
            organization_id=test_org.id,
            recipient_email="native@recipient.com",
            subject="Native platform email",
            body="<p>Native body</p>",
            status=EmailStatus.SENT.value,
            external_id=f"platform_msg_{uuid.uuid4().hex}",
        )
        db.add(email_log)
        db.flush()

        other_org = Organization(
            id=uuid.uuid4(),
            name="Other Platform Email Organization",
            slug=f"other-platform-email-{uuid.uuid4().hex[:8]}",
        )
        db.add(other_org)
        db.flush()
        colliding_email_log = EmailLog(
            organization_id=other_org.id,
            recipient_email="other-native@recipient.com",
            subject="Other native platform email",
            body="<p>Other native body</p>",
            status=EmailStatus.SENT.value,
            external_id=email_log.external_id,
        )
        db.add(colliding_email_log)
        db.commit()

        payload = {
            "type": "email.delivered",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {
                "email_id": email_log.external_id,
                "tags": {
                    "organization_id": str(test_org.id),
                    "email_log_id": str(email_log.id),
                },
            },
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)
        response = await client.post(
            "/webhooks/resend/platform",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        db.refresh(email_log)
        assert email_log.resend_status == "delivered"
        assert email_log.delivered_at.isoformat() == "2026-07-21T14:03:00+00:00"
        db.refresh(colliding_email_log)
        assert colliding_email_log.resend_status is None

    @pytest.mark.asyncio
    async def test_platform_webhook_acknowledges_legacy_event_without_tenant_tags(
        self, client, monkeypatch
    ):
        """Signed pre-tag platform events cannot be scoped and must not retry forever."""
        import json

        from pydantic import SecretStr

        from app.core.config import settings as app_settings

        webhook_secret_bytes = b"platform_legacy_webhook_secret"
        webhook_secret = "whsec_" + base64.urlsafe_b64encode(webhook_secret_bytes).decode(
            "utf-8"
        ).rstrip("=")
        monkeypatch.setattr(
            app_settings,
            "PLATFORM_RESEND_WEBHOOK_SECRET",
            SecretStr(webhook_secret),
        )

        payload = {
            "type": "email.delivered",
            "created_at": "2026-07-21T14:03:00.000Z",
            "data": {"email_id": f"legacy_platform_{uuid.uuid4().hex}"},
        }
        body = json.dumps(payload).encode("utf-8")
        timestamp = str(int(time.time()))
        msg_id, signature = _generate_svix_signature(body, webhook_secret, timestamp)

        response = await client.post(
            "/webhooks/resend/platform",
            content=body,
            headers={
                "Content-Type": "application/json",
                "svix-id": msg_id,
                "svix-timestamp": timestamp,
                "svix-signature": signature,
            },
        )

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestCampaignRunProviderLock:
    """Test that email provider is locked on CampaignRun creation."""

    def test_enqueue_campaign_locks_provider(self, db, test_org, test_user):
        """Test that enqueue_campaign_send locks the email provider on the run."""
        from app.db.models import Campaign, CampaignRun, EmailTemplate
        from app.db.enums import CampaignStatus
        from app.services import campaign_service, resend_settings_service

        # Setup: Create Resend settings
        resend_settings_service.update_resend_settings(
            db,
            test_org.id,
            test_user.id,
            email_provider="resend",
            api_key="re_test_key",
            from_email="no-reply@example.com",
            verified_domain="example.com",
        )

        # Create template
        template = EmailTemplate(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            name="Test Template",
            subject="Test",
            body="<p>Test</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()

        # Create campaign
        campaign = Campaign(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            email_template_id=template.id,
            name="Test Campaign",
            recipient_type="case",
            status=CampaignStatus.DRAFT.value,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        # Enqueue the campaign
        message, run_id, _ = campaign_service.enqueue_campaign_send(
            db, test_org.id, campaign.id, test_user.id, send_now=True
        )

        # Check that provider was locked on the run
        run = db.query(CampaignRun).filter(CampaignRun.id == run_id).first()
        assert run is not None
        assert run.email_provider == "resend"

    def test_enqueue_campaign_fails_without_provider(self, db, test_org, test_user):
        """Test that enqueue fails if email provider not configured."""
        from app.db.models import Campaign, EmailTemplate
        from app.db.enums import CampaignStatus
        from app.services import campaign_service, resend_settings_service

        # Create settings without provider
        resend_settings_service.get_or_create_resend_settings(db, test_org.id, test_user.id)

        # Create template and campaign
        template = EmailTemplate(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            name="Test Template 2",
            subject="Test",
            body="<p>Test</p>",
            is_active=True,
        )
        db.add(template)
        db.flush()

        campaign = Campaign(
            organization_id=test_org.id,
            created_by_user_id=test_user.id,
            email_template_id=template.id,
            name="Test Campaign 2",
            recipient_type="case",
            status=CampaignStatus.DRAFT.value,
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)

        # Should fail because no provider configured
        with pytest.raises(ValueError) as exc:
            campaign_service.enqueue_campaign_send(
                db, test_org.id, campaign.id, test_user.id, send_now=True
            )

        assert "not configured" in str(exc.value).lower()
