"""Canonical, atomic writes shared by the OPS studio and its HTTP CLI."""

from copy import deepcopy
from datetime import UTC, datetime
from typing import get_args
from uuid import UUID

from fastapi import Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Organization,
    PlatformEmailTemplate,
    PlatformEmailTemplateTarget,
    PlatformFormTemplate,
    PlatformFormTemplateHiddenOrg,
    PlatformFormTemplateTarget,
    WorkflowTemplate,
    WorkflowTemplateTarget,
)
from app.schemas.platform_templates import (
    PlatformEmailTemplateDraft,
    PlatformFormTemplateDraft,
    PlatformWorkflowTemplateDraft,
)
from app.services import email_service, platform_service

MODELS = {
    "email": PlatformEmailTemplate,
    "form": PlatformFormTemplate,
    "workflow": WorkflowTemplate,
}
TARGETS = {
    "email": PlatformEmailTemplateTarget,
    "form": PlatformFormTemplateTarget,
    "workflow": WorkflowTemplateTarget,
}
SCHEMAS = {
    "email": PlatformEmailTemplateDraft,
    "form": PlatformFormTemplateDraft,
    "workflow": PlatformWorkflowTemplateDraft,
}
FIELDS = {
    "email": ("name", "subject", "body", "from_email", "category"),
    "form": ("name", "description", "schema_json", "settings_json"),
    "workflow": (
        "name",
        "description",
        "icon",
        "category",
        "subject_type",
        "trigger_type",
        "trigger_config",
        "conditions",
        "condition_logic",
        "actions",
    ),
}


class TemplateConflict(ValueError):
    pass


class TemplateInputError(ValueError):
    """Safe, authored validation messages; never wrap provider or database errors."""


def template_query(db, kind):
    model = MODELS[kind]
    query = db.query(model)
    if kind == "workflow":
        query = query.filter(model.is_global.is_(True), model.organization_id.is_(None))
    return query


def find_template(db, kind, *, key=None, template_id=None, lock=False):
    if key is None and template_id is None:
        return None
    model = MODELS[kind]
    query = template_query(db, kind)
    query = (
        query.filter(model.id == template_id)
        if template_id
        else query.filter(model.external_key == key)
    )
    if lock:
        # Reload after taking the lock: the identity map may contain a pre-lock read.
        query = query.populate_existing().with_for_update()
    return query.first()


def content(template, kind, *, published=False):
    if published and not template.published_version:
        return None
    if kind == "workflow" and not published and template.draft_config is not None:
        return deepcopy(template.draft_config)
    prefix = "published_" if published and kind != "workflow" else ""
    return {field: deepcopy(getattr(template, prefix + field)) for field in FIELDS[kind]}


def audience_for(db, kind, template):
    target = TARGETS[kind]
    ids = db.query(target.organization_id).filter(target.template_id == template.id).all()
    return {
        "publish_all": template.is_published_globally,
        "org_ids": sorted(str(row[0]) for row in ids),
    }


def record(db, kind, template):
    hidden = []
    if kind == "form":
        hidden = [
            str(row[0])
            for row in db.query(PlatformFormTemplateHiddenOrg.organization_id)
            .filter(PlatformFormTemplateHiddenOrg.template_id == template.id)
            .all()
        ]
    return {
        "id": str(template.id),
        "type": kind,
        "key": template.external_key,
        "revision": template.current_version,
        "published_version": template.published_version,
        "status": template.status,
        "draft": content(template, kind),
        "published": content(template, kind, published=True),
        "audience": audience_for(db, kind, template),
        "published_at": template.published_at,
        "hidden_org_ids": sorted(hidden),
    }


