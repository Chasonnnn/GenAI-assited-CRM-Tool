from app.services import email_service


def test_create_template_sanitizes_body(db, test_org, test_user):
    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Welcome",
        subject="Hello",
        body="<p>Hello</p><script>alert(1)</script>",
    )

    assert "<script" not in template.body
    assert "<p>Hello</p>" in template.body


def test_update_template_sanitizes_body(db, test_org, test_user):
    template = email_service.create_template(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        name="Follow Up",
        subject="Subject",
        body="<p>Initial</p>",
    )

    updated = email_service.update_template(
        db=db,
        template=template,
        user_id=test_user.id,
        body="<p>Updated</p><script>alert(2)</script>",
    )

    assert "<script" not in updated.body
    assert "<p>Updated</p>" in updated.body
