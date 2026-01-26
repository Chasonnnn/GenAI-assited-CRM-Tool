"""CSV Import service for bulk surrogate creation.

Features:
- Smart encoding/delimiter detection (UTF-8, UTF-16, auto)
- Dynamic column mapping with keyword + semantic analysis
- AI-powered mapping assistance (opt-in)
- Flexible data transformations (dates, heights, booleans)
- Custom field support during import
- Import template management
- Admin approval workflow
- Dedupe by email (against DB + within CSV)
- Async execution via job queue
"""

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.encryption import hash_email
from app.db.enums import SurrogateSource
from app.db.models import ImportTemplate, Surrogate, SurrogateImport
from app.schemas.surrogate import SurrogateCreate
from app.services import surrogate_service
from app.services.import_detection_service import (
    AVAILABLE_SURROGATE_FIELDS,
    ColumnSuggestion,
    analyze_columns,
    detect_file_format,
)
from app.services.import_transformers import transform_value


# =============================================================================
# Column Mapping (Legacy - kept for backward compatibility)
# =============================================================================

# Expected CSV columns (case-insensitive, underscores/spaces normalized)
# NOTE: This is the basic mapping. Full mapping is in import_detection_service.py
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


SUGGESTED_COLUMN_MAPPING: dict[str, dict[str, str | None]] = {
    normalize_column_name("are_you_currently_between_the_ages_of_21_and_36?"): {
        "suggested_field": "is_age_eligible",
        "transformation": "boolean_flexible",
    },
    normalize_column_name(
        "do_you_use_nicotine/tobacco_products_of_any_kind_(cigarettes,_cigars,_vape_devices,_hookahs,_marijuana,_etc.)?"
    ): {
        "suggested_field": "is_non_smoker",
        "transformation": "boolean_inverted",
    },
}


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
        self.duplicate_details: list[dict[str, str]] = []  # [{email, existing_id}]
        self.new_records: int = 0  # Unique emails not in DB
        self.validation_errors: int = 0  # Rows with validation errors
        self.detected_encoding: str | None = None
        self.detected_delimiter: str | None = None
        self.column_suggestions: list[dict[str, str | None]] = []
        self.date_ambiguity_warnings: list[dict[str, str | int]] = []
        self.column_mapping_snapshot: list[dict[str, str]] = []


def parse_csv_file(file_content: bytes | str) -> tuple[list[str], list[list[str]]]:
    """
    Parse CSV content into headers and rows.

    Returns:
        (headers, rows)
    """
    if isinstance(file_content, bytes):
        headers, rows, _encoding, _delimiter = _parse_csv_with_detection(file_content)
        return headers, rows

    reader = csv.reader(io.StringIO(file_content))
    rows = list(reader)

    if not rows:
        return [], []

    headers = rows[0]
    data_rows = rows[1:]

    return headers, data_rows


def _detect_encoding(file_content: bytes) -> str:
    if file_content.startswith(b"\xff\xfe") or file_content.startswith(b"\xfe\xff"):
        return "utf-16"
    if file_content.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if b"\x00" in file_content:
        return "utf-16"
    return "utf-8"


def _detect_delimiter(text: str) -> str:
    sample_line = ""
    for line in text.splitlines():
        if line.strip():
            sample_line = line
            break
    if not sample_line:
        return ","

    candidates = [",", "\t", ";", "|"]
    counts = {c: sample_line.count(c) for c in candidates}
    return max(counts, key=counts.get)


def _parse_csv_with_detection(
    file_content: bytes | str,
) -> tuple[list[str], list[list[str]], str, str]:
    if isinstance(file_content, bytes):
        encoding = _detect_encoding(file_content)
        text = file_content.decode(encoding, errors="replace")
    else:
        encoding = "utf-8"
        text = file_content

    delimiter = _detect_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return [], [], encoding, delimiter

    headers = rows[0]
    if headers and headers[0].startswith("\ufeff"):
        headers[0] = headers[0].lstrip("\ufeff")
    data_rows = rows[1:]
    return headers, data_rows, encoding, delimiter


