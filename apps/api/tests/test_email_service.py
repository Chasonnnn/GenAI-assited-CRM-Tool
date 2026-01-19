def test_send_email_commit_false_skips_commit(db, test_org, monkeypatch):
    from app.services import email_service

    def fail_commit():
        raise AssertionError("send_email should not commit when commit=False")

    monkeypatch.setattr(db, "commit", fail_commit)

    email_log, job = email_service.send_email(
        db=db,
        org_id=test_org.id,
        template_id=None,
        recipient_email="test@example.com",
        subject="Hello",
        body="Body",
        commit=False,
    )

    assert email_log.id is not None
    assert job.id is not None
    assert email_log.job_id == job.id
