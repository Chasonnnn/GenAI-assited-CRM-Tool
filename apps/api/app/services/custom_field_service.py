"""Custom field service for org-scoped field definitions."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import CustomField


def list_custom_fields(db: Session, org_id: UUID) -> list[CustomField]:
    return (
        db.query(CustomField)
        .filter(CustomField.organization_id == org_id)
        .order_by(CustomField.created_at.desc())
        .all()
    )


def get_custom_field(db: Session, org_id: UUID, field_id: UUID) -> CustomField | None:
    return (
        db.query(CustomField)
        .filter(
            CustomField.organization_id == org_id,
            CustomField.id == field_id,
        )
        .first()
    )


def create_custom_field(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    *,
    key: str,
    label: str,
    field_type: str,
    options: list[str] | None,
) -> CustomField:
    existing = (
        db.query(CustomField)
        .filter(CustomField.organization_id == org_id, CustomField.key == key)
        .first()
    )
    if existing:
        raise ValueError("Custom field key already exists")

    field = CustomField(
        organization_id=org_id,
        key=key,
        label=label,
        field_type=field_type,
        options=options,
        created_by_user_id=user_id,
        is_active=True,
    )
    db.add(field)
    db.commit()
    db.refresh(field)
    return field


def update_custom_field(
    db: Session,
    field: CustomField,
    *,
    label: str | None = None,
    options: list[str] | None = None,
    is_active: bool | None = None,
) -> CustomField:
    if label is not None:
        field.label = label
    if options is not None:
        field.options = options
    if is_active is not None:
        field.is_active = is_active
    db.commit()
    db.refresh(field)
    return field


def delete_custom_field(db: Session, field: CustomField) -> None:
    db.delete(field)
    db.commit()


# =============================================================================
# Custom Field Values (for imports)
# =============================================================================


def get_custom_field_by_key(db: Session, org_id: UUID, key: str) -> CustomField | None:
    """Get a custom field by its key."""
    return (
        db.query(CustomField)
        .filter(
            CustomField.organization_id == org_id,
            CustomField.key == key,
        )
        .first()
    )


def set_custom_field_value(
    db: Session,
    surrogate_id: UUID,
    custom_field_id: UUID,
    value: object,
) -> None:
    """Set a custom field value for a surrogate."""
    from app.db.models import CustomFieldValue

    existing = (
        db.query(CustomFieldValue)
        .filter(
            CustomFieldValue.surrogate_id == surrogate_id,
            CustomFieldValue.custom_field_id == custom_field_id,
        )
        .first()
    )

    if existing:
        existing.value_json = {"value": value}
    else:
        cfv = CustomFieldValue(
            surrogate_id=surrogate_id,
            custom_field_id=custom_field_id,
            value_json={"value": value},
        )
        db.add(cfv)


def set_bulk_custom_values(
    db: Session,
    org_id: UUID,
    surrogate_id: UUID,
    values: dict[str, object],
) -> int:
    """
    Set multiple custom field values at once.

    Args:
        db: Database session
        org_id: Organization ID (for field lookup)
        surrogate_id: Surrogate ID
        values: Dict of field_key -> value

    Returns:
        Number of values set successfully
    """
    count = 0
    for key, value in values.items():
        field = get_custom_field_by_key(db, org_id, key)
        if field:
            set_custom_field_value(db, surrogate_id, field.id, value)
            count += 1
    db.commit()
    return count