def _build_column_suggestions(headers: list[str]) -> list[dict[str, str | None]]:
    suggestions: list[dict[str, str | None]] = []
    for header in headers:
        normalized = normalize_column_name(header)
        suggestion = SUGGESTED_COLUMN_MAPPING.get(normalized)
        if not suggestion:
            continue
        suggestions.append(
            {
                "csv_column": header,
                "suggested_field": suggestion.get("suggested_field"),
                "transformation": suggestion.get("transformation"),
            }
        )
    return suggestions


def _detect_date_ambiguity_warnings(
    headers: list[str],
    rows: list[list[str]],
    column_map: dict[int, str],
) -> list[dict[str, str | int]]:
    warnings: list[dict[str, str | int]] = []
    date_columns = [idx for idx, field in column_map.items() if "date" in field or "dob" in field]
    if not date_columns:
        return warnings

    for row_idx, row in enumerate(rows):
        for col_idx in date_columns:
            if col_idx >= len(row):
                continue
            value = row[col_idx].strip()
            if not value or "/" not in value:
                continue
            parts = value.split("/")
            if len(parts) != 3:
                continue
            try:
                month = int(parts[0])
                day = int(parts[1])
            except ValueError:
                continue
            if 1 <= month <= 12 and 1 <= day <= 12 and month != day:
                warnings.append(
                    {
                        "row": row_idx + 2,
                        "column": headers[col_idx],
                        "value": value,
                    }
                )
    return warnings


