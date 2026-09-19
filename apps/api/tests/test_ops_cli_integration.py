"""Exercise the installed CLI contract against FastAPI and real disposable PostgreSQL."""

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.db.models import AdminActionLog, AutomationWorkflow, EmailTemplate, Form, Job
from app.main import app
from app.services import ops_cli_service
from app.services import platform_template_write_service as writes


@pytest.fixture
def cli_api(db, test_user, monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "ops-cli" / "src"))
    from ops_cli import cli
    from ops_cli.client import Client

    test_user.is_platform_admin = True
    db.commit()
    _, token = ops_cli_service.mint_token(db, test_user)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = lambda: db
    api = TestClient(app, base_url="https://test")

    def handle(request):
        response = api.request(
            request.method, str(request.url), headers=dict(request.headers), content=request.content
        )
        return httpx.Response(
            response.status_code, headers=response.headers, content=response.content
        )

    client = Client("https://test", token, transport=httpx.MockTransport(handle))
    monkeypatch.setattr(
        cli, "remote", lambda env: (client, {"api_url": "https://test", "ops_url": "https://test"})
    )
    monkeypatch.chdir(tmp_path)
    yield CliRunner(), cli.main, api, {"Authorization": f"Bearer {token}"}
    api.close()
    if previous is None:
        app.dependency_overrides.pop(get_db, None)
    else:
        app.dependency_overrides[get_db] = previous


def test_bundle_publish_roundtrip_and_no_execution(cli_api, db, test_user):
    runner, command, api, headers = cli_api
    before = {
        model: db.query(model).count() for model in (AutomationWorkflow, EmailTemplate, Form, Job)
    }
    for kind in ("email", "form", "workflow"):
        result = runner.invoke(command, ["templates", "init", kind, f"sample-{kind}"])
        assert result.exit_code == 0, result.output
    Path("bundle.json").write_text(
        json.dumps({"version": 1, "templates": ["sample-email", "sample-form", "sample-workflow"]})
    )
    for expected in ("published", "unchanged"):
        result = runner.invoke(
            command, ["templates", "publish", ".", "--env", "test", "--all-orgs"]
        )
        assert result.exit_code == 0, result.output
        assert {row["status"] for row in json.loads(result.output)["templates"]} == {expected}
    for kind in ("email", "form", "workflow"):
        result = runner.invoke(
            command,
            ["templates", "pull", kind, f"sample-{kind}", "--env", "test", "--output", "pulled"],
        )
        assert result.exit_code == 0, result.output
        result = runner.invoke(
            command, ["templates", "diff", f"pulled/sample-{kind}", "--env", "test", "--published"]
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)["templates"][0]["different"] is False
    assert all(db.query(model).count() == count for model, count in before.items())
    assert (
        db.query(AdminActionLog)
        .filter(
            AdminActionLog.actor_user_id == test_user.id,
            AdminActionLog.action.like("platform_template.%.publish"),
        )
        .count()
        == 3
    )
    response = api.post(
        "/platform/cli/templates/email/preview",
        headers=headers,
        json={
            "draft": {
                "name": "Preview",
                "subject": "Hello {{first_name}}",
                "body": "<p>{{first_name}}</p>",
            },
            "variables": {"first_name": "<script>alert(1)</script>"},
        },
    )
    assert response.status_code == 200
    assert "<script>" not in response.json()["html"]
    assert all(db.query(model).count() == count for model, count in before.items())


def test_cli_cannot_access_tenant_workflows_or_send(cli_api, db, test_org, test_user):
    _, _, api, headers = cli_api
    from app.db.models import WorkflowTemplate

    tenant = WorkflowTemplate(
        name="Private",
        organization_id=test_org.id,
        is_global=False,
        trigger_type="surrogate_created",
        actions=[],
    )
    db.add(tenant)
    db.commit()
    assert (
        api.get(f"/platform/cli/templates/workflow/by-id/{tenant.id}", headers=headers).status_code
        == 404
    )
    payload = {
        "draft": {"name": "Replace", "trigger_type": "surrogate_created"},
        "bind_id": str(tenant.id),
        "expected_revision": 1,
    }
    assert (
        api.put(
            "/platform/cli/templates/workflow/private/apply", headers=headers, json=payload
        ).status_code
        == 404
    )
    for path in (f"/platform/templates/email/{uuid4()}/test", "/platform/cli/login/approve"):
        assert api.post(path, headers=headers, json={}).status_code in (401, 403)
    assert api.get("/platform/orgs", headers=headers).status_code == 401


def test_bad_batch_has_no_writes_and_donor_publish_rolls_back(cli_api, db, test_user):
    runner, command, api, headers = cli_api
    runner.invoke(command, ["templates", "init", "email", "valid"])
    runner.invoke(command, ["templates", "init", "workflow", "invalid"])
    document = json.loads(Path("invalid/template.json").read_text())
    document["draft"]["actions"] = [{"action_type": "not_an_action"}]
    Path("invalid/template.json").write_text(json.dumps(document))
    Path("bundle.json").write_text(json.dumps({"version": 1, "templates": ["valid", "invalid"]}))
    result = runner.invoke(command, ["templates", "publish", ".", "--env", "test", "--all-orgs"])
    assert result.exit_code != 0
    assert writes.find_template(db, "email", key="valid") is None
    draft = {"name": "Donor", "schema_json": {"pages": [{"title": "About", "fields": []}]}}
    template, _ = writes.apply_template(db, "form", key="donor", actor_id=test_user.id, draft=draft)
    before = writes.record(db, "form", template)
    response = api.put(
        "/platform/cli/templates/form/donor/apply",
        headers=headers,
        json={
            "draft": {
                **draft,
                "name": "Must not persist",
                "settings_json": {"lead_kind": "egg_donor"},
            },
            "mode": "publish",
            "expected_revision": template.current_version,
            "audience": {"publish_all": True, "org_ids": []},
        },
    )
    assert response.status_code == 422
    db.refresh(template)
    assert writes.record(db, "form", template) == before
