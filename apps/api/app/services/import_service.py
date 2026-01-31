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
import hashlib
import io
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
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
    AVAILABLE_IMPORT_FIELDS,
    ColumnSuggestion,
    analyze_columns_with_learning,
    detect_file_format,
    normalize_column_name,
)
from app.services.import_transformers import transform_value
from app.utils.datetime_parsing import parse_datetime_with_timezone

if TYPE_CHECKING:
    from app.db.models import Job


ACTIVE_IMPORT_STATUSES = {
    "pending",
    "awaiting_approval",
    "approved",
    "processing",
    "running",
}

VALIDATION_MODE_SKIP = "skip_invalid_rows"
VALIDATION_MODE_DROP_FIELDS = "drop_invalid_fields"
VALIDATION_MODES = {VALIDATION_MODE_SKIP, VALIDATION_MODE_DROP_FIELDS}
REQUIRED_IMPORT_FIELDS = {"full_name", "email"}


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
    # created time variations
    "created_at": "created_at",
    "created_time": "created_at",
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


def compute_file_hash(file_content: bytes | str) -> str:
    """Compute a stable hash for a CSV file to detect duplicate uploads."""
    if isinstance(file_content, str):
        payload = file_content.encode("utf-8")
    else:
        payload = file_content
    return hashlib.sha256(payload).hexdigest()


def find_active_import_by_hash(db: Session, org_id: UUID, file_hash: str) -> SurrogateImport | None:
    """Find an active import with the same file hash for an org."""
    return (
        db.query(SurrogateImport)
        .filter(
            SurrogateImport.organization_id == org_id,
            SurrogateImport.file_hash == file_hash,
            SurrogateImport.status.in_(list(ACTIVE_IMPORT_STATUSES)),
        )
        .order_by(SurrogateImport.created_at.desc())
        .first()
    )


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


def _row_to_dict(row: list[str], column_map: dict[int, str]) -> dict[str, str]:
    """Convert CSV row to dict using column mapping."""
    result = {}
    for idx, field_name in column_map.items():
        if idx < len(row):
            value = row[idx].strip()
            if value:
                result[field_name] = value
    return result


def _validate_row(
    row_data: dict[str, str],
    default_source: SurrogateSource | str | None = None,
) -> SurrogateCreate:
    """
    Validate row data using SurrogateCreate schema.

    Raises:
        ValidationError if invalid
    """
    # Apply default source if CSV didn't provide one
    if "source" not in row_data and default_source is not None:
        if isinstance(default_source, SurrogateSource):
            row_data["source"] = default_source.value
        else:
            row_data["source"] = str(default_source)

    return SurrogateCreate(**row_data)


def _normalize_validation_mode(value: str | None) -> str:
    if value in VALIDATION_MODES:
        return value
    return VALIDATION_MODE_SKIP


