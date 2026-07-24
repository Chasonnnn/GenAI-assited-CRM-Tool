def test_send_email_queues_immutable_org_resend_delivery_instead_of_generic_job(
    db,
    test_org,
    test_user,
):
    from app.db.enums import EmailDeliveryStatus, EmailProviderScope, EmailStatus
    from app.db.models import Job, ResendSettings
    from app.services import email_service, resend_settings_service

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="care@example.com",
            from_name="Care Team",
            reply_to_email="reply@example.com",
            verified_domain="example.com",
        )
    )
    db.flush()

    email_log, delivery = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="test@example.com",
        subject="Hello",
        body="<p>Hello <strong>world</strong></p>",
        sender_user_id=test_user.id,
        commit=False,
    )

    assert email_log.status == EmailStatus.PENDING.value
    assert email_log.actor_user_id == test_user.id
    assert email_log.provider_scope == EmailProviderScope.ORGANIZATION.value
    assert email_log.from_email == "Care Team <care@example.com>"
    assert email_log.reply_to_email == "reply@example.com"
    assert email_log.text_body == "Hello world"
    assert delivery.status == EmailDeliveryStatus.PENDING.value
    assert delivery.email_log_id == email_log.id
    assert delivery.provider_account_id == f"organization:{test_org.id}"
    assert db.query(Job).filter(Job.organization_id == test_org.id).count() == 0


def test_send_email_commit_false_skips_commit(db, test_org, monkeypatch):
    from app.db.models import ResendSettings
    from app.services import email_service, resend_settings_service

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="care@example.com",
            verified_domain="example.com",
        )
    )
    db.flush()

    def fail_commit():
        raise AssertionError("send_email should not commit when commit=False")

    monkeypatch.setattr(db, "commit", fail_commit)

    email_log, delivery = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="test@example.com",
        subject="Hello",
        body="Body",
        commit=False,
    )

    assert email_log.id is not None
    assert delivery.id is not None
    assert email_log.job_id is None
    assert delivery.email_log_id == email_log.id


def test_send_email_queues_attachment_snapshot_and_links_in_one_operation(
    db,
    test_org,
):
    from uuid import uuid4

    from app.db.models import Attachment, ResendSettings
    from app.services import email_service, resend_settings_service

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="care@example.com",
            verified_domain="example.com",
        )
    )
    attachment_id = uuid4()
    attachment = Attachment(
        id=attachment_id,
        organization_id=test_org.id,
        filename="consent.pdf",
        storage_key=f"{test_org.id}/email-tests/{attachment_id}",
        content_type="application/pdf",
        file_size=9,
        checksum_sha256="29d1283686193dc1461a7deac4f53d9bc5402a28b95d854f69e94986756fd0a9",
        scan_status="clean",
        quarantined=False,
    )
    db.add(attachment)
    db.flush()

    email_log, delivery = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="test@example.com",
        subject="Attached consent",
        body="<p>Please review.</p>",
        attachments=[attachment],
        idempotency_key=f"email-service-attachment/{uuid4()}",
        commit=False,
    )

    assert email_log.attachment_manifest == [
        {
            "attachment_id": str(attachment.id),
            "filename": "consent.pdf",
            "content_type": "application/pdf",
            "size_bytes": 9,
            "sha256": "29d1283686193dc1461a7deac4f53d9bc5402a28b95d854f69e94986756fd0a9",
        }
    ]
    assert [link.attachment_id for link in email_log.attachment_links] == [attachment.id]
    assert delivery is not None


def test_send_from_template_reuses_the_client_email_occurrence(
    db,
    test_org,
    test_user,
    monkeypatch,
):
    from uuid import uuid4

    from app.db.models import EmailDelivery, EmailLog, ResendSettings
    from app.services import email_service, resend_settings_service, unsubscribe_service

    db.add(
        ResendSettings(
            organization_id=test_org.id,
            email_provider="resend",
            api_key_encrypted=resend_settings_service.encrypt_api_key("re_test_key"),
            from_email="care@example.com",
            verified_domain="example.com",
        )
    )
    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name=f"Idempotent manual send {uuid4().hex[:8]}",
        subject="Hello {{full_name}}",
        body="<p>Hello {{full_name}}</p>",
    )
    occurrence_key = f"manual-template-send/{uuid4()}"
    token_time = 1_700_000_000
    monkeypatch.setattr(unsubscribe_service.time, "time", lambda: token_time)

    first = email_service.send_from_template(
        db=db,
        org_id=test_org.id,
        template_id=template.id,
        recipient_email="recipient@example.com",
        variables={"full_name": "Recipient"},
        sender_user_id=test_user.id,
        idempotency_key=occurrence_key,
    )
    token_time += 120
    second = email_service.send_from_template(
        db=db,
        org_id=test_org.id,
        template_id=template.id,
        recipient_email="recipient@example.com",
        variables={"full_name": "Recipient"},
        sender_user_id=test_user.id,
        idempotency_key=occurrence_key,
    )

    assert first is not None
    assert second is not None
    assert second[0].id == first[0].id
    assert second[1].id == first[1].id
    assert (
        db.query(EmailLog)
        .filter(
            EmailLog.organization_id == test_org.id,
            EmailLog.idempotency_key == occurrence_key,
        )
        .count()
        == 1
    )
    assert db.query(EmailDelivery).filter(EmailDelivery.email_log_id == first[0].id).count() == 1
