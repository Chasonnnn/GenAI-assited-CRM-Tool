import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.db.enums import IntakeLeadStatus
from app.db.models import FormSubmission
from app.services import form_intake_service


def _compiled_sql(statement) -> str:
    return " ".join(
        str(statement.compile(dialect=postgresql.dialect())).lower().split()
    )


def test_published_version_count_uses_direct_aggregate(monkeypatch):
    db = MagicMock()
    db.scalar.return_value = 2
    monkeypatch.setattr(
        form_intake_service.form_submission_service,
        "_snapshot_mappings",
        lambda *_args, **_kwargs: {},
    )
    monkeypatch.setattr(form_intake_service, "_snapshot_field_policy", lambda _form: {})
    form = SimpleNamespace(
        id=uuid.uuid4(),
        published_schema_json={},
        schema_json={},
    )
    link = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        tracking_mode="none",
        allowed_embed_origins=[],
        embed_enabled=False,
        consent_text=None,
        thank_you_config={},
        embed_theme_json={},
    )

    version = form_intake_service.create_published_intake_version(
        db,
        form=form,
        link=link,
        user_id=None,
    )

    statement = db.scalar.call_args.args[0]
    sql = _compiled_sql(statement)
    assert "select count(published_intake_versions.id)" in sql
    assert "from (select" not in sql
    assert version.version == 3


def test_promoted_lead_count_uses_direct_aggregate():
    surrogate = SimpleNamespace(id=uuid.uuid4())
    lead = SimpleNamespace(
        id=uuid.uuid4(),
        organization_id=uuid.uuid4(),
        status=IntakeLeadStatus.PROMOTED.value,
        promoted_surrogate_id=surrogate.id,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = surrogate
    db.scalar.return_value = 4

    returned_surrogate, linked_count = form_intake_service.promote_intake_lead(
        db,
        lead=lead,
        user_id=None,
    )

    statement = db.scalar.call_args.args[0]
    sql = _compiled_sql(statement)
    assert "select count(form_submissions.id)" in sql
    assert "from (select" not in sql
    assert returned_surrogate is surrogate
    assert linked_count == 4
    assert statement.whereclause.compare(
        (FormSubmission.intake_lead_id == lead.id)
        & (FormSubmission.surrogate_id == surrogate.id)
    )
