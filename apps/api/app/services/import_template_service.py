"""Import template service for reusable CSV mappings."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import ImportTemplate


def list_templates(db: Session, org_id: UUID) -> list[ImportTemplate]:
    return (
        db.query(ImportTemplate)
        .filter(ImportTemplate.organization_id == org_id)
        .order_by(ImportTemplate.created_at.desc())
        .all()
    )


def get_template(db: Session, org_id: UUID, template_id: UUID) -> ImportTemplate | None:
    return (
        db.query(ImportTemplate)
        .filter(
            ImportTemplate.organization_id == org_id,
            ImportTemplate.id == template_id,
        )
        .first()
    )


def _clear_default(db: Session, org_id: UUID, exclude_id: UUID | None = None) -> None:
    query = db.query(ImportTemplate).filter(
        ImportTemplate.organization_id == org_id,
        ImportTemplate.is_default.is_(True),
    )
    if exclude_id:
        query = query.filter(ImportTemplate.id != exclude_id)
    query.update({ImportTemplate.is_default: False})


def create_template(
    db: Session,
    org_id: UUID,
    user_id: UUID,
    *,
    name: str,
    description: str | None,
    is_default: bool,
    encoding: str,
    delimiter: str,
    has_header: bool,
    column_mappings: list[dict] | None,
    transformations: dict | None,
    unknown_column_behavior: str,
) -> ImportTemplate:
    if is_default:
        _clear_default(db, org_id)

    template = ImportTemplate(
        organization_id=org_id,
        name=name,
        description=description,
        is_default=is_default,
        encoding=encoding,
        delimiter=delimiter,
        has_header=has_header,
        column_mappings=column_mappings,
        transformations=transformations,
        unknown_column_behavior=unknown_column_behavior,
        created_by_user_id=user_id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(
    db: Session,
    template: ImportTemplate,
    *,
    name: str | None = None,
    description: str | None = None,
    is_default: bool | None = None,
    encoding: str | None = None,
    delimiter: str | None = None,
    has_header: bool | None = None,
    column_mappings: list[dict] | None = None,
    transformations: dict | None = None,
    unknown_column_behavior: str | None = None,
) -> ImportTemplate:
    if is_default is True:
        _clear_default(db, template.organization_id, exclude_id=template.id)
        template.is_default = True
    elif is_default is False:
        template.is_default = False

    if name is not None:
        template.name = name
    if description is not None:
        template.description = description
    if encoding is not None:
        template.encoding = encoding
    if delimiter is not None:
        template.delimiter = delimiter
    if has_header is not None:
        template.has_header = has_header
    if column_mappings is not None:
        template.column_mappings = column_mappings
    if transformations is not None:
        template.transformations = transformations
    if unknown_column_behavior is not None:
        template.unknown_column_behavior = unknown_column_behavior

    db.commit()
    db.refresh(template)
    return template


def clone_template(
    db: Session,
    template: ImportTemplate,
    *,
    name: str,
    user_id: UUID,
) -> ImportTemplate:
    clone = ImportTemplate(
        organization_id=template.organization_id,
        name=name,
        description=template.description,
        is_default=False,
        encoding=template.encoding,
        delimiter=template.delimiter,
        has_header=template.has_header,
        column_mappings=template.column_mappings,
        transformations=template.transformations,
        unknown_column_behavior=template.unknown_column_behavior,
        created_by_user_id=user_id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


def delete_template(db: Session, template: ImportTemplate) -> None:
    db.delete(template)
    db.commit()


def increment_template_usage(db: Session, template_id: UUID) -> None:
    """Increment the usage count and update last_used_at."""
    from datetime import datetime, timezone

    db.query(ImportTemplate).filter(ImportTemplate.id == template_id).update(
        {
            "usage_count": ImportTemplate.usage_count + 1,
            "last_used_at": datetime.now(timezone.utc),
        }
    )
    db.commit()
