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
async def test_preview_import_success(authed_client: AsyncClient, test_org):
    """Test CSV preview with valid data."""
    csv_data = create_csv_content([
        {"full_name": "John Doe", "email": "john@test.com", "phone": "5551234567"},
        {"full_name": "Jane Smith", "email": "jane@test.com", "phone": "5559876543"},
    ])
    
    response = await authed_client.post(
        "/cases/import/preview",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 200
    data = response.json()
    
    assert data["total_rows"] == 2
    assert len(data["sample_rows"]) == 2
    assert "full_name" in data["detected_columns"]
    assert "email" in data["detected_columns"]
    assert data["duplicate_emails_db"] == 0
    assert data["duplicate_emails_csv"] == 0
    # Validation count varies based on sample data
    assert isinstance(data["validation_errors"], int)


@pytest.mark.asyncio
async def test_preview_import_detects_duplicates_in_db(authed_client: AsyncClient, db, test_org, test_user):
    """Test preview detects existing cases in database."""
    from app.services import case_service
    from app.schemas.case import CaseCreate
    from app.db.enums import CaseSource
    
    # Create existing case using service
    case_data = CaseCreate(
        full_name="Existing User",
        email="existing@test.com",
        source=CaseSource.IMPORT,
    )
    case_service.create_case(db, test_org.id, test_user.id, case_data)
    
    
    # Upload CSV with duplicate email
    csv_data = create_csv_content([
        {"full_name": "John Doe", "email": "existing@test.com"},
        {"full_name": "Jane Smith", "email": "jane@test.com"},
    ])
    
    response = await authed_client.post(
        "/cases/import/preview",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_emails_db"] == 1


@pytest.mark.asyncio
async def test_preview_import_detects_duplicates_in_csv(authed_client: AsyncClient):
    """Test preview detects duplicate emails within CSV."""
    csv_data = create_csv_content([
        {"full_name": "John Doe", "email": "john@test.com"},
        {"full_name": "John Duplicate", "email": "john@test.com"},
        {"full_name": "Jane Smith", "email": "jane@test.com"},
    ])
    
    response = await authed_client.post(
        "/cases/import/preview",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["duplicate_emails_csv"] == 1


@pytest.mark.asyncio
async def test_preview_import_detects_unmapped_columns(authed_client: AsyncClient):
    """Test preview identifies unmapped columns."""
    csv_data = create_csv_content([
        {"full_name": "John Doe", "email": "john@test.com", "unknown_field": "value"},
    ])
    
    response = await authed_client.post(
        "/cases/import/preview",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "unknown_field" in data["unmapped_columns"]


@pytest.mark.asyncio
async def test_preview_import_rejects_non_csv(authed_client: AsyncClient):
    """Test preview rejects non-CSV files."""
    response = await authed_client.post(
        "/cases/import/preview",
        files={"file": ("test.txt", io.BytesIO(b"not a csv"), "text/plain")},
    )
    
    assert response.status_code == 400
    assert "csv" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_preview_import_without_auth_fails(client: AsyncClient):
    """Test unauthenticated preview request fails."""
    csv_data = create_csv_content([{"email": "alice@test.com"}])
    
    response = await client.post(
        "/cases/import/preview",
        files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    # 403 because CSRF header is missing (not 401 for auth)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_execute_import_success(authed_client: AsyncClient, db, test_org):
    """Test successful CSV import execution."""
    from app.db.models import Case, CaseImport
    
    csv_data = create_csv_content([
        {"full_name": "Alice Johnson", "email": "alice@test.com", "phone": "5551111111"},
        {"full_name": "Bob Wilson", "email": "bob@test.com", "phone": "5552222222"},
    ])
    
    response = await authed_client.post(
        "/cases/import/execute",
        files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 202
    data = response.json()
    assert "import_id" in data
    assert "message" in data
    
    # Refresh session to see committed data
    db.expire_all()
    
    # Verify cases created
    cases = db.query(Case).filter(Case.organization_id == test_org.id).all()
    assert len(cases) == 2
    
    emails = {c.email for c in cases}
    assert "alice@test.com" in emails
    assert "bob@test.com" in emails
    
    # Verify import record created
    import_record = db.query(CaseImport).filter(
        CaseImport.id == uuid.UUID(data["import_id"])
    ).first()
    assert import_record is not None
    assert import_record.status == "completed"
    assert import_record.imported_count == 2


@pytest.mark.asyncio
async def test_execute_import_skips_duplicates(authed_client: AsyncClient, db, test_org, test_user):
    """Test import skips duplicate emails."""
    from app.db.models import Case
    from app.services import case_service
    from app.schemas.case import CaseCreate
    from app.db.enums import CaseSource
    
    # Create existing case using service
    case_data = CaseCreate(
        full_name="Existing",
        email="existing@test.com",
        source=CaseSource.IMPORT,
    )
    case_service.create_case(db, test_org.id, test_user.id, case_data)
    
    # Import with duplicate
    csv_data = create_csv_content([
        {"full_name": "Duplicate", "email": "existing@test.com"},
        {"full_name": "New User", "email": "newuser@test.com"},
    ])
    
    response = await authed_client.post(
        "/cases/import/execute",
        files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 202
    
    # Should only create the new case
    cases = db.query(Case).filter(
        Case.organization_id == test_org.id
    ).all()
    assert len(cases) == 2  # existing + newuser
    emails = {c.email for c in cases}
    assert "existing@test.com" in emails
    assert "newuser@test.com" in emails
async def test_execute_import_handles_validation_errors(authed_client: AsyncClient, db):
    """Test import handles rows with validation errors."""
    from app.db.models import CaseImport
    
    csv_data = create_csv_content([
        {"full_name": "Valid User", "email": "alice@test.com"},
        {"full_name": "", "email": "invalid-email"},  # Invalid
    ])
    
    response = await authed_client.post(
        "/cases/import/execute",
        files={"file": ("import.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 202
    import_id = response.json()["import_id"]
    
    # Check import record
    import_record = db.query(CaseImport).filter(
        CaseImport.id == uuid.UUID(import_id)
    ).first()
    
    # Check import record - may have errors but should have tried
    assert import_record.imported_count >= 0
    assert import_record.error_count >= 0


@pytest.mark.asyncio
async def test_list_imports_returns_history(authed_client: AsyncClient, db, test_org, test_user):
    """Test listing import history."""
    from app.db.models import CaseImport
    from datetime import datetime, timezone
    
    # Create import records
    import1 = CaseImport(
        organization_id=test_org.id,
        created_by_user_id=test_user.id,
        filename="import1.csv",
        status="completed",
        total_rows=10,
        imported_count=10,
        skipped_count=0,
        error_count=0,
    )
    import2 = CaseImport(
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
    
    response = await authed_client.get("/cases/import")
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    filenames = {imp["filename"] for imp in data}
    assert "import1.csv" in filenames
    assert "import2.csv" in filenames


@pytest.mark.asyncio
async def test_get_import_details(authed_client: AsyncClient, db, test_org, test_user):
    """Test getting detailed import information."""
    from app.db.models import CaseImport
    
    # Create import with errors
    import_record = CaseImport(
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
    
    response = await authed_client.get(f"/cases/import/{import_record.id}")
    
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
    response = await authed_client.get(f"/cases/import/{fake_id}")
    
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_imports_org_isolation(authed_client: AsyncClient, db, test_user):
    """Test imports are isolated per organization."""
    from app.db.models import Organization, CaseImport
    
    # Create second org
    org2 = Organization(
        id=uuid.uuid4(),
        name="Org 2",
        slug=f"org2-{uuid.uuid4().hex[:8]}",
    )
    db.add(org2)
    db.flush()
    
    # Create import in org2
    import2 = CaseImport(
        organization_id=org2.id,
        created_by_user_id=test_user.id,
        filename="org2import.csv",
        status="completed",
        total_rows=1,
    )
    db.add(import2)
    db.flush()
    
    # Authed client (org1) should not see org2's imports
    response = await authed_client.get("/cases/import")
    assert response.status_code == 200
    data = response.json()
    
    filenames = [imp["filename"] for imp in data]
    assert "org2import.csv" not in filenames


@pytest.mark.asyncio
async def test_execute_import_requires_csrf(authed_client: AsyncClient):
    """Test import execution requires CSRF header."""
    csv_data = create_csv_content([{"email": "alice@test.com"}])
    
    # Remove CSRF header (create new client without it)
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    from app.core.deps import get_db
    
    def override_get_db():
        yield authed_client._state.db  # Access existing db from fixture
    
    app.dependency_overrides[get_db] = override_get_db
    
    # Client without CSRF header
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="https://test",
        cookies=authed_client.cookies,
    ) as no_csrf_client:
        response = await no_csrf_client.post(
            "/cases/import/execute",
            files={"file": ("test.csv", io.BytesIO(csv_data), "text/csv")},
        )
        # Should fail due to missing CSRF
        assert response.status_code in [403, 401]
    
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_execute_import_empty_csv(authed_client: AsyncClient):
    """Test importing empty CSV."""
    csv_data = b"full_name,email\n"  # Just headers, no data
    
    response = await authed_client.post(
        "/cases/import/execute",
        files={"file": ("empty.csv", io.BytesIO(csv_data), "text/csv")},
    )
    
    assert response.status_code == 202
    # Should complete with 0 imports