def _compute_dedup_stats(
    db: Session, org_id: UUID, emails: list[str]
) -> tuple[int, int, list[dict[str, str]], int]:
    """
    Compute deduplication stats for a list of emails.

    Returns:
        (duplicate_emails_db, duplicate_emails_csv, duplicate_details, new_records)
    """
    seen_emails: set[str] = set()
    duplicate_in_csv: set[str] = set()

    for email in emails:
        if email in seen_emails:
            duplicate_in_csv.add(email)
        seen_emails.add(email)

    unique_emails = set(seen_emails)

    duplicate_details: list[dict[str, str]] = []
    if unique_emails:
        email_hashes = {hash_email(email): email for email in unique_emails}
        existing = db.execute(
            select(Surrogate.id, Surrogate.email_hash).where(
                Surrogate.organization_id == org_id,
                Surrogate.is_archived.is_(False),
                Surrogate.email_hash.in_(list(email_hashes.keys())),
            )
        ).all()

        for surrogate_id, email_hash in existing:
            email = email_hashes.get(email_hash)
            if email:
                duplicate_details.append(
                    {
                        "email": email,
                        "existing_id": str(surrogate_id),
                    }
                )

    duplicate_emails_db = len(duplicate_details)
    duplicates_db_emails = {d["email"] for d in duplicate_details}
    new_records = len(unique_emails - duplicates_db_emails) if unique_emails else 0
    duplicate_emails_csv = len(duplicate_in_csv)

    return duplicate_emails_db, duplicate_emails_csv, duplicate_details, new_records


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

    headers, rows, encoding, delimiter = _parse_csv_with_detection(file_content)
    if not headers:
        return preview

    preview.detected_encoding = encoding
    preview.detected_delimiter = delimiter

    # Map columns
    column_map = map_columns(headers)
    preview.detected_columns = list(set(column_map.values()))
    preview.unmapped_columns = [headers[i] for i in range(len(headers)) if i not in column_map]
    preview.total_rows = len(rows)
    preview.column_suggestions = _build_column_suggestions(headers)
    preview.column_mapping_snapshot = [
        {"csv_column": headers[idx], "surrogate_field": field} for idx, field in column_map.items()
    ]
    preview.date_ambiguity_warnings = _detect_date_ambiguity_warnings(headers, rows, column_map)

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

    if csv_emails:
        (
            preview.duplicate_emails_db,
            preview.duplicate_emails_csv,
            preview.duplicate_details,
            preview.new_records,
        ) = _compute_dedup_stats(db, org_id, csv_emails)

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
        self.warnings: list[
            dict[str, object]
        ] = []  # [{level: "warning", column: str, count: int, message: str}]


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
    status: str = "pending",
) -> SurrogateImport:
    """Create an import job record."""
    import_record = SurrogateImport(
        organization_id=org_id,
        created_by_user_id=user_id,
        filename=filename,
        file_content=file_content,
        status=status,
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


def list_pending_imports(db: Session, org_id: UUID) -> list[SurrogateImport]:
    return (
        db.query(SurrogateImport)
        .filter(
            SurrogateImport.organization_id == org_id,
            SurrogateImport.status == "awaiting_approval",
        )
        .order_by(SurrogateImport.created_at.desc())
        .all()
    )


def submit_import_for_approval(
    db: Session,
    import_record: SurrogateImport,
) -> SurrogateImport:
    preview = None
    if import_record.file_content:
        preview = preview_import(
            db=db,
            org_id=import_record.organization_id,
            file_content=import_record.file_content,
        )
        import_record.deduplication_stats = {
            "total": preview.total_rows,
            "duplicate_emails_db": preview.duplicate_emails_db,
            "duplicate_emails_csv": preview.duplicate_emails_csv,
        }
        import_record.total_rows = preview.total_rows
        import_record.column_mapping_snapshot = preview.column_mapping_snapshot
        import_record.date_ambiguity_warnings = preview.date_ambiguity_warnings

    import_record.status = "awaiting_approval"
    db.commit()
    db.refresh(import_record)
    return import_record


# =============================================================================
# Enhanced Import Preview (v2)
# =============================================================================


@dataclass
class EnhancedImportPreview:
    """Enhanced preview with detection and suggestions."""

    # Detection results
    detected_encoding: str
    detected_delimiter: str
    has_header: bool
    total_rows: int

    # Column analysis
    column_suggestions: list[ColumnSuggestion]
    matched_count: int
    unmatched_count: int

    # Sample data
    sample_rows: list[dict[str, str]]

    # Deduplication
    duplicate_emails_db: int
    duplicate_emails_csv: int
    duplicate_details: list[dict]  # [{email: str, existing_id: UUID}]
    new_records: int

    # Validation
    validation_errors: int
    date_ambiguity_warnings: list[dict]

    # Template matching
    matching_templates: list[dict]

    # Available fields
    available_fields: list[str]

    # AI availability
    ai_available: bool


def preview_import_enhanced(
    db: Session,
    org_id: UUID,
    file_content: bytes,
) -> EnhancedImportPreview:
    """
    Generate enhanced preview with smart detection and suggestions.

    Uses the detection service for:
    - Encoding detection (UTF-8, UTF-16, etc.)
    - Delimiter detection (comma, tab, etc.)
    - Column analysis with confidence scoring
    """
    # Detect file format
    detection = detect_file_format(file_content)

    # Analyze columns
    column_suggestions = analyze_columns(detection.headers, detection.sample_rows)

    # Count matched/unmatched
    matched = sum(1 for s in column_suggestions if s.confidence >= 0.5)
    unmatched = len(column_suggestions) - matched

    # Check for email column and duplicates
    email_col_idx = None
    for idx, suggestion in enumerate(column_suggestions):
        if suggestion.suggested_field == "email":
            email_col_idx = idx
            break

    all_emails: list[str] = []
    if email_col_idx is not None:
        decoded = file_content.decode(detection.encoding)
        reader = csv.reader(io.StringIO(decoded), delimiter=detection.delimiter)
        rows = list(reader)
        data_rows = rows[1:] if detection.has_header else rows
        for row in data_rows:
            if email_col_idx < len(row):
                email = row[email_col_idx].strip().lower()
                if email:
                    all_emails.append(email)

    duplicate_details: list[dict[str, str]] = []
    duplicate_emails_db = 0
    duplicate_emails_csv = 0
    new_records = 0
    if all_emails:
        (
            duplicate_emails_db,
            duplicate_emails_csv,
            duplicate_details,
            new_records,
        ) = _compute_dedup_stats(db, org_id, all_emails)

    # Build sample rows dict
    sample_rows_dict = []
    for row in detection.sample_rows[:5]:
        row_dict = {}
        for idx, value in enumerate(row):
            if idx < len(detection.headers):
                row_dict[detection.headers[idx]] = value
        sample_rows_dict.append(row_dict)

    # Check date ambiguity warnings in suggestions
    date_warnings = []
    for suggestion in column_suggestions:
        for warning in suggestion.warnings:
            if "ambiguous" in warning.lower() or "date" in warning.lower():
                date_warnings.append(
                    {
                        "column": suggestion.csv_column,
                        "warning": warning,
                    }
                )

    # Find matching templates
    matching_templates = _find_matching_templates(db, org_id, detection.headers)

    # Check AI availability
    from app.services.import_ai_mapper_service import is_ai_available

    ai_available = is_ai_available(db, org_id)

    return EnhancedImportPreview(
        detected_encoding=detection.encoding,
        detected_delimiter=detection.delimiter,
        has_header=detection.has_header,
        total_rows=detection.row_count,
        column_suggestions=column_suggestions,
        matched_count=matched,
        unmatched_count=unmatched,
        sample_rows=sample_rows_dict,
        duplicate_emails_db=duplicate_emails_db,
        duplicate_emails_csv=duplicate_emails_csv,
        duplicate_details=duplicate_details,
        new_records=new_records,
        validation_errors=0,  # Will be calculated during preview validation
        date_ambiguity_warnings=date_warnings,
        matching_templates=matching_templates,
        available_fields=AVAILABLE_SURROGATE_FIELDS,
        ai_available=ai_available,
    )


def _find_matching_templates(
    db: Session,
    org_id: UUID,
    headers: list[str],
) -> list[dict]:
    """Find templates that might match the current CSV structure."""
    templates = db.query(ImportTemplate).filter(ImportTemplate.organization_id == org_id).all()

    matches = []
    header_set = set(h.lower().strip() for h in headers)

    for template in templates:
        if not template.column_mappings:
            continue

        # Calculate match score
        template_columns = set(
            m.get("csv_column", "").lower().strip() for m in template.column_mappings
        )

        if not template_columns:
            continue

        intersection = header_set & template_columns
        match_score = len(intersection) / len(template_columns) if template_columns else 0

        if match_score >= 0.5:  # At least 50% match
            matches.append(
                {
                    "id": str(template.id),
                    "name": template.name,
                    "match_score": match_score,
                }
            )

    # Sort by match score descending
    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:5]  # Top 5


