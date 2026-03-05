from __future__ import annotations

from uuid import uuid4

from app.core.encryption import hash_email
from app.db.models import Surrogate
from app.services import import_service
from app.utils.normalization import normalize_email


def _create_surrogate(db, *, org_id, stage_id, user_id, email: str) -> Surrogate:
    normalized = normalize_email(email)
    surrogate = Surrogate(
        id=uuid4(),
        organization_id=org_id,
        surrogate_number=f"S{uuid4().int % 90000 + 10000:05d}",
        stage_id=stage_id,
        status_label="new_unread",
        source="manual",
        owner_type="user",
        owner_id=user_id,
        created_by_user_id=user_id,
        full_name="Import Existing",
        email=normalized,
        email_hash=hash_email(normalized),
    )
    db.add(surrogate)
    db.flush()
    return surrogate


def test_import_csv_detection_and_hash_helpers():
    utf16_tsv = "full_name\temail\nAlice\talice@example.com\n".encode("utf-16")
    headers, rows, encoding, delimiter = import_service._parse_csv_with_detection(utf16_tsv)
    assert headers == ["full_name", "email"]
    assert rows == [["Alice", "alice@example.com"]]
    assert encoding == "utf-16"
    assert delimiter == "\t"

    parsed_headers, parsed_rows = import_service.parse_csv_file(
        "full_name,email\nBob,bob@example.com\n"
    )
    assert parsed_headers == ["full_name", "email"]
    assert parsed_rows == [["Bob", "bob@example.com"]]

    assert import_service.compute_file_hash("a,b\n1,2\n") == import_service.compute_file_hash(
        b"a,b\n1,2\n"
    )


def test_import_date_ambiguity_and_dedup_stats(db, test_org, test_user, default_stage):
    _create_surrogate(
        db,
        org_id=test_org.id,
        stage_id=default_stage.id,
        user_id=test_user.id,
        email="duplicate@example.com",
    )
    db.commit()

    headers = ["full_name", "date_of_birth", "email"]
    rows = [
        ["Alice", "03/04/2020", "duplicate@example.com"],
        ["Bob", "12/31/2020", "unique@example.com"],
        ["Bob 2", "04/05/2020", "unique@example.com"],
    ]
    column_map = {0: "full_name", 1: "date_of_birth", 2: "email"}
    warnings = import_service._detect_date_ambiguity_warnings(headers, rows, column_map)
    assert any(item["column"] == "date_of_birth" for item in warnings)

    emails = ["duplicate@example.com", "unique@example.com", "unique@example.com"]
    duplicate_db, duplicate_csv, details, new_records = import_service._compute_dedup_stats(
        db, test_org.id, emails
    )
    assert duplicate_db == 1
    assert duplicate_csv == 1
    assert details[0]["email"] == "duplicate@example.com"
    assert new_records == 1


def test_execute_import_empty_csv_marks_failed(db, test_org, test_user):
    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="empty.csv",
        total_rows=0,
        file_content=b"",
        status="approved",
    )

    result = import_service.execute_import(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        import_id=import_record.id,
        file_content=b"",
    )
    assert result.imported == 0
    assert result.skipped == 0
    assert result.errors == []

    refreshed = import_service.get_import(db, test_org.id, import_record.id)
    assert refreshed is not None
    assert refreshed.status == "failed"
    assert refreshed.error_count == 1
    assert refreshed.errors is not None
    assert refreshed.errors[0]["errors"][0] == "Empty CSV file"


def test_import_row_validation_modes():
    row = {
        "full_name": "Test User",
        "email": "valid@example.com",
        "date_of_birth": "13/40/2020",
    }
    dropped_counts: dict[str, int] = {}
    validated = import_service._validate_row_with_mode(
        row_data=row.copy(),
        default_source="manual",
        validation_mode=import_service.VALIDATION_MODE_DROP_FIELDS,
        dropped_field_counts=dropped_counts,
    )
    assert validated.full_name == "Test User"
    assert validated.email == "valid@example.com"
    assert dropped_counts.get("date_of_birth") == 1