def _format_validation_errors(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for err in exc.errors():
        loc = err.get("loc") or []
        msg = err.get("msg") or "Invalid value"
        if loc:
            path = ".".join(str(part) for part in loc if part is not None)
            if path:
                messages.append(f"{path}: {msg}")
                continue
        messages.append(msg)
    return messages


def _validate_row_with_mode(
    row_data: dict[str, Any],
    default_source: SurrogateSource | str | None,
    validation_mode: str,
    dropped_field_counts: dict[str, int],
) -> SurrogateCreate:
    normalized_mode = _normalize_validation_mode(validation_mode)
    if normalized_mode != VALIDATION_MODE_DROP_FIELDS:
        return _validate_row(row_data, default_source)

    try:
        return _validate_row(row_data, default_source)
    except ValidationError as e:
        invalid_fields: set[str] = set()
        has_required_error = False
        for err in e.errors():
            loc = err.get("loc") or []
            field = loc[0] if loc else None
            if isinstance(field, str):
                if field in REQUIRED_IMPORT_FIELDS:
                    has_required_error = True
                else:
                    invalid_fields.add(field)

        if invalid_fields:
            for field in invalid_fields:
                if field in row_data:
                    row_data.pop(field, None)
                    dropped_field_counts[field] = dropped_field_counts.get(field, 0) + 1

        if has_required_error or not invalid_fields:
            raise

        return _validate_row(row_data, default_source)


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
    default_source: SurrogateSource | str | None = None,
    validation_mode: str | None = None,
) -> ImportResult:
    """
    Execute CSV import.

    Args:
        dedupe_action: "skip" = skip duplicates, "update" = update existing (future)

    Relies on case creation retry to avoid surrogate_number collisions under concurrency.
    """
    result = ImportResult()
    normalized_validation_mode = _normalize_validation_mode(validation_mode)

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

    dropped_field_counts: dict[str, int] = {}

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
            surrogate_data = _validate_row_with_mode(
                row_data,
                default_source,
                normalized_validation_mode,
                dropped_field_counts,
            )
        except ValidationError as e:
            result.errors.append(
                {
                    "row": row_num,
                    "errors": _format_validation_errors(e),
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
    if dropped_field_counts:
        for field, count in sorted(dropped_field_counts.items()):
            result.warnings.append(
                {
                    "level": "warning",
                    "code": "invalid_field_dropped",
                    "field": field,
                    "count": count,
                    "message": f"Dropped invalid values for {field} in {count} row(s).",
                }
            )
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
    file_hash: str | None = None,
    default_source: SurrogateSource | str | None = None,
) -> SurrogateImport:
    """Create an import job record."""
    if file_content and not file_hash:
        file_hash = compute_file_hash(file_content)

    import_record = SurrogateImport(
        organization_id=org_id,
        created_by_user_id=user_id,
        filename=filename,
        file_content=file_content,
        file_hash=file_hash,
        default_source=default_source.value
        if isinstance(default_source, SurrogateSource)
        else default_source,
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
            SurrogateImport.status != "cancelled",
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

    # Auto-applied template (if >80% match)
    auto_applied_template: dict | None = None  # {id, name, match_score}
    template_unknown_column_behavior: str | None = None  # "ignore", "metadata", "warn"

    # AI auto-trigger results
    ai_auto_triggered: bool = False
    ai_mapped_columns: list[str] = field(default_factory=list)


async def preview_import_enhanced(
    db: Session,
    org_id: UUID,
    file_content: bytes,
    *,
    apply_template: bool = True,
    enable_ai: bool = False,
) -> EnhancedImportPreview:
    """
    Generate enhanced preview with smart detection and suggestions.

    Uses the detection service for:
    - Encoding detection (UTF-8, UTF-16, etc.)
    - Delimiter detection (comma, tab, etc.)
    - Column analysis with confidence scoring (including learning)
    - Template auto-apply (>80% match)
    - AI auto-trigger for unmatched columns (non-blocking)
    """
    import asyncio
    import logging

    logger = logging.getLogger(__name__)

    # Detect file format
    detection = detect_file_format(file_content)

    # Analyze columns WITH learning from previous corrections
    column_suggestions = analyze_columns_with_learning(
        db,
        org_id,
        detection.headers,
        detection.sample_rows,
        allowed_fields=AVAILABLE_IMPORT_FIELDS,
    )

    # Find matching templates
    matching_templates = _find_matching_templates(db, org_id, detection.headers)

    # Auto-apply best template if score >= 0.8 (FULL OVERRIDE)
    auto_applied_template: dict | None = None
    template_unknown_behavior: str | None = None
    if apply_template and matching_templates and matching_templates[0]["match_score"] >= 0.8:
        best_template = matching_templates[0]
        template = db.get(ImportTemplate, UUID(best_template["id"]))
        if template and template.column_mappings:
            # Apply full template payload - OVERRIDES existing suggestions
            column_suggestions = _apply_template_to_suggestions(
                column_suggestions,
                template.column_mappings,
            )
            auto_applied_template = best_template
            # Carry template's unknown_column_behavior as default (user can override)
            template_unknown_behavior = template.unknown_column_behavior

    # Check AI availability
    from app.services.import_ai_mapper_service import is_ai_available

    ai_available = is_ai_available(db, org_id)

    # Identify low-confidence columns after template application
    low_confidence_cols = [
        s for s in column_suggestions if s.confidence < 0.5 and s.suggested_field is None
    ]

    # Auto-trigger AI for unmatched columns (explicit opt-in, limit 20, non-blocking)
    ai_mapped_columns: list[str] = []
    ai_auto_triggered = False
    if enable_ai and low_confidence_cols and len(low_confidence_cols) <= 20 and ai_available:
        ai_auto_triggered = True
        try:
            from app.services.import_ai_mapper_service import ai_suggest_mappings

            ai_suggestions = await asyncio.wait_for(
                ai_suggest_mappings(db, org_id, low_confidence_cols),
                timeout=2.0,
            )

            # AI returns list[ColumnSuggestion] directly
            for ai_suggestion in ai_suggestions:
                if ai_suggestion.suggested_field and ai_suggestion.confidence > 0.3:
                    # Find and update matching column in original list
                    for idx, orig in enumerate(column_suggestions):
                        if orig.csv_column == ai_suggestion.csv_column:
                            # Replace with AI suggestion (already has reason set)
                            column_suggestions[idx] = ai_suggestion
                            ai_mapped_columns.append(ai_suggestion.csv_column)
                            break
        except asyncio.TimeoutError:
            logger.warning("AI auto-mapping timed out (non-blocking)")
        except Exception as e:
            logger.warning(f"AI auto-mapping failed (non-blocking): {e}")
            # Continue without AI - non-blocking failure

    # RECOMPUTE all derived values after template/AI overrides
    matched = sum(1 for s in column_suggestions if s.confidence >= 0.5)
    unmatched = len(column_suggestions) - matched

    decoded = file_content.decode(detection.encoding)
    reader = csv.reader(io.StringIO(decoded), delimiter=detection.delimiter)
    rows = list(reader)
    data_rows = rows[1:] if detection.has_header else rows

    # Check for email column and duplicates (recompute in case email mapping changed)
    email_col_idx = None
    for idx, suggestion in enumerate(column_suggestions):
        if suggestion.suggested_field == "email":
            email_col_idx = idx
            break

    all_emails: list[str] = []
    if email_col_idx is not None:
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

    # Check date ambiguity warnings in data (recompute for date columns)
    date_column_map: dict[int, str] = {}
    for idx, suggestion in enumerate(column_suggestions):
        if (
            suggestion.suggested_field
            and ("date" in suggestion.suggested_field or "dob" in suggestion.suggested_field)
            and suggestion.confidence >= 0.5
        ):
            date_column_map[idx] = suggestion.suggested_field

    date_warnings = _detect_date_ambiguity_warnings(
        detection.headers,
        data_rows,
        date_column_map,
    )

    # Basic validation errors (focus on required fields only)
    validation_errors = 0
    required_map: dict[int, str] = {}
    for idx, suggestion in enumerate(column_suggestions):
        if suggestion.suggested_field in ("full_name", "email") and suggestion.confidence >= 0.5:
            required_map[idx] = suggestion.suggested_field

    if required_map:
        for row in detection.sample_rows[:5]:
            row_data: dict[str, str] = {}
            for idx, req_field in required_map.items():
                if idx < len(row):
                    value = row[idx].strip()
                    if value:
                        row_data[req_field] = value
            try:
                _validate_row(row_data, None)
            except Exception:
                validation_errors += 1

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
        validation_errors=validation_errors,
        date_ambiguity_warnings=date_warnings,
        matching_templates=matching_templates,
        available_fields=AVAILABLE_IMPORT_FIELDS,
        ai_available=ai_available,
        auto_applied_template=auto_applied_template,
        template_unknown_column_behavior=template_unknown_behavior,
        ai_auto_triggered=ai_auto_triggered,
        ai_mapped_columns=ai_mapped_columns,
    )


def _apply_template_to_suggestions(
    suggestions: list[ColumnSuggestion],
    template_mappings: list[dict],
) -> list[ColumnSuggestion]:
    """
    Apply template mappings to column suggestions.

    OVERRIDES existing suggestions (not just fills blanks).
    Applies full payload: surrogate_field, transformation, action, custom_field_key.
    """
    from app.services.import_detection_service import ConfidenceLevel
    from app.services.import_transformers import get_suggested_transformer

    # Build lookup using normalize_column_name() for consistent matching
    template_map = {normalize_column_name(m.get("csv_column", "")): m for m in template_mappings}

    result = []
    for suggestion in suggestions:
        normalized = normalize_column_name(suggestion.csv_column)
        if normalized in template_map:
            mapping = template_map[normalized]
            action = mapping.get("action", "map")

            # For custom fields, set suggested_field="custom.<key>" so UI can infer
            suggested_field = mapping.get("surrogate_field")
            if action == "custom" and mapping.get("custom_field_key"):
                suggested_field = f"custom.{mapping['custom_field_key']}"

            # Get transformation from template or infer from field
            transformation = mapping.get("transformation")
            if not transformation and suggested_field and not suggested_field.startswith("custom."):
                transformation = get_suggested_transformer(suggested_field)

            # Apply FULL template payload (override whatever was detected)
            result.append(
                ColumnSuggestion(
                    csv_column=suggestion.csv_column,
                    suggested_field=suggested_field,
                    confidence=0.95,  # High confidence from template
                    confidence_level=ConfidenceLevel.HIGH,
                    transformation=transformation,
                    sample_values=suggestion.sample_values,
                    reason="Matched from saved template",
                    default_action=action,
                )
            )
        else:
            # Keep original suggestion for columns not in template
            result.append(suggestion)

    return result


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


def build_column_mappings_from_snapshot(snapshot: list[dict]) -> list[ColumnMapping]:
    """Build ColumnMapping objects from a stored mapping snapshot."""
    mappings: list[ColumnMapping] = []
    for item in snapshot:
        if not isinstance(item, dict):
            continue
        action = item.get("action") or ("map" if item.get("surrogate_field") else "ignore")
        mappings.append(
            ColumnMapping(
                csv_column=item.get("csv_column", ""),
                surrogate_field=item.get("surrogate_field"),
                transformation=item.get("transformation"),
                action=action,
                custom_field_key=item.get("custom_field_key"),
            )
        )
    return mappings


def execute_import_with_mappings(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    import_id: UUID,
    file_content: bytes,
    column_mappings: list[ColumnMapping],
    unknown_column_behavior: str = "ignore",
    backdate_created_at: bool = False,
    default_source: SurrogateSource | str | None = None,
    validation_mode: str | None = None,
) -> ImportResult:
    """
    Execute import with user-specified column mappings.

    Features:
    - Custom column mappings with transformations
    - Custom field value storage
    - Import metadata storage for unmapped columns
    - Optional backdating of created_at from mapped submission time
    """
    from app.services import custom_field_service

    result = ImportResult()
    normalized_validation_mode = _normalize_validation_mode(validation_mode)
    from app.db.models import Organization

    org_timezone: str | None = None
    org = db.get(Organization, org_id)
    if org:
        org_timezone = org.timezone

    now_utc = datetime.now(timezone.utc)
    created_at_backdated = 0
    created_at_future = 0
    created_at_invalid = 0
    created_at_date_only = 0
    created_at_disabled = 0
    created_at_timezone_fallback = 0

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
    dropped_field_counts: dict[str, int] = {}

    for row_num, row in enumerate(data_rows, start=2):
        row_data: dict[str, Any] = {}
        custom_values: dict[str, Any] = {}
        import_metadata: dict[str, str] = {}
        row_created_at: datetime | None = None

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
                if mapping.surrogate_field == "created_at":
                    if not backdate_created_at:
                        created_at_disabled += 1
                        import_metadata[detection.headers[idx]] = raw_value
                        continue

                    parsed = parse_datetime_with_timezone(raw_value, org_timezone)
                    if parsed.used_fallback_timezone:
                        created_at_timezone_fallback += 1
                    if parsed.date_only:
                        created_at_date_only += 1
                    if parsed.value is None:
                        created_at_invalid += 1
                    else:
                        row_created_at = parsed.value
                        if row_created_at > now_utc:
                            created_at_future += 1
                        elif row_created_at < now_utc:
                            created_at_backdated += 1
                    continue

                # Apply transformation if specified
                if mapping.transformation:
                    transform_result = transform_value(mapping.transformation, raw_value)
                    if transform_result.success:
                        row_data[mapping.surrogate_field] = transform_result.value
                    else:
                        if normalized_validation_mode == VALIDATION_MODE_DROP_FIELDS:
                            dropped_field_counts[mapping.surrogate_field] = (
                                dropped_field_counts.get(mapping.surrogate_field, 0) + 1
                            )
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

        # Validate and create surrogate
        try:
            surrogate_data = _validate_row_with_mode(
                row_data,
                default_source,
                normalized_validation_mode,
                dropped_field_counts,
            )
            surrogate = surrogate_service.create_surrogate(
                db=db,
                org_id=org_id,
                user_id=user_id,
                data=surrogate_data,
                created_at_override=row_created_at,
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
                    "errors": _format_validation_errors(e),
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
    if dropped_field_counts:
        for field, count in sorted(dropped_field_counts.items()):
            result.warnings.append(
                {
                    "level": "warning",
                    "code": "invalid_field_dropped",
                    "field": field,
                    "count": count,
                    "message": f"Dropped invalid values for {field} in {count} row(s).",
                }
            )
    if created_at_disabled:
        result.warnings.append(
            {
                "level": "warning",
                "code": "created_at_disabled",
                "count": created_at_disabled,
                "message": "Created_at mapping ignored because backdating is disabled.",
            }
        )
    if created_at_invalid:
        result.warnings.append(
            {
                "level": "warning",
                "code": "created_at_invalid",
                "count": created_at_invalid,
                "message": "Created_at could not be parsed; used import time instead.",
            }
        )
    if created_at_date_only:
        result.warnings.append(
            {
                "level": "warning",
                "code": "created_at_date_only",
                "count": created_at_date_only,
                "message": "Created_at date-only values assumed 12:00 local time.",
            }
        )
    if created_at_timezone_fallback:
        result.warnings.append(
            {
                "level": "warning",
                "code": "created_at_timezone_fallback",
                "count": created_at_timezone_fallback,
                "message": "Organization timezone invalid; default timezone applied.",
            }
        )
    if created_at_backdated:
        result.warnings.append(
            {
                "level": "warning",
                "code": "created_at_backdated",
                "count": created_at_backdated,
                "message": "Created_at backdated from submission time.",
            }
        )
    if created_at_future:
        result.warnings.append(
            {
                "level": "warning",
                "code": "created_at_future",
                "count": created_at_future,
                "message": "Created_at is in the future for some rows.",
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
# Learning from Corrections
# =============================================================================


def store_mapping_corrections(
    db: Session,
    org_id: UUID,
    original_suggestions: list[dict],
    final_mappings: list[ColumnMapping],
) -> None:
    """
    Compare original suggestions to final mappings and store corrections.
    Called when import is confirmed/approved.

    SKIPS action="ignore" to avoid teaching the system to hide columns permanently.
    """
    from sqlalchemy import func

    from app.db.models.surrogates import ImportMappingCorrection
    from app.services.import_detection_service import normalize_column_name

    # Build lookup of original suggestions using normalize_column_name()
    original_map = {normalize_column_name(s["csv_column"]): s for s in original_suggestions}

    for final in final_mappings:
        # SKIP ignore - don't teach system to hide columns
        if final.action == "ignore":
            continue

        normalized = normalize_column_name(final.csv_column)

        # Skip empty or invalid column names
        if not normalized:
            continue

        original = original_map.get(normalized)

        corrected_field = final.surrogate_field
        if final.action == "custom":
            if not final.custom_field_key:
                continue
            corrected_field = f"custom.{final.custom_field_key}"

        # Skip if no change from original suggestion (and transformation unchanged)
        if final.action == "map" and original:
            if (
                original.get("suggested_field") == corrected_field
                and original.get("transformation") == final.transformation
            ):
                continue

        # Upsert correction
        existing = (
            db.query(ImportMappingCorrection)
            .filter(
                ImportMappingCorrection.organization_id == org_id,
                ImportMappingCorrection.column_name_normalized == normalized,
            )
            .first()
        )

        if existing:
            if existing.corrected_field == corrected_field:
                # Same correction, increment count
                existing.times_used += 1
            else:
                # Different correction, reset
                existing.corrected_field = corrected_field
                existing.corrected_transformation = final.transformation
                existing.corrected_action = final.action
                existing.times_used = 1
            existing.last_used_at = func.now()
        else:
            db.add(
                ImportMappingCorrection(
                    organization_id=org_id,
                    column_name_normalized=normalized,
                    original_suggestion=original.get("suggested_field") if original else None,
                    corrected_field=corrected_field,
                    corrected_transformation=final.transformation,
                    corrected_action=final.action,
                )
            )


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
    backdate_created_at: bool = False,
    default_source: SurrogateSource | str | None = None,
    validation_mode: str | None = None,
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
    import_record.backdate_created_at = backdate_created_at
    import_record.validation_mode = _normalize_validation_mode(validation_mode)
    if default_source is None:
        import_record.default_source = SurrogateSource.MANUAL.value
    elif isinstance(default_source, SurrogateSource):
        import_record.default_source = default_source.value
    else:
        import_record.default_source = str(default_source)

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
    Also stores mapping corrections for learning.
    """
    import_record = get_import(db, org_id, import_id)
    if not import_record:
        raise ValueError(f"Import {import_id} not found")

    if import_record.status != "awaiting_approval":
        raise ValueError(f"Import is not awaiting approval (current: {import_record.status})")

    # Store corrections for learning (before approval to ensure data is captured)
    if import_record.original_suggestions_snapshot and import_record.column_mapping_snapshot:
        final_mappings = [
            ColumnMapping(
                csv_column=m["csv_column"],
                surrogate_field=m.get("surrogate_field"),
                transformation=m.get("transformation"),
                action=m.get("action", "map"),
                custom_field_key=m.get("custom_field_key"),
            )
            for m in import_record.column_mapping_snapshot
        ]
        store_mapping_corrections(
            db,
            org_id,
            import_record.original_suggestions_snapshot,
            final_mappings,
        )

    import_record.status = "approved"
    import_record.approved_by_user_id = approved_by_user_id
    import_record.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(import_record)
    return import_record


def queue_import_job(
    db: Session,
    org_id: UUID,
    import_record: SurrogateImport,
    *,
    dedupe_action: str = "skip",
    use_mappings: bool = True,
    unknown_column_behavior: str | None = None,
) -> tuple["Job", bool]:
    """
    Queue a CSV import job for an approved/failed import.

    Returns:
        (job, already_queued)
    """
    from app.db.enums import JobStatus, JobType
    from app.db.models import Job
    from app.services import job_service

    if import_record.organization_id != org_id:
        raise ValueError("Import not found")

    if import_record.status in {"running", "processing"}:
        raise ValueError("Import is already running")
    if import_record.status == "cancelled":
        raise ValueError("Import was cancelled")
    if import_record.status not in {"approved", "failed"}:
        raise ValueError(f"Import is not approved for processing (current: {import_record.status})")
    if not import_record.file_content:
        raise ValueError("Import file missing; re-upload to retry")

    existing = (
        db.query(Job)
        .filter(
            Job.organization_id == org_id,
            Job.job_type == JobType.CSV_IMPORT.value,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value]),
            Job.payload["import_id"].astext == str(import_record.id),
        )
        .first()
    )
    if existing:
        return existing, True

    if import_record.status == "failed":
        import_record.status = "approved"
        import_record.completed_at = None
        import_record.error_count = 0
        import_record.errors = None
        import_record.imported_count = 0
        import_record.skipped_count = 0
        db.commit()

    job = job_service.schedule_job(
        db=db,
        org_id=org_id,
        job_type=JobType.CSV_IMPORT,
        payload={
            "import_id": str(import_record.id),
            "dedupe_action": dedupe_action,
            "use_mappings": use_mappings,
            "unknown_column_behavior": unknown_column_behavior
            or import_record.unknown_column_behavior
            or "ignore",
            "validation_mode": _normalize_validation_mode(import_record.validation_mode),
        },
    )
    return job, False


def run_import_execution(
    db: Session,
    org_id: UUID,
    import_record: SurrogateImport,
    *,
    use_mappings: bool | None = None,
    dedupe_action: str = "skip",
    unknown_column_behavior: str | None = None,
    validation_mode: str | None = None,
) -> None:
    """Execute an import immediately using stored content and mappings."""
    if not import_record.file_content:
        raise ValueError("Import record missing file content")

    import_record.status = "running"
    db.commit()

    try:
        mapping_snapshot = import_record.column_mapping_snapshot or []
        resolved_use_mappings = use_mappings if use_mappings is not None else bool(mapping_snapshot)
        resolved_unknown_behavior = (
            unknown_column_behavior or import_record.unknown_column_behavior or "ignore"
        )
        resolved_default_source = getattr(import_record, "default_source", None)
        resolved_validation_mode = _normalize_validation_mode(
            validation_mode or getattr(import_record, "validation_mode", None)
        )

        if resolved_use_mappings and isinstance(mapping_snapshot, list) and mapping_snapshot:
            mappings = build_column_mappings_from_snapshot(mapping_snapshot)

            execute_import_with_mappings(
                db=db,
                org_id=org_id,
                user_id=import_record.created_by_user_id,
                import_id=import_record.id,
                file_content=import_record.file_content,
                column_mappings=mappings,
                unknown_column_behavior=resolved_unknown_behavior,
                backdate_created_at=bool(getattr(import_record, "backdate_created_at", False)),
                default_source=resolved_default_source,
                validation_mode=resolved_validation_mode,
            )
        else:
            execute_import(
                db=db,
                org_id=org_id,
                user_id=import_record.created_by_user_id,
                import_id=import_record.id,
                file_content=import_record.file_content,
                dedupe_action=dedupe_action,
                default_source=resolved_default_source,
                validation_mode=resolved_validation_mode,
            )

        import_record.file_content = None
        db.commit()
    except Exception as e:
        import_record.status = "failed"
        import_record.errors = import_record.errors or []
        import_record.errors.append({"message": str(e)})
        db.commit()
        raise


def run_import_inline(
    db: Session,
    org_id: UUID,
    import_id: UUID,
    *,
    dedupe_action: str = "skip",
) -> SurrogateImport:
    """Run an approved/failed import inline (no worker)."""
    import_record = get_import(db, org_id, import_id)
    if not import_record:
        raise ValueError("Import not found")

    if import_record.status in {"running", "processing"}:
        raise ValueError("Import is already running")
    if import_record.status == "cancelled":
        raise ValueError("Import was cancelled")
    if import_record.status not in {"approved", "failed"}:
        raise ValueError(f"Import is not approved for processing (current: {import_record.status})")

    run_import_execution(
        db=db,
        org_id=org_id,
        import_record=import_record,
        use_mappings=True,
        dedupe_action=dedupe_action,
        unknown_column_behavior=import_record.unknown_column_behavior,
    )
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


def cancel_import(
    db: Session,
    org_id: UUID,
    import_id: UUID,
) -> SurrogateImport:
    """Cancel an import and remove its stored file content."""
    import_record = get_import(db, org_id, import_id)
    if not import_record:
        raise ValueError("Import not found")

    if import_record.status in {"running", "processing"}:
        raise ValueError("Import is running and cannot be cancelled")

    import_record.status = "cancelled"
    import_record.file_content = None
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
    default_source: SurrogateSource | str | None = None,
) -> SurrogateImport:
    """Create an import job record with template reference."""
    file_hash = compute_file_hash(file_content)
    import_record = SurrogateImport(
        organization_id=org_id,
        created_by_user_id=user_id,
        filename=filename,
        file_content=file_content,
        file_hash=file_hash,
        default_source=default_source.value
        if isinstance(default_source, SurrogateSource)
        else default_source,
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
