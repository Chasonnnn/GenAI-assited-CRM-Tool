"""Activity pagination bounds hydrated records while preserving legacy ordering."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import event

from app.core.encryption import hash_email
from app.db.models import Donor, EntityNote, IntendedParent
from app.services import entity_activity_service


@pytest.mark.parametrize("kind", ["donor", "intended_parent"])
def test_activity_hydrates_only_requested_page(db, test_org, test_user, default_stage, kind):
    org_id, user_id = test_org.id, test_user.id
    email = f"page-{uuid.uuid4().hex}@example.com"
    values = dict(
        id=uuid.uuid4(),
        organization_id=org_id,
        full_name="Activity Pagination",
        email=email,
        email_hash=hash_email(email),
        stage_id=default_stage.id,
    )
    number = str(uuid.uuid4().int % 90000 + 10000)
    subject = (
        Donor(**values, donor_type="egg", donor_number=f"D{number}")
        if kind == "donor"
        else IntendedParent(**values, intended_parent_number=f"I{number}")
    )
    db.add(subject)
    db.flush()
    subject_id = subject.id
    note_ids = [uuid.uuid4() for _ in range(48)]
    timestamp = datetime(2026, 8, 30, 12, tzinfo=UTC)
    db.add_all(
        [
            EntityNote(
                id=note_id,
                organization_id=org_id,
                entity_type=kind,
                entity_id=subject_id,
                author_id=user_id,
                content="Pagination note",
                created_at=timestamp,
            )
            for note_id in note_ids
        ]
    )
    db.flush()
    db.expunge_all()
    hydrated_notes = []

    def record_loaded(_session, instance):
        if isinstance(instance, EntityNote):
            hydrated_notes.append(instance.id)

    event.listen(db, "loaded_as_persistent", record_loaded)
    try:
        items, total = entity_activity_service.list_entity_activity(
            db,
            org_id=org_id,
            entity_type=kind,
            entity_id=subject_id,
            page=3,
            per_page=5,
            include_note_previews=True,
        )
    finally:
        event.remove(db, "loaded_as_persistent", record_loaded)

    expected_ids = sorted((uuid.uuid5(note_id, "note_added") for note_id in note_ids), reverse=True)
    assert [item["id"] for item in items] == expected_ids[10:15]
    assert total == 48
    assert len(hydrated_notes) == 5
    assert all(item["details"]["preview"] == "Pagination note" for item in items)

    empty_items, empty_total = entity_activity_service.list_entity_activity(
        db,
        org_id=org_id,
        entity_type=kind,
        entity_id=subject_id,
        page=20,
        per_page=5,
    )
    assert empty_items == []
    assert empty_total == total
