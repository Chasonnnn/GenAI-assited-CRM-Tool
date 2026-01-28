import uuid

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.services import form_service, form_submission_service
from app.utils.normalization import normalize_email


def _create_surrogate(db, org_id, user_id, stage):
    email = f"form-svc-{uuid.uuid4().hex[:8]}@example.com"
    normalized_email = normalize_email(email)
    surrogate = Surrogate(
        id=uuid.uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid.uuid4().int % 90000 + 10000:05d}",
        stage_id=stage.id,
        status_label=stage.label,
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Original Name",
        email=normalized_email,
        email_hash=hash_email(normalized_email),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def _create_published_form(db, org_id, user_id):
    schema = {
        "pages": [
            {
                "title": "Basics",
                "fields": [
                    {
                        "key": "full_name",
                        "label": "Full Name",
                        "type": "text",
                        "required": True,
                    },
                    {
                        "key": "date_of_birth",
                        "label": "Date of Birth",
                        "type": "date",
                        "required": False,
                    },
                ],
            }
        ]
    }

    form = form_service.create_form(
        db=db,
        org_id=org_id,
        user_id=user_id,
        name="Application Form",
        description="Test form",
        schema=schema,
        max_file_size_bytes=None,
        max_file_count=None,
        allowed_mime_types=None,
    )
    form_service.publish_form(db, form, user_id)
    form_service.set_field_mappings(
        db,
        form,
        [
            {"field_key": "full_name", "surrogate_field": "full_name"},
            {"field_key": "date_of_birth", "surrogate_field": "date_of_birth"},
        ],
    )
    return form


def test_submission_service_single_use_token(db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    form = _create_published_form(db, test_org.id, test_user.id)

    token_record = form_submission_service.create_submission_token(
        db=db,
        org_id=test_org.id,
        form=form,
        surrogate=surrogate,
        user_id=test_user.id,
        expires_in_days=7,
    )
    assert token_record.token

    token = form_submission_service.get_valid_token(db, token_record.token)
    assert token is not None

    submission = form_submission_service.create_submission(
        db=db,
        token=token,
        form=form,
        answers={"full_name": "Jane Doe", "date_of_birth": "1990-01-01"},
        files=[],
    )
    assert submission.surrogate_id == surrogate.id

    refreshed = form_submission_service.get_valid_token(db, token_record.token)
    assert refreshed is None


def test_submission_service_approval_updates_surrogate(db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    form = _create_published_form(db, test_org.id, test_user.id)

    token_record = form_submission_service.create_submission_token(
        db=db,
        org_id=test_org.id,
        form=form,
        surrogate=surrogate,
        user_id=test_user.id,
        expires_in_days=7,
    )

    submission = form_submission_service.create_submission(
        db=db,
        token=token_record,
        form=form,
        answers={"full_name": "Jane Doe", "date_of_birth": "1990-01-01"},
        files=[],
    )

    approved = form_submission_service.approve_submission(
        db=db,
        submission=submission,
        reviewer_id=test_user.id,
        review_notes="Looks good",
    )
    assert approved.status == "approved"

    db.refresh(surrogate)
    assert surrogate.full_name == "Jane Doe"
    assert str(surrogate.date_of_birth) == "1990-01-01"


def test_submission_service_update_answers_syncs_surrogate(db, test_org, test_user, default_stage):
    surrogate = _create_surrogate(db, test_org.id, test_user.id, default_stage)
    form = _create_published_form(db, test_org.id, test_user.id)

    token_record = form_submission_service.create_submission_token(
        db=db,
        org_id=test_org.id,
        form=form,
        surrogate=surrogate,
        user_id=test_user.id,
        expires_in_days=7,
    )

    submission = form_submission_service.create_submission(
        db=db,
        token=token_record,
        form=form,
        answers={"full_name": "Jane Doe", "date_of_birth": "1990-01-01"},
        files=[],
    )

    _, updates = form_submission_service.update_submission_answers(
        db=db,
        submission=submission,
        updates=[
            {"field_key": "full_name", "value": "Jane Smith"},
            {"field_key": "date_of_birth", "value": "1991-02-03"},
        ],
        user_id=test_user.id,
    )
    assert "full_name" in updates

    db.refresh(surrogate)
    assert surrogate.full_name == "Jane Smith"
    assert str(surrogate.date_of_birth) == "1991-02-03"
