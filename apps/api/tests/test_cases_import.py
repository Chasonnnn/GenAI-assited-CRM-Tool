"""
Comprehensive tests for CSV Import API.

Tests upload, preview, execution, validation, deduplication, and history.
"""

import io
import uuid
import pytest
from httpx import AsyncClient


def create_csv_content(rows: list[dict]) -> bytes:
    """Helper to create CSV content from list of dicts."""
    if not rows:
        return b""

    headers = list(rows[0].keys())
    lines = [",".join(headers)]

    for row in rows:
        values = [str(row.get(h, "")) for h in headers]
        lines.append(",".join(values))

    return "\n".join(lines).encode("utf-8")


@pytest.mark.asyncio
async def test_preview_import_success(authed_client: AsyncClient):
    """Test enhanced CSV preview with valid data."""
    csv_data = create_csv_content(
        [
            {"full_name": "John Doe", "email": "john@test.com", "phone": "5551234567"},
            {
                "full_name": "Jane Smith",
                "email": "jane@test.com",
                "phone": "5559876543",
            },
        ]
    )

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total_rows"] == 2
    assert len(data["sample_rows"]) == 2
    assert data["duplicate_emails_db"] == 0
    assert data["duplicate_emails_csv"] == 0
    assert data["has_header"] is True
    assert isinstance(data["validation_errors"], int)
    assert isinstance(data["ai_available"], bool)

    suggested_fields = {s["suggested_field"] for s in data["column_suggestions"]}
    assert "full_name" in suggested_fields
    assert "email" in suggested_fields


@pytest.mark.asyncio
async def test_preview_import_ai_available_requires_consent(
    authed_client: AsyncClient, db, test_org, test_user
):
    from datetime import datetime, timezone

    from app.db.models import AISettings
    from app.services import ai_settings_service

    settings = AISettings(
        organization_id=test_org.id,
        is_enabled=True,
        provider="openai",
        model="gpt-4o-mini",
        current_version=1,
        consent_accepted_at=None,
        consent_accepted_by=None,
        api_key_encrypted=ai_settings_service.encrypt_api_key("sk-test"),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(settings)
    db.flush()

    csv_data = create_csv_content([{"full_name": "John Doe", "email": "john@test.com"}])

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ai_available"] is False


@pytest.mark.asyncio
async def test_preview_import_detects_duplicates_in_db(
    authed_client: AsyncClient, db, test_org, test_user
):
    """Test preview detects existing cases in database."""
    from app.services import surrogate_service
    from app.schemas.surrogate import SurrogateCreate
    from app.db.enums import SurrogateSource

    # Create existing case using service
    case_data = SurrogateCreate(
        full_name="Existing User",
        email="existing@test.com",
        source=SurrogateSource.IMPORT,
    )
    surrogate_service.create_surrogate(db, test_org.id, test_user.id, case_data)

    # Upload CSV with duplicate email
    csv_data = create_csv_content(
        [
            {"full_name": "John Doe", "email": "existing@test.com"},
            {"full_name": "Jane Smith", "email": "jane@test.com"},
        ]
    )

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_emails_db"] == 1


@pytest.mark.asyncio
async def test_preview_import_detects_duplicates_in_csv(authed_client: AsyncClient):
    """Test preview detects duplicate emails within CSV."""
    csv_data = create_csv_content(
        [
            {"full_name": "John Doe", "email": "john@test.com"},
            {"full_name": "John Duplicate", "email": "john@test.com"},
            {"full_name": "Jane Smith", "email": "jane@test.com"},
        ]
    )

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_emails_csv"] == 1


@pytest.mark.asyncio
async def test_preview_import_blocks_duplicate_file(
    authed_client: AsyncClient, db, test_org, test_user
):
    """Uploading the exact same file while an import is active should be blocked."""
    from app.db.models import SurrogateImport
    from app.services import import_service

    csv_data = create_csv_content([{"full_name": "Dupe User", "email": "dupe@test.com"}])
    file_hash = import_service.compute_file_hash(csv_data)

    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="dupe.csv",
        file_content=csv_data,
        file_hash=file_hash,
        status="pending",
        total_rows=1,
    )
    db.add(import_record)
    db.commit()

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("dupe.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 409
    assert "already" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_import_detects_unmapped_columns(authed_client: AsyncClient):
    """Test enhanced preview identifies unmapped columns."""
    csv_data = create_csv_content(
        [
            {
                "full_name": "John Doe",
                "email": "john@test.com",
                "unknown_field": "value",
            },
        ]
    )

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["unmatched_count"] >= 1
    unknown = [s for s in data["column_suggestions"] if s["csv_column"] == "unknown_field"]
    assert unknown and unknown[0]["suggested_field"] is None


@pytest.mark.asyncio
async def test_preview_import_rejects_non_csv(authed_client: AsyncClient):
    """Test preview rejects non-CSV files."""
    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.txt", io.BytesIO(b"not a csv"), "text/plain")},
    )

    assert response.status_code == 400
    assert "csv" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_import_without_auth_fails(client: AsyncClient):
    """Test unauthenticated preview request fails."""
    csv_data = create_csv_content([{"email": "alice@test.com"}])

    response = await client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_submit_import_updates_status_and_snapshot(authed_client: AsyncClient, db):
    """Test submitting import stores mapping snapshot and status."""
    from app.db.models import SurrogateImport

    csv_data = create_csv_content(
        [
            {"full_name": "Alice Johnson", "email": "alice@test.com"},
            {"full_name": "Bob Wilson", "email": "bob@test.com"},
        ]
    )

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200
    import_id = preview.json()["import_id"]

    submit = await authed_client.post(
        f"/surrogates/import/{import_id}/submit",
        json={
            "column_mappings": [
                {"csv_column": "full_name", "surrogate_field": "full_name"},
                {"csv_column": "email", "surrogate_field": "email"},
            ],
            "unknown_column_behavior": "metadata",
            "backdate_created_at": True,
        },
    )
    assert submit.status_code == 200
    submit_data = submit.json()
    assert submit_data["status"] == "awaiting_approval"
    assert "deduplication_stats" in submit_data

    db.expire_all()
    import_record = (
        db.query(SurrogateImport).filter(SurrogateImport.id == uuid.UUID(import_id)).first()
    )
    assert import_record is not None
    assert import_record.status == "awaiting_approval"
    assert import_record.column_mapping_snapshot is not None
    assert import_record.unknown_column_behavior == "metadata"
    assert import_record.backdate_created_at is True


