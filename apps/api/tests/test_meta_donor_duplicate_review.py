"""A Meta donor lead that matches an active donor raises an alert and a review task."""

from app.db.enums import AlertType
from app.db.models import SystemAlert, Task
from app.schemas.donor import DonorCreate
from app.services import donor_service, meta_lead_service
from tests.test_meta_donor_routing import _lead, _mapped_form


def test_duplicate_donor_email_records_alert_and_one_review_task(db, test_org, test_user):
    existing = donor_service.create_donor(
        db,
        test_org.id,
        test_user.id,
        DonorCreate(donor_type="egg", full_name="Existing Donor", email="dup-review@example.com"),
    )
    form = _mapped_form(db, test_org.id, external_id="dup-review", lead_kind="sperm_donor")
    lead = _lead(
        db,
        test_org.id,
        external_id="lead-dup-review",
        form_external_id=form.form_external_id,
        email="Dup-Review@example.com",
    )

    status, subject = meta_lead_service.process_stored_meta_lead(db, lead)
    lead.status = "convert_failed"
    db.commit()
    meta_lead_service.process_stored_meta_lead(db, lead)

    assert (status, subject) == ("convert_failed", None)
    alert = (
        db.query(SystemAlert)
        .filter(
            SystemAlert.organization_id == test_org.id,
            SystemAlert.alert_type == AlertType.META_CONVERT_FAILED.value,
            SystemAlert.integration_key == f"meta_form:{form.form_external_id}",
        )
        .one()
    )
    assert alert.details["reason"] == "active_donor_email"
    assert alert.occurrence_count == 2
    tasks = (
        db.query(Task)
        .filter(Task.organization_id == test_org.id, Task.donor_id == existing.id)
        .all()
    )
    assert len(tasks) == 1
    assert tasks[0].title == "Review duplicate donor Meta lead"
    assert "dup-review@example.com" not in (tasks[0].description or "").lower()
    assert str(lead.id) in tasks[0].description
    assert existing.donor_number in tasks[0].description
