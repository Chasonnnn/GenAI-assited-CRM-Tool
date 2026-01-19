"""CSV Import service for bulk surrogate creation.

Features:
- Parse CSV with column mapping
- Validate using same rules as SurrogateCreate
- Dedupe by email (against DB + within CSV)
- Async execution via job queue
- Progress tracking
"""

import csv
import io
from datetime import datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import hash_email
from app.db.enums import SurrogateSource
from app.db.models import Surrogate, SurrogateImport
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service


# =============================================================================
# Column Mapping
# =============================================================================

# Expected CSV columns (case-insensitive, underscores/spaces normalized)
COLUMN_MAPPING = {
    # name variations
    "full_name": "full_name",
    "fullname": "full_name",
    "name": "full_name",
    "full name": "full_name",
    # email variations
    "email": "email",
    "email_address": "email",
    "emailaddress": "email",
    # phone variations
    "phone": "phone",
    "phone_number": "phone",
    "phonenumber": "phone",
    "mobile": "phone",
    # state variations
    "state": "state",
    "st": "state",
    # date of birth variations
    "date_of_birth": "date_of_birth",
    "dob": "date_of_birth",
    "birth_date": "date_of_birth",
    "birthdate": "date_of_birth",
    # source
    "source": "source",
}


def normalize_column_name(col: str) -> str:
    """Normalize column name for matching."""
    return col.lower().strip().replace(" ", "_").replace("-", "_")


def map_columns(headers: list[str]) -> dict[int, str]:
    """
    Map CSV column indices to field names.

    Returns:
        Dict of {column_index: field_name}
    """
    mapping = {}
    for i, header in enumerate(headers):
        normalized = normalize_column_name(header)
        if normalized in COLUMN_MAPPING:
            mapping[i] = COLUMN_MAPPING[normalized]
    return mapping


# =============================================================================
# CSV Parsing
# =============================================================================


class ImportPreview:
    """Preview of CSV import before confirmation."""

    def __init__(self) -> None:
        self.total_rows: int = 0
        self.sample_rows: list[dict[str, str]] = []  # First 5 rows
        self.detected_columns: list[str] = []  # Mapped field names
        self.unmapped_columns: list[str] = []  # Columns we couldn't map
        self.duplicate_emails_db: int = 0  # Emails already in DB
        self.duplicate_emails_csv: int = 0  # Duplicate emails within CSV
        self.validation_errors: int = 0  # Rows with validation errors


def parse_csv_file(file_content: bytes | str) -> tuple[list[str], list[list[str]]]:
    """
    Parse CSV content into headers and rows.

    Returns:
        (headers, rows)
    """
    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8-sig")  # Handle BOM

    reader = csv.reader(io.StringIO(file_content))
    rows = list(reader)

    if not rows:
        return [], []

    headers = rows[0]
    data_rows = rows[1:]

    return headers, data_rows


def preview_import(
    db: Session,
    org_id: UUID,
    file_content: bytes | str,
) -> ImportPreview:
    """
    Generate preview of CSV import.

    - Parses CSV
    - Maps columns
    - Counts duplicates (DB + CSV)
    - Validates sample rows
    """
    preview = ImportPreview()

    headers, rows = parse_csv_file(file_content)
    if not headers:
        return preview

    # Map columns
    column_map = map_columns(headers)
    preview.detected_columns = list(set(column_map.values()))
    preview.unmapped_columns = [headers[i] for i in range(len(headers)) if i not in column_map]
    preview.total_rows = len(rows)

    # Extract emails for dedupe check
    email_col_idx = None
    for idx, field in column_map.items():
        if field == "email":
            email_col_idx = idx
            break

    csv_emails = []
    if email_col_idx is not None:
        for row in rows:
            if email_col_idx < len(row):
                email = row[email_col_idx].strip().lower()
                if email:
                    csv_emails.append(email)

    # Check for duplicates within CSV
    seen_emails = set()
    duplicate_in_csv = set()
    for email in csv_emails:
        if email in seen_emails:
            duplicate_in_csv.add(email)
        seen_emails.add(email)
    preview.duplicate_emails_csv = len(duplicate_in_csv)

    # Check for duplicates in DB (active surrogates only)
    if csv_emails:
        email_hashes = [hash_email(email) for email in csv_emails]
        existing = (
            db.execute(
                select(Surrogate.email_hash).where(
                    Surrogate.organization_id == org_id,
                    Surrogate.is_archived.is_(False),
                    Surrogate.email_hash.in_(email_hashes),
                )
            )
            .scalars()
            .all()
        )
        preview.duplicate_emails_db = len(existing)

    # Sample rows with validation
    for i, row in enumerate(rows[:5]):
        row_data = _row_to_dict(row, column_map)
        preview.sample_rows.append(row_data)

        # Try to validate
        try:
            _validate_row(row_data)
        except Exception:
            preview.validation_errors += 1

    return preview