@pytest.mark.asyncio
async def test_approve_import_queues_job(authed_client: AsyncClient, db, test_org):
    """Test approving import queues a background job."""
    from app.db.models import Job
    from app.db.enums import JobType

    csv_data = create_csv_content(
        [
            {"full_name": "Charlie", "email": "charlie@test.com"},
            {"full_name": "Delta", "email": "delta@test.com"},
        ]
    )

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200
    import_id = preview.json()["import_id"]

    submit = await authed_client.post(
        f"/surrogates/import/{import_id}/submit",
        json={
            "column_mappings": [
                {"csv_column": "full_name", "surrogate_field": "full_name"},
                {"csv_column": "email", "surrogate_field": "email"},
            ],
            "unknown_column_behavior": "metadata",
        },
    )
    assert submit.status_code == 200

    approve = await authed_client.post(f"/surrogates/import/{import_id}/approve")
    assert approve.status_code == 200

    db.expire_all()
    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.CSV_IMPORT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload["import_id"] == str(import_id)
    assert job.payload["use_mappings"] is True
    assert job.payload["unknown_column_behavior"] == "metadata"


@pytest.mark.asyncio
async def test_retry_import_queues_job(authed_client: AsyncClient, db, test_org, test_user):
    """Retrying an approved import should enqueue a CSV import job."""
    from app.db.enums import JobType
    from app.db.models import Job, SurrogateImport

    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="retry.csv",
        file_content=b"full_name,email\nRetry User,retry@test.com\n",
        status="approved",
        total_rows=1,
    )
    db.add(import_record)
    db.commit()

    response = await authed_client.post(f"/surrogates/import/{import_record.id}/retry")
    assert response.status_code == 200

    job = (
        db.query(Job)
        .filter(
            Job.organization_id == test_org.id,
            Job.job_type == JobType.CSV_IMPORT.value,
        )
        .order_by(Job.created_at.desc())
        .first()
    )
    assert job is not None
    assert job.payload["import_id"] == str(import_record.id)


@pytest.mark.asyncio
async def test_run_inline_import_completes(authed_client: AsyncClient, db, test_org, test_user):
    """Approved imports can be executed inline when the worker is unavailable."""
    from app.db.models import SurrogateImport

    csv_data = create_csv_content([{"full_name": "Inline User", "email": "inline@test.com"}])

    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="inline.csv",
        file_content=csv_data,
        status="approved",
        total_rows=1,
        column_mapping_snapshot=[
            {
                "csv_column": "full_name",
                "surrogate_field": "full_name",
                "transformation": None,
                "action": "map",
            },
            {
                "csv_column": "email",
                "surrogate_field": "email",
                "transformation": None,
                "action": "map",
            },
        ],
    )
    db.add(import_record)
    db.commit()

    response = await authed_client.post(f"/surrogates/import/{import_record.id}/run-inline")
    assert response.status_code == 200

    db.refresh(import_record)
    assert import_record.status == "completed"
    assert import_record.imported_count == 1
    assert import_record.file_content is None


