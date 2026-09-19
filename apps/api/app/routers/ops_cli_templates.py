"""Explicitly scoped library-template API for the operations CLI."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.ops_cli_auth import OpsCliContext, require_ops_cli
from app.db.models import Organization
from app.services import email_service
from app.services import platform_template_write_service as writes

router = APIRouter(prefix="/platform/cli", tags=["platform-cli"])
Kind = Literal["email", "form", "workflow"]
Key = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]
Context = Annotated[OpsCliContext, Depends(require_ops_cli)]
Database = Annotated[Session, Depends(get_db)]


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft: dict


class Audience(BaseModel):
    model_config = ConfigDict(extra="forbid")
    publish_all: bool = False
    org_ids: list[UUID] = Field(default_factory=list, max_length=1000)


class ApplyRequest(DraftRequest):
    expected_revision: int | None = Field(default=None, ge=1)
    mode: Literal["draft", "publish"] = "draft"
    audience: Audience | None = None
    keep_audience: bool = False
    replace_audience: bool = False
    bind_id: UUID | None = None


class PreviewRequest(DraftRequest):
    variables: dict[str, str] = Field(default_factory=dict)


def template_error(exc):
    if isinstance(exc, writes.TemplateConflict):
        return HTTPException(409, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(404, detail="Template not found")
    if isinstance(exc, writes.TemplateInputError):
        path, separator, message = str(exc).partition(": ")
        return HTTPException(
            422,
            detail=[
                {
                    "loc": path.split(".") if separator else ["audience"],
                    "type": "template_validation",
                    "msg": message if separator else str(exc),
                }
            ],
        )
    if isinstance(exc, ValidationError):
        return HTTPException(
            422,
            detail=[
                {"loc": item["loc"], "type": item["type"]}
                for item in exc.errors(include_input=False)
            ],
        )
    # Domain messages may contain tenant configuration values. Do not echo them.
    return HTTPException(
        422,
        detail="Invalid template or audience; validate the template and review publication flags",
    )


@router.get("/orgs")
def organizations(
    context: Context,
    db: Database,
    search: str = "",
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = db.query(Organization).filter(Organization.deleted_at.is_(None))
    if search:
        filters = [Organization.slug.ilike(f"%{search}%"), Organization.name.ilike(f"%{search}%")]
        try:
            filters.append(Organization.id == UUID(search))
        except ValueError:
            pass
        query = query.filter(or_(*filters))
    return {
        "items": [
            {"id": row.id, "name": row.name, "slug": row.slug}
            for row in query.order_by(Organization.slug, Organization.id)
            .offset(offset)
            .limit(limit)
        ],
        "total": query.count(),
    }


@router.get("/templates/{kind}")
def list_templates(kind: Kind, context: Context, db: Database):
    return [writes.record(db, kind, row) for row in writes.template_query(db, kind).all()]


@router.post("/templates/{kind}/validate")
def validate(kind: Kind, body: DraftRequest, context: Context):
    try:
        return writes.validate_template(kind, body.draft)
    except ValueError as exc:
        raise template_error(exc) from None


@router.post("/templates/email/preview")
def preview_email(body: PreviewRequest, context: Context):
    try:
        checked = writes.validate_template("email", body.draft)
    except ValueError as exc:
        raise template_error(exc) from None
    draft = checked["draft"]
    missing = email_service.find_unresolved_template_variables(
        [draft["subject"], draft["body"]], body.variables
    )
    subject, html = email_service.render_template(draft["subject"], draft["body"], body.variables)
    # An artifact, never a public form or a send job. Block active content and remote tracking.
    html = (
        '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" '
        "content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'\">"
        + html
    )
    return {
        "subject": subject,
        "html": html,
        "warnings": checked["warnings"]
        + (["Some sample variables are missing"] if missing else []),
    }


@router.get("/templates/{kind}/by-id/{template_id}")
def get_by_id(kind: Kind, template_id: UUID, context: Context, db: Database):
    template = writes.find_template(db, kind, template_id=template_id)
    if template is None:
        raise HTTPException(404, detail="Template not found")
    return writes.record(db, kind, template)


@router.get("/templates/{kind}/{key}")
def get_template(kind: Kind, key: Key, context: Context, db: Database):
    template = writes.find_template(db, kind, key=key)
    if template is None:
        raise HTTPException(404, detail="Template not found")
    return writes.record(db, kind, template)


@router.put("/templates/{kind}/{key}/apply")
def apply(
    kind: Kind, key: Key, body: ApplyRequest, request: Request, context: Context, db: Database
):
    try:
        template, result = writes.apply_template(
            db,
            kind,
            key=key,
            actor_id=context.user_id,
            request=request,
            **body.model_dump(mode="python", exclude={"audience"}),
            audience=body.audience.model_dump(mode="json") if body.audience else None,
        )
    except (ValueError, LookupError) as exc:
        raise template_error(exc) from None
    return {**writes.record(db, kind, template), "result": result}