def _row_to_dict(row: list[str], column_map: dict[int, str]) -> dict[str, str]:
    """Convert CSV row to dict using column mapping."""
    result = {}
    for idx, field in column_map.items():
        if idx < len(row):
            value = row[idx].strip()
            if value:
                result[field] = value
    return result


def _validate_row(row_data: dict[str, str]) -> SurrogateCreate:
    """
    Validate row data using SurrogateCreate schema.

    Raises:
        ValidationError if invalid
    """
    # Set defaults for required fields not in CSV
    if "source" not in row_data:
        row_data["source"] = SurrogateSource.IMPORT.value

    return SurrogateCreate(**row_data)


# =============================================================================
# Import Execution
# =============================================================================


class ImportResult:
    """Result of import execution."""

    def __init__(self) -> None:
        self.imported: int = 0
        self.skipped: int = 0
        self.errors: list[dict[str, object]] = []  # [{row: int, errors: list[str]}]


def execute_import(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    import_id: UUID,
    file_content: bytes | str,
    dedupe_action: str = "skip",  # "skip" or "update" (future)
) -> ImportResult:
    """
    Execute CSV import.

    Args:
        dedupe_action: "skip" = skip duplicates, "update" = update existing (future)

    Relies on case creation retry to avoid surrogate_number collisions under concurrency.
    """
    result = ImportResult()

    headers, rows = parse_csv_file(file_content)
    if not headers:
        import_record = (
            db.query(SurrogateImport)
            .filter(
                SurrogateImport.id == import_id,
                SurrogateImport.organization_id == org_id,
            )
            .first()
        )
        if import_record:
            import_record.status = "failed"
            import_record.imported_count = 0
            import_record.skipped_count = 0
            import_record.error_count = 1
            import_record.errors = [{"row": 0, "errors": ["Empty CSV file"]}]
            import_record.completed_at = datetime.now(timezone.utc)
            db.commit()
        return result

    column_map = map_columns(headers)

    # Get existing emails in org (active surrogates only)
    existing_emails = set(
        db.execute(
            select(Surrogate.email_hash).where(
                Surrogate.organization_id == org_id,
                Surrogate.is_archived.is_(False),
            )
        )
        .scalars()
        .all()
    )

    # Track emails seen in this import (for intra-CSV dedupe)
    seen_emails = set()

    for row_num, row in enumerate(rows, start=2):  # 1-indexed, skip header
        row_data = _row_to_dict(row, column_map)

        # Skip empty rows
        if not row_data:
            continue

        email = row_data.get("email", "").lower()
        email_hash = hash_email(email) if email else None

        # Check dedupe
        if email_hash:
            if email_hash in existing_emails:
                result.skipped += 1
                continue
            if email_hash in seen_emails:
                result.skipped += 1
                continue
            seen_emails.add(email_hash)

        # Validate
        try:
            surrogate_data = _validate_row(row_data)
        except ValidationError as e:
            result.errors.append(
                {
                    "row": row_num,
                    "errors": [err["msg"] for err in e.errors()],
                }
            )
            continue

        # Create surrogate
        try:
            surrogate_service.create_surrogate(
                db=db,
                org_id=org_id,
                user_id=user_id,
                data=surrogate_data,
            )
            result.imported += 1

            if email:
                existing_emails.add(email)  # Prevent within-batch duplicates

        except Exception as e:
            result.errors.append(
                {
                    "row": row_num,
                    "errors": [str(e)],
                }
            )

    # Update import record
    import_record = (
        db.query(SurrogateImport)
        .filter(
            SurrogateImport.id == import_id,
            SurrogateImport.organization_id == org_id,
        )
        .first()
    )
    if import_record:
        import_record.status = "completed"
        import_record.imported_count = result.imported
        import_record.skipped_count = result.skipped
        import_record.error_count = len(result.errors)
        import_record.errors = result.errors if result.errors else None
        import_record.completed_at = datetime.now(timezone.utc)

    db.commit()

    return result


# =============================================================================
# Import Job Creation
# =============================================================================


def create_import_job(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    filename: str,
    total_rows: int,
    file_content: bytes | None = None,
) -> SurrogateImport:
    """Create an import job record."""
    import_record = SurrogateImport(
        organization_id=org_id,
        created_by_user_id=user_id,
        filename=filename,
        file_content=file_content,
        status="pending",
        total_rows=total_rows,
    )
    db.add(import_record)
    db.commit()
    db.refresh(import_record)
    return import_record


def get_import(db: Session, org_id: UUID, import_id: UUID) -> SurrogateImport | None:
    """Get import by ID (org-scoped)."""
    return (
        db.query(SurrogateImport)
        .filter(
            SurrogateImport.id == import_id,
            SurrogateImport.organization_id == org_id,
        )
        .first()
    )


def list_imports(
    db: Session,
    org_id: UUID,
    limit: int = 20,
) -> list[SurrogateImport]:
    """List recent imports for org."""
    return (
        db.query(SurrogateImport)
        .filter(
            SurrogateImport.organization_id == org_id,
        )
        .order_by(SurrogateImport.created_at.desc())
        .limit(limit)
        .all()
    )