@pytest.mark.asyncio
async def test_cancel_import_marks_cancelled_and_clears_file(
    authed_client: AsyncClient, db, test_org, test_user
):
    from app.db.models import SurrogateImport

    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="cancel.csv",
        file_content=b"full_name,email\nCancel User,cancel@test.com\n",
        status="pending",
        total_rows=1,
    )
    db.add(import_record)
    db.commit()

    response = await authed_client.delete(f"/surrogates/import/{import_record.id}")
    assert response.status_code == 200

    db.refresh(import_record)
    assert import_record.status == "cancelled"
    assert import_record.file_content is None

    list_response = await authed_client.get("/surrogates/import")
    assert list_response.status_code == 200
    assert str(import_record.id) not in {item["id"] for item in list_response.json()}


@pytest.mark.asyncio
async def test_cancel_import_blocks_running(authed_client: AsyncClient, db, test_org, test_user):
    from app.db.models import SurrogateImport

    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="running.csv",
        file_content=b"full_name,email\nRun User,run@test.com\n",
        status="running",
        total_rows=1,
    )
    db.add(import_record)
    db.commit()

    response = await authed_client.delete(f"/surrogates/import/{import_record.id}")
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_preview_import_reports_validation_errors(authed_client: AsyncClient):
    """Test enhanced preview reports validation errors for bad rows."""
    csv_data = create_csv_content(
        [
            {"full_name": "Valid User", "email": "valid@test.com"},
            {"full_name": "", "email": "invalid-email"},
        ]
    )

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["validation_errors"] >= 1


def test_execute_import_warns_on_unmapped_columns(db, test_org, test_user):
    """Test unknown_column_behavior=warn stores warnings without error_count."""
    from app.services import import_service
    from app.services.import_service import ColumnMapping
    from app.db.models import SurrogateImport

    csv_data = create_csv_content(
        [
            {
                "full_name": "Warn User",
                "email": "warn@test.com",
                "unmapped_col": "extra",
            }
        ]
    )

    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="warn.csv",
        total_rows=1,
        file_content=csv_data,
        status="pending",
    )

    mappings = [
        ColumnMapping(
            csv_column="full_name",
            surrogate_field="full_name",
            transformation=None,
            action="map",
        ),
        ColumnMapping(
            csv_column="email",
            surrogate_field="email",
            transformation=None,
            action="map",
        ),
    ]

    import_service.execute_import_with_mappings(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        import_id=import_record.id,
        file_content=csv_data,
        column_mappings=mappings,
        unknown_column_behavior="warn",
    )

    db.expire_all()
    stored = db.query(SurrogateImport).filter(SurrogateImport.id == import_record.id).first()
    assert stored is not None
    assert stored.error_count == 0
    warnings = [entry for entry in (stored.errors or []) if entry.get("level") == "warning"]
    assert warnings
    assert warnings[0]["column"] == "unmapped_col"


def test_execute_import_uses_default_source(db, test_org, test_user):
    """Default source should be applied when CSV lacks a source column."""
    from app.db.enums import SurrogateSource
    from app.db.models import Surrogate
    from app.services import import_service
    from app.services.import_service import ColumnMapping

    csv_data = create_csv_content(
        [
            {"full_name": "Source User", "email": "source@test.com"},
        ]
    )

    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="source.csv",
        total_rows=1,
        file_content=csv_data,
        status="pending",
    )
    import_record.default_source = SurrogateSource.REFERRAL.value
    db.commit()

    mappings = [
        ColumnMapping(
            csv_column="full_name",
            surrogate_field="full_name",
            transformation=None,
            action="map",
        ),
        ColumnMapping(
            csv_column="email",
            surrogate_field="email",
            transformation=None,
            action="map",
        ),
    ]

    import_service.execute_import_with_mappings(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        import_id=import_record.id,
        file_content=csv_data,
        column_mappings=mappings,
        default_source=SurrogateSource.REFERRAL,
    )

    db.expire_all()
    surrogate = (
        db.query(Surrogate)
        .filter(Surrogate.organization_id == test_org.id)
        .order_by(Surrogate.created_at.desc())
        .first()
    )
    assert surrogate is not None
    assert surrogate.source == SurrogateSource.REFERRAL.value