# =============================================================================
# Enhanced Import Execution (v2)
# =============================================================================


@dataclass
class ColumnMapping:
    """Column mapping configuration."""

    csv_column: str
    surrogate_field: str | None
    transformation: str | None
    action: str  # 'map', 'metadata', 'custom', 'ignore'
    custom_field_key: str | None = None


def execute_import_with_mappings(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    import_id: UUID,
    file_content: bytes,
    column_mappings: list[ColumnMapping],
    unknown_column_behavior: str = "ignore",
) -> ImportResult:
    """
    Execute import with user-specified column mappings.

    Features:
    - Custom column mappings with transformations
    - Custom field value storage
    - Import metadata storage for unmapped columns
    """
    from app.services import custom_field_service

    result = ImportResult()

    # Detect encoding and delimiter
    detection = detect_file_format(file_content)

    if not detection.headers:
        _mark_import_failed(db, org_id, import_id, "Empty CSV file")
        return result

    # Build column index mapping
    header_to_idx = {h.lower().strip(): i for i, h in enumerate(detection.headers)}
    mapping_by_column = {m.csv_column.lower().strip(): m for m in column_mappings}

    # Get existing emails in org
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

    # Track seen emails
    seen_emails: set[str] = set()

    # Parse full file
    decoded = file_content.decode(detection.encoding)
    reader = csv.reader(io.StringIO(decoded), delimiter=detection.delimiter)
    all_rows = list(reader)
    data_rows = all_rows[1:] if detection.has_header else all_rows

    warning_counts: dict[str, int] = {}

    for row_num, row in enumerate(data_rows, start=2):
        row_data: dict[str, Any] = {}
        custom_values: dict[str, Any] = {}
        import_metadata: dict[str, str] = {}

        # Process each column
        for header, idx in header_to_idx.items():
            if idx >= len(row):
                continue

            raw_value = row[idx].strip()
            if not raw_value:
                continue

            mapping = mapping_by_column.get(header)

            if not mapping:
                if unknown_column_behavior == "metadata":
                    import_metadata[detection.headers[idx]] = raw_value
                elif unknown_column_behavior == "warn":
                    original_header = detection.headers[idx]
                    warning_counts[original_header] = warning_counts.get(original_header, 0) + 1
                continue

            if mapping.action == "ignore":
                continue

            if mapping.action == "metadata":
                import_metadata[detection.headers[idx]] = raw_value
                continue

            if mapping.action == "custom" and mapping.custom_field_key:
                # Store for custom field
                if mapping.transformation:
                    transform_result = transform_value(mapping.transformation, raw_value)
                    if transform_result.success:
                        custom_values[mapping.custom_field_key] = transform_result.value
                else:
                    custom_values[mapping.custom_field_key] = raw_value
                continue

            if mapping.action == "map" and mapping.surrogate_field:
                # Apply transformation if specified
                if mapping.transformation:
                    transform_result = transform_value(mapping.transformation, raw_value)
                    if transform_result.success:
                        row_data[mapping.surrogate_field] = transform_result.value
                    else:
                        # Keep original value on transform failure
                        row_data[mapping.surrogate_field] = raw_value
                else:
                    row_data[mapping.surrogate_field] = raw_value

        # Skip empty rows
        if not row_data:
            continue

        # Add import metadata if any
        if import_metadata:
            row_data["import_metadata"] = import_metadata

        # Check email deduplication
        email = str(row_data.get("email", "")).lower()
        email_hash = hash_email(email) if email else None

        if email_hash:
            if email_hash in existing_emails:
                result.skipped += 1
                continue
            if email_hash in seen_emails:
                result.skipped += 1
                continue
            seen_emails.add(email_hash)

        # Set default source
        if "source" not in row_data:
            row_data["source"] = SurrogateSource.IMPORT.value

        # Validate and create surrogate
        try:
            surrogate_data = SurrogateCreate(**row_data)
            surrogate = surrogate_service.create_surrogate(
                db=db,
                org_id=org_id,
                user_id=user_id,
                data=surrogate_data,
            )
            result.imported += 1

            # Set custom field values
            if custom_values:
                custom_field_service.set_bulk_custom_values(
                    db=db,
                    org_id=org_id,
                    surrogate_id=surrogate.id,
                    values=custom_values,
                )

            if email_hash:
                existing_emails.add(email_hash)

        except ValidationError as e:
            result.errors.append(
                {
                    "row": row_num,
                    "errors": [err["msg"] for err in e.errors()],
                }
            )
        except Exception as e:
            result.errors.append(
                {
                    "row": row_num,
                    "errors": [str(e)],
                }
            )

    # Update import record
    if warning_counts:
        for column, count in sorted(warning_counts.items()):
            result.warnings.append(
                {
                    "level": "warning",
                    "column": column,
                    "count": count,
                    "message": "Unmapped column ignored",
                }
            )
    _update_import_completed(db, org_id, import_id, result)

    return result