def _reject_tenant_ids(value, path="draft"):
    if isinstance(value, dict):
        for key, item in value.items():
            _reject_tenant_ids(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_tenant_ids(item, f"{path}.{index}")
    elif isinstance(value, str):
        try:
            UUID(value)
        except ValueError:
            return
        raise TemplateInputError(f"{path}: tenant identifiers are not portable")


def validate_template(kind, draft, *, publishing=True, portable=True):
    canonical = (
        SCHEMAS[kind].model_validate(draft, extra="forbid").model_dump(mode="json", by_alias=True)
    )
    warnings, bindings = [], []
    if kind == "workflow":
        # Older studio drafts may contain editor row IDs, not tenant bindings.
        for item in canonical["actions"] + canonical["conditions"]:
            item.pop("clientId", None)
    if not canonical["name"].strip():
        raise TemplateInputError("draft.name: must not be blank")
    if kind == "email":
        from app.services import template_variable_catalog

        canonical["body"] = email_service.sanitize_template_html(canonical["body"])
        catalog = template_variable_catalog.list_platform_email_template_variables()
        used = template_variable_catalog.extract_template_variables(
            canonical["subject"] + canonical["body"]
        )
        unknown = used - {item.name for item in catalog}
        if unknown:
            raise TemplateInputError("draft.body: unsupported template variables")
        if canonical["body"] != draft.get("body"):
            warnings.append("HTML was sanitized; diff and publication use sanitized content")
    elif kind == "form" and publishing:
        from app.schemas.forms import FormFieldMappingsUpdate
        from app.services import form_service

        if canonical["schema_json"] is None:
            raise TemplateInputError("draft.schema_json: a form schema is required for publication")
        settings = canonical["settings_json"] or {}
        mappings = FormFieldMappingsUpdate.model_validate(
            {"mappings": settings.get("mappings", [])}
        )
        if settings.get("lead_kind") in {"egg_donor", "sperm_donor"}:
            form_service.validate_donor_intake_configuration(
                schema_json=canonical["schema_json"],
                mappings={item.surrogate_field: item.field_key for item in mappings.mappings},
                max_file_count=settings.get("max_file_count", form_service.DEFAULT_MAX_FILE_COUNT),
                allowed_mime_types=settings.get("allowed_mime_types"),
            )
    elif kind == "workflow" and publishing:
        from app.db.enums import WorkflowTriggerType
        from app.schemas import workflow as schemas
        from app.services import workflow_service

        try:
            trigger = WorkflowTriggerType(canonical["trigger_type"])
        except ValueError:
            raise TemplateInputError("draft.trigger_type: unsupported trigger") from None
        subject_type = canonical.get("subject_type")
        if subject_type is None:
            from app.services import template_service

            if trigger.value in template_service.DONOR_ONLY_TRIGGER_TYPES:
                raise TemplateInputError(
                    "draft.subject_type: donor triggers require an explicit "
                    "egg_donor or sperm_donor subject"
                )
        else:
            try:
                workflow_service._validate_subject_trigger(subject_type, trigger)
            except ValueError as exc:
                raise TemplateInputError(f"draft.subject_type: {exc}") from None
        if canonical["condition_logic"] not in {"AND", "OR"}:
            raise TemplateInputError("draft.condition_logic: expected AND or OR")
        for condition in canonical["conditions"]:
            schemas.Condition.model_validate(condition)
        if portable:
            _reject_tenant_ids(
                {key: canonical[key] for key in ("trigger_config", "conditions", "actions")}
            )
        config = canonical["trigger_config"]
        if trigger.value in {
            "form_started",
            "form_submitted",
            "intake_lead_created",
        } and config.get("form_name"):
            bindings.append(
                "trigger_config.form_name: select a matching published form in the organization"
            )
        if trigger.value == "form_started" and not config.get("form_id"):
            bindings.append(
                "trigger_config.form_id: select a published form when adopting the template"
            )
        else:
            workflow_service._validate_trigger_config(trigger, config)
        models = {
            get_args(model.model_fields["action_type"].annotation)[0]: model
            for model in get_args(schemas.ActionConfig)
        }
        if not canonical["actions"]:
            raise TemplateInputError("draft.actions: at least one action is required")
        for index, action in enumerate(canonical["actions"]):
            action_type = action.get("action_type")
            model = models.get(action_type)
            if model is None:
                raise TemplateInputError(f"draft.actions.{index}.action_type: unsupported action")
            if action_type == "send_email" and not action.get("template_id"):

                class LibraryEmailAction(schemas.SendEmailActionConfig):
                    template_id: None = None

                LibraryEmailAction.model_validate(action)
                bindings.append(
                    f"actions.{index}.template_id: select an organization email template"
                )
            else:
                model.model_validate(action)
    return {"draft": canonical, "warnings": warnings, "bindings": bindings}


def apply_template(db: Session, kind: str, **kwargs):
    """Own the transaction, including rollback without discarding a caller's outer transaction."""
    with db.begin_nested():
        template, result = _apply_template(db, kind, **kwargs)
    db.commit()
    db.refresh(template)
    return template, result


def _apply_template(
    db: Session,
    kind: str,
    *,
    actor_id: UUID,
    draft: dict | None = None,
    key: str | None = None,
    template_id: UUID | None = None,
    bind_id: UUID | None = None,
    expected_revision: int | None = None,
    mode: str = "draft",
    audience: dict | None = None,
    keep_audience: bool = False,
    replace_audience: bool = False,
    patch: bool = False,
    portable: bool = True,
    request: Request | None = None,
):
    """Apply one desired state. Row lock, content, audience and audit share one commit."""
    try:
        template = find_template(db, kind, key=key, template_id=bind_id or template_id, lock=True)
        if (bind_id or template_id) and template is None:
            raise LookupError("Template not found")
        if bind_id and template.external_key not in (None, key):
            raise TemplateConflict("Template already has another key")
        is_new = template is None
        if is_new and expected_revision is not None:
            raise TemplateConflict("Template no longer exists")
        old_draft = content(template, kind) if template else {}
        desired = old_draft if draft is None else ({**old_draft, **draft} if patch else draft)
        checked = validate_template(
            kind, desired, publishing=mode == "publish" or portable, portable=portable
        )
        canonical = checked["draft"]
        old_audience = (
            audience_for(db, kind, template) if template else {"publish_all": False, "org_ids": []}
        )
        target_audience = old_audience
        if mode == "publish":
            if keep_audience:
                if audience is not None or not template or not template.published_version:
                    raise TemplateInputError(
                        "keep_audience requires an existing publication and no audience"
                    )
            else:
                if audience is None:
                    raise TemplateInputError("An explicit publication audience is required")
                ids = sorted({str(UUID(str(value))) for value in audience.get("org_ids", [])})
                global_ = audience.get("publish_all", False)
                if (global_ and ids) or (not global_ and not ids):
                    raise TemplateInputError(
                        "Choose all organizations or a nonempty organization list"
                    )
                if ids:
                    count = (
                        db.query(Organization)
                        .filter(
                            Organization.id.in_([UUID(value) for value in ids]),
                            Organization.deleted_at.is_(None),
                        )
                        .count()
                    )
                    if count != len(ids):
                        raise TemplateInputError("Audience contains an unavailable organization")
                target_audience = {"publish_all": global_, "org_ids": ids}
            if (
                template
                and template.published_version
                and target_audience != old_audience
                and not replace_audience
            ):
                raise TemplateInputError("Changing the audience requires replace_audience")
        elif audience is not None:
            raise TemplateInputError("Draft updates cannot change the publication audience")

        same = (
            template is not None
            and canonical == old_draft
            and (key is None or key == template.external_key)
        )
        if mode == "publish":
            same = (
                same
                and canonical == content(template, kind, published=True)
                and target_audience == old_audience
            )
        if same:
            return template, "unchanged"
        if template and (
            expected_revision is None or expected_revision != template.current_version
        ):
            raise TemplateConflict("Template revision mismatch; pull and review the remote changes")

        if is_new:
            values = dict(canonical)
            if kind == "workflow":
                values.update(is_global=True, organization_id=None, created_by_user_id=actor_id)
            template = MODELS[kind](
                **values,
                external_key=key,
                current_version=1,
                published_version=0,
                status="draft",
                is_published_globally=False,
            )
            db.add(template)
        else:
            template.current_version += 1
            if key is not None:
                template.external_key = key
        if kind == "workflow":
            template.draft_config = deepcopy(canonical)
        else:
            for field, value in canonical.items():
                setattr(template, field, deepcopy(value))
        template.status = "draft"
        result = "created" if is_new else "updated"
        if mode == "publish":
            for field, value in canonical.items():
                setattr(
                    template, field if kind == "workflow" else "published_" + field, deepcopy(value)
                )
            if kind == "workflow":
                template.draft_config = None
            template.published_version += 1
            template.published_at = datetime.now(UTC)
            template.status = "published"
            template.is_published_globally = target_audience["publish_all"]
            result = "published"
        template.updated_at = datetime.now(UTC)
        db.flush()
        if mode == "publish" and target_audience != old_audience:
            target = TARGETS[kind]
            db.query(target).filter(target.template_id == template.id).delete()
            for org_id in target_audience["org_ids"]:
                db.add(target(template_id=template.id, organization_id=UUID(org_id)))
        platform_service.log_admin_action(
            db,
            actor_id,
            f"platform_template.{kind}.{'publish' if mode == 'publish' else 'create' if is_new else 'update'}",
            metadata={
                "template_id": str(template.id),
                "revision": template.current_version,
                "publish_all": target_audience["publish_all"],
                "org_ids": target_audience["org_ids"],
            },
            request=request,
        )
        db.flush()
        return template, result
    except IntegrityError as exc:
        raise TemplateConflict(
            "Template key conflicts with an existing template; reread before retrying"
        ) from exc