def test_execute_import_backdates_created_at(db, test_org, test_user):
    """Backdate created_at from submission time using org timezone."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    from app.db.models import Surrogate, SurrogateImport
    from app.services import import_service
    from app.services.import_service import ColumnMapping

    test_org.timezone = "America/New_York"
    db.commit()

    csv_data = create_csv_content(
        [
            {
                "full_name": "Timed User",
                "email": "timed@test.com",
                "submitted_at": "2026-01-02 09:30",
            }
        ]
    )

    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="timed.csv",
        total_rows=1,
        file_content=csv_data,
        status="pending",
    )

    mappings = [
        ColumnMapping(
            csv_column="full_name",
            surrogate_field="full_name",
            transformation=None,
            action="map",
        ),
        ColumnMapping(
            csv_column="email",
            surrogate_field="email",
            transformation=None,
            action="map",
        ),
        ColumnMapping(
            csv_column="submitted_at",
            surrogate_field="created_at",
            transformation="datetime_flexible",
            action="map",
        ),
    ]

    import_service.execute_import_with_mappings(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        import_id=import_record.id,
        file_content=csv_data,
        column_mappings=mappings,
        unknown_column_behavior="ignore",
        backdate_created_at=True,
    )

    surrogate = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == test_org.id,
            Surrogate.email_hash.isnot(None),
        )
        .first()
    )
    assert surrogate is not None

    expected = datetime(2026, 1, 2, 9, 30, tzinfo=ZoneInfo("America/New_York")).astimezone(
        timezone.utc
    )
    stored_created_at = surrogate.created_at
    if stored_created_at.tzinfo is None:
        stored_created_at = stored_created_at.replace(tzinfo=timezone.utc)
    assert stored_created_at == expected

    stored_import = db.query(SurrogateImport).filter(SurrogateImport.id == import_record.id).first()
    warnings = [
        entry
        for entry in (stored_import.errors or [])
        if entry.get("code") == "created_at_backdated"
    ]
    assert warnings
    assert warnings[0]["count"] == 1


def test_execute_import_backdate_invalid_datetime_warns(db, test_org, test_user):
    """Warn when created_at values cannot be parsed."""
    from app.db.models import SurrogateImport
    from app.services import import_service
    from app.services.import_service import ColumnMapping

    csv_data = create_csv_content(
        [
            {
                "full_name": "Bad Date",
                "email": "bad@test.com",
                "submitted_at": "not-a-date",
            }
        ]
    )

    import_record = import_service.create_import_job(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        filename="bad-date.csv",
        total_rows=1,
        file_content=csv_data,
        status="pending",
    )

    mappings = [
        ColumnMapping(
            csv_column="full_name",
            surrogate_field="full_name",
            transformation=None,
            action="map",
        ),
        ColumnMapping(
            csv_column="email",
            surrogate_field="email",
            transformation=None,
            action="map",
        ),
        ColumnMapping(
            csv_column="submitted_at",
            surrogate_field="created_at",
            transformation="datetime_flexible",
            action="map",
        ),
    ]

    import_service.execute_import_with_mappings(
        db=db,
        org_id=test_org.id,
        user_id=test_user.id,
        import_id=import_record.id,
        file_content=csv_data,
        column_mappings=mappings,
        unknown_column_behavior="ignore",
        backdate_created_at=True,
    )

    stored = db.query(SurrogateImport).filter(SurrogateImport.id == import_record.id).first()
    warnings = [
        entry for entry in (stored.errors or []) if entry.get("code") == "created_at_invalid"
    ]
    assert warnings
    assert warnings[0]["count"] == 1


@pytest.mark.asyncio
async def test_csv_import_job_uses_mapping_snapshot(db, test_org, test_user):
    """Worker should honor mapping snapshots for non-legacy headers."""
    from app.db.enums import JobType
    from app.db.models import Job, Surrogate, SurrogateImport
    from app.worker import process_csv_import

    csv_data = create_csv_content(
        [
            {
                "Full Name": "Mapped User",
                "Primary Email": "mapped@test.com",
            }
        ]
    )

    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="mapped.csv",
        file_content=csv_data,
        status="approved",
        total_rows=1,
        column_mapping_snapshot=[
            {
                "csv_column": "Full Name",
                "surrogate_field": "full_name",
                "transformation": None,
                "action": "map",
                "custom_field_key": None,
            },
            {
                "csv_column": "Primary Email",
                "surrogate_field": "email",
                "transformation": None,
                "action": "map",
                "custom_field_key": None,
            },
        ],
        unknown_column_behavior="ignore",
    )
    db.add(import_record)
    db.flush()

    job = Job(
        organization_id=test_org.id,
        job_type=JobType.CSV_IMPORT.value,
        payload={
            "import_id": str(import_record.id),
            "dedupe_action": "skip",
            "use_mappings": True,
            "unknown_column_behavior": "ignore",
        },
    )
    db.add(job)
    db.flush()

    await process_csv_import(db, job)

    surrogate = (
        db.query(Surrogate)
        .filter(
            Surrogate.organization_id == test_org.id,
            Surrogate.email_hash.isnot(None),
        )
        .first()
    )
    assert surrogate is not None
    assert surrogate.full_name == "Mapped User"


@pytest.mark.asyncio
async def test_list_imports_returns_history(authed_client: AsyncClient, db, test_org, test_user):
    """Test listing import history."""
    from app.db.models import SurrogateImport

    # Create import records
    import1 = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="import1.csv",
        status="completed",
        total_rows=10,
        imported_count=10,
        skipped_count=0,
        error_count=0,
    )
    import2 = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="import2.csv",
        status="failed",
        total_rows=5,
        imported_count=0,
        skipped_count=0,
        error_count=5,
    )
    db.add_all([import1, import2])
    db.flush()

    response = await authed_client.get("/surrogates/import")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    filenames = {imp["filename"] for imp in data}
    assert "import1.csv" in filenames
    assert "import2.csv" in filenames


@pytest.mark.asyncio
async def test_get_import_details(authed_client: AsyncClient, db, test_org, test_user):
    """Test getting detailed import information."""
    from app.db.models import SurrogateImport

    # Create import with errors
    import_record = SurrogateImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="detailed.csv",
        status="completed",
        total_rows=3,
        imported_count=2,
        skipped_count=0,
        error_count=1,
        errors=[{"row": 3, "errors": ["Invalid email"]}],
    )
    db.add(import_record)
    db.flush()

    response = await authed_client.get(f"/surrogates/import/{import_record.id}")

    assert response.status_code == 200
    data = response.json()

    assert data["filename"] == "detailed.csv"
    assert data["total_rows"] == 3
    assert data["imported_count"] == 2
    assert data["error_count"] == 1
    assert len(data["errors"]) == 1
    assert data["errors"][0]["row"] == 3


@pytest.mark.asyncio
async def test_get_import_details_not_found(authed_client: AsyncClient):
    """Test getting details for non-existent import."""
    fake_id = uuid.uuid4()
    response = await authed_client.get(f"/surrogates/import/{fake_id}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_imports_org_isolation(authed_client: AsyncClient, db, test_user):
    """Test imports are isolated per organization."""
    from app.db.models import Organization, SurrogateImport

    # Create second org
    org2 = Organization(
        id=uuid.uuid4(),
        name="Org 2",
        slug=f"org2-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)
    db.flush()

    # Create import in org2
    import2 = SurrogateImport(
        organization_id=org2.id,
        created_by_user_id=test_user.id,
        filename="org2import.csv",
        status="completed",
        total_rows=1,
    )
    db.add(import2)
    db.flush()

    # Authed client (org1) should not see org2's imports
    response = await authed_client.get("/surrogates/import")
    assert response.status_code == 200
    data = response.json()

    filenames = [imp["filename"] for imp in data]
    assert "org2import.csv" not in filenames


@pytest.mark.asyncio
async def test_submit_import_requires_csrf(authed_client: AsyncClient, db):
    """Test submit import requires CSRF header."""
    csv_data = create_csv_content([{"email": "alice@test.com"}])

    preview = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert preview.status_code == 200
    import_id = preview.json()["import_id"]

    # Remove CSRF header (create new client without it)
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    # Client without CSRF header
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies=authed_client.cookies,
    ) as no_csrf_client:
        response = await no_csrf_client.post(
            f"/surrogates/import/{import_id}/submit",
            json={"column_mappings": [{"csv_column": "email", "surrogate_field": "email"}]},
        )
        # Should fail due to missing CSRF
        assert response.status_code in [403, 401]

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preview_import_empty_csv(authed_client: AsyncClient):
    """Test enhanced previewing empty CSV."""
    csv_data = b"full_name,email\n"  # Just headers, no data

    response = await authed_client.post(
        "/surrogates/import/preview/enhanced",
        files={"file": ("empty.csv", io.BytesIO(csv_data), "text/csv")},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_rows"] == 0
    assert "import_id" in data