def _mark_import_failed(
    db: Session,
    org_id: UUID,
    import_id: UUID,
    error_message: str,
) -> None:
    """Mark an import as failed."""
    import_record = get_import(db, org_id, import_id)
    if import_record:
        import_record.status = "failed"
        import_record.imported_count = 0
        import_record.skipped_count = 0
        import_record.error_count = 1
        import_record.errors = [{"row": 0, "errors": [error_message]}]
        import_record.completed_at = datetime.now(timezone.utc)
        db.commit()


def _update_import_completed(
    db: Session,
    org_id: UUID,
    import_id: UUID,
    result: ImportResult,
) -> None:
    """Update import record after completion."""
    import_record = get_import(db, org_id, import_id)
    if import_record:
        import_record.status = "completed"
        import_record.imported_count = result.imported
        import_record.skipped_count = result.skipped
        import_record.error_count = len(result.errors)
        combined_entries = []
        if result.errors:
            combined_entries.extend(result.errors)
        if result.warnings:
            combined_entries.extend(result.warnings)
        import_record.errors = combined_entries if combined_entries else None
        import_record.completed_at = datetime.now(timezone.utc)
        db.commit()


# =============================================================================
# Approval Workflow
# =============================================================================


def submit_for_approval(
    db: Session,
    org_id: UUID,
    import_id: UUID,
    column_mappings: list[ColumnMapping],
    dedup_stats: dict,
    unknown_column_behavior: str = "ignore",
) -> SurrogateImport:
    """
    Submit an import for admin approval.

    Changes status to 'awaiting_approval' and stores the mapping snapshot.
    """
    import_record = get_import(db, org_id, import_id)
    if not import_record:
        raise ValueError(f"Import {import_id} not found")

    if import_record.status != "pending":
        raise ValueError(f"Import is not in pending status (current: {import_record.status})")

    import_record.status = "awaiting_approval"
    import_record.column_mapping_snapshot = [
        {
            "csv_column": m.csv_column,
            "surrogate_field": m.surrogate_field,
            "transformation": m.transformation,
            "action": m.action,
            "custom_field_key": m.custom_field_key,
        }
        for m in column_mappings
    ]
    import_record.deduplication_stats = dedup_stats
    import_record.unknown_column_behavior = unknown_column_behavior

    db.commit()
    db.refresh(import_record)
    return import_record


def approve_import(
    db: Session,
    org_id: UUID,
    import_id: UUID,
    approved_by_user_id: UUID,
) -> SurrogateImport:
    """
    Approve an import for execution.

    Changes status to 'approved' and queues the background job.
    """
    import_record = get_import(db, org_id, import_id)
    if not import_record:
        raise ValueError(f"Import {import_id} not found")

    if import_record.status != "awaiting_approval":
        raise ValueError(f"Import is not awaiting approval (current: {import_record.status})")

    import_record.status = "approved"
    import_record.approved_by_user_id = approved_by_user_id
    import_record.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(import_record)
    return import_record


def reject_import(
    db: Session,
    org_id: UUID,
    import_id: UUID,
    rejected_by_user_id: UUID,
    reason: str,
) -> SurrogateImport:
    """
    Reject an import with a reason.

    Changes status to 'rejected'.
    """
    import_record = get_import(db, org_id, import_id)
    if not import_record:
        raise ValueError(f"Import {import_id} not found")

    if import_record.status != "awaiting_approval":
        raise ValueError(f"Import is not awaiting approval (current: {import_record.status})")

    import_record.status = "rejected"
    import_record.approved_by_user_id = rejected_by_user_id  # Reuse field for rejector
    import_record.rejection_reason = reason
    import_record.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(import_record)
    return import_record


def list_pending_approvals(
    db: Session,
    org_id: UUID,
    limit: int = 50,
) -> list[SurrogateImport]:
    """List imports awaiting approval."""
    return (
        db.query(SurrogateImport)
        .filter(
            SurrogateImport.organization_id == org_id,
            SurrogateImport.status == "awaiting_approval",
        )
        .order_by(SurrogateImport.created_at.desc())
        .limit(limit)
        .all()
    )


# =============================================================================
# Template Helpers
# =============================================================================


def create_import_with_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    filename: str,
    total_rows: int,
    file_content: bytes,
    template_id: UUID | None = None,
    detected_encoding: str | None = None,
    detected_delimiter: str | None = None,
) -> SurrogateImport:
    """Create an import job record with template reference."""
    import_record = SurrogateImport(
        organization_id=org_id,
        created_by_user_id=user_id,
        filename=filename,
        file_content=file_content,
        status="pending",
        total_rows=total_rows,
        template_id=template_id,
        detected_encoding=detected_encoding,
        detected_delimiter=detected_delimiter,
    )
    db.add(import_record)
    db.commit()
    db.refresh(import_record)

    # Increment template usage if used
    if template_id:
        from app.services import import_template_service

        import_template_service.increment_template_usage(db, template_id)

    return import_record
