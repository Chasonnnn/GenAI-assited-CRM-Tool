from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest
from click.testing import CliRunner

from ops_cli import bundle, cli, config
from ops_cli.cli import _apply_one, main
from ops_cli.client import APIError, Client, resolve_org


def make_template(path: Path, key: str = "welcome", draft: dict | None = None) -> Path:
    path.mkdir()
    (path / "template.json").write_text(
        json.dumps(
            {
                "version": 1,
                "type": "email",
                "key": key,
                "draft": draft or {"subject": "Hi", "body": "Hello"},
            }
        )
    )
    return path


def test_init_and_offline_validate(tmp_path: Path) -> None:
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        result = runner.invoke(main, ["templates", "init", "email", "welcome"])
        assert result.exit_code == 0
        result = runner.invoke(main, ["templates", "validate", "welcome"])
        assert result.exit_code == 0
        assert json.loads(result.output)["templates"][0]["valid"] is True


@pytest.mark.parametrize("existing", [False, True])
def test_set_env_rejects_ops_paths_without_changing_profiles(tmp_path, monkeypatch, existing):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = config.config_dir() / "config.json"
    if existing:
        config.set_environment("test", "https://api.example.test", "https://ops.example.test")
    before = path.read_bytes() if existing else None

    result = CliRunner().invoke(
        main,
        [
            "--json",
            "config",
            "set-env",
            "test",
            "--api-url",
            "https://new-api.example.test",
            "--ops-url",
            "https://ops.example.test/internal",
        ],
    )

    assert result.exit_code == 1
    assert json.loads(result.output) == {"error": "invalid Ops URL"}
    assert (path.read_bytes() if path.exists() else None) == before


@pytest.mark.parametrize("ops_url", ["https://ops.example.test", "https://ops.example.test/"])
def test_set_env_accepts_reloadable_ops_origins(tmp_path, monkeypatch, ops_url):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    result = CliRunner().invoke(
        main,
        [
            "config",
            "set-env",
            "test",
            "--api-url",
            "https://api.example.test/",
            "--ops-url",
            ops_url,
        ],
    )

    assert result.exit_code == 0
    assert config.environment("test") == {
        "api_url": "https://api.example.test",
        "ops_url": "https://ops.example.test",
    }


def test_path_escape_through_symlink_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "bundle"
    root.mkdir()
    outside = make_template(tmp_path / "outside")
    (root / "linked").symlink_to(outside, target_is_directory=True)
    (root / "bundle.json").write_text('{"version":1,"templates":["linked"]}')
    with pytest.raises(bundle.BundleError, match="escapes"):
        bundle.load(root)


def test_token_fallback_is_private_and_roundtrips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    # Force the optional backend to be unavailable regardless of the host.
    monkeypatch.setitem(__import__("sys").modules, "keyring", None)
    config.set_environment("dev", "https://api.example.test", "https://ops.example.test")
    config.store_token("dev", "very-secret")
    path = config.config_dir() / "tokens.json"
    assert config.token("dev") == "very-secret"
    assert os.stat(path).st_mode & 0o777 == 0o600
    config.set_environment("dev", "https://other.example.test", "https://ops.example.test")
    with pytest.raises(ValueError, match="not logged in"):
        config.token("dev")


def test_client_redacts_token_and_server_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["authorization"] == "Bearer very-secret"
        return httpx.Response(500, text="very-secret database exploded")

    client = Client("https://example.test", "very-secret", httpx.MockTransport(handler))
    with pytest.raises(APIError) as error:
        client.request("GET", "/platform/cli/whoami")
    assert "very-secret" not in str(error.value)
    assert "database" not in str(error.value)


def test_exact_org_resolution_paginates_and_ignores_partial() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        if offset == 0:
            return httpx.Response(
                200, json={"items": [{"id": "1", "slug": "acme-old", "name": "Old"}], "total": 2}
            )
        return httpx.Response(
            200, json={"items": [{"id": "2", "slug": "acme", "name": "Acme"}], "total": 2}
        )

    result = resolve_org(Client("https://example.test", "x", httpx.MockTransport(handler)), "acme")
    assert result["id"] == "2"


def test_canonical_file_roundtrip(tmp_path: Path) -> None:
    directory = make_template(tmp_path / "welcome", draft={"body": None, "subject": "Hi"})
    first = bundle.load_template(directory)
    rewritten = {"version": 1, "type": first.type, "key": first.key, "draft": first.draft}
    (directory / "template.json").write_text(json.dumps(rewritten, indent=2, sort_keys=True) + "\n")
    assert bundle.load_template(directory).draft == {"body": None, "subject": "Hi"}


def test_conflict_keeps_observed_base(tmp_path: Path) -> None:
    directory = make_template(tmp_path / "welcome")
    item = bundle.load_template(directory)
    bundle.update_state(directory, "https://dev.test", item, {"id": "id-1", "revision": 7})

    class ConflictClient:
        def request(self, method: str, path: str, **kwargs: object) -> dict:
            if method == "PUT":
                assert kwargs["json"]["expected_revision"] == 7  # type: ignore[index]
                raise APIError("server returned HTTP 409")
            return {"draft": {"subject": "remote"}}

    with pytest.raises(APIError):
        _apply_one(
            ConflictClient(),
            directory,
            item,
            "https://dev.test",
            {  # type: ignore[arg-type]
                "draft": item.draft,
                "mode": "draft",
                "audience": None,
            },
        )
    assert bundle.state_record(directory, "https://dev.test", item)["revision"] == 7


def test_lost_response_recovers_only_exact_state(tmp_path: Path) -> None:
    directory = make_template(tmp_path / "welcome")
    item = bundle.load_template(directory)

    class LostResponseClient:
        def request(self, method: str, path: str, **kwargs: object) -> dict:
            if method == "PUT":
                raise APIError("network request failed")
            return {
                "id": "id-1",
                "revision": 1,
                "draft": item.draft,
                "published": None,
                "audience": {"publish_all": False, "org_ids": []},
            }

    result = _apply_one(
        LostResponseClient(),
        directory,
        item,
        "https://dev.test",
        {  # type: ignore[arg-type]
            "draft": item.draft,
            "mode": "draft",
            "audience": None,
        },
    )
    assert result["recovered"] is True
    assert bundle.state_record(directory, "https://dev.test", item)["revision"] == 1


def test_client_accepts_empty_logout_response() -> None:
    transport = httpx.MockTransport(lambda request: httpx.Response(204))
    assert Client("https://example.test", "token", transport).request("POST", "/logout") is None


def test_login_start_does_not_send_an_empty_bearer_header() -> None:
    def handler(request):
        assert "authorization" not in request.headers
        return httpx.Response(200, json={"status": "pending"})

    assert Client("https://example.test", "", httpx.MockTransport(handler)).request(
        "POST", "/platform/cli/login/start"
    ) == {"status": "pending"}


def test_cli_batch_preflight_failure_and_resume(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "templates"
    root.mkdir()
    names = ("alpha", "bravo", "charlie")
    for name in names:
        make_template(root / name, name)
    (root / "bundle.json").write_text(json.dumps({"version": 1, "templates": list(names)}))
    calls: list[tuple[str, str]] = []
    fail_bravo = True

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal fail_bravo
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/validate"):
            return httpx.Response(200, json={"draft": json.loads(request.content)["draft"]})
        key = request.url.path.split("/")[-2 if request.method == "PUT" else -1]
        state_path = root / key / bundle.STATE
        if request.method == "GET":
            if not state_path.exists():
                return httpx.Response(404)
            revision = bundle.state(root / key)["origins"]["https://api.test"]["revision"]
            return httpx.Response(
                200,
                json={
                    "id": f"id-{key}",
                    "revision": revision,
                    "draft": {"subject": "Hi", "body": "Hello"},
                },
            )
        if key == "bravo" and fail_bravo:
            fail_bravo = False
            return httpx.Response(500)
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            json={"id": f"id-{key}", "revision": 1, "result": "created", "draft": payload["draft"]},
        )

    client = Client("https://api.test", "token", httpx.MockTransport(handler))
    monkeypatch.setattr(cli, "remote", lambda env: (client, {"api_url": "https://api.test"}))
    runner = CliRunner()
    first = runner.invoke(main, ["templates", "push", str(root), "--env", "test"])
    assert first.exit_code == 1
    result = json.loads(first.stdout)
    assert [item["status"] for item in result["templates"]] == [
        "created",
        "failed",
        "unattempted",
    ]
    first_put = next(index for index, call in enumerate(calls) if call[0] == "PUT")
    assert sum(path.endswith("/validate") for _, path in calls[:first_put]) == 3
    assert not any(path.endswith("/charlie/apply") for _, path in calls)

    calls.clear()
    second = runner.invoke(main, ["templates", "push", str(root), "--env", "test"])
    assert second.exit_code == 0
    statuses = [item["status"] for item in json.loads(second.stdout)["templates"]]
    assert statuses == ["created", "created", "created"]


def test_cli_paths_groups_and_json_error() -> None:
    runner = CliRunner()
    assert runner.invoke(main, ["config", "--help"]).exit_code == 0
    assert runner.invoke(main, ["templates", "--help"]).exit_code == 0
    assert runner.invoke(main, ["login", "--help"]).output.find("--token") == -1
    result = runner.invoke(main, ["--json", "templates", "show", "email", "../x", "--env", "x"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"].startswith("key must")


@pytest.mark.parametrize("no_browser", [False, True])
def test_browser_login_stores_session_without_printing_secrets(monkeypatch, no_browser):
    from unittest.mock import Mock

    grant = {
        "device_code": "private-device",
        "user_code": "ABCD-EFGH-JKLM",
        "expires_in": 600,
        "interval": 3,
    }
    responses = iter(
        [
            grant,
            {"status": "pending"},
            {"status": "approved", "token": "private-token"},
            {"email": "ops@example.test"},
        ]
    )
    client = Mock()
    client.request.side_effect = lambda *args, **kwargs: next(responses)
    monkeypatch.setattr(cli, "Client", Mock(return_value=client))
    monkeypatch.setattr(
        config,
        "environment",
        lambda env: {"api_url": "https://api.test", "ops_url": "https://ops.test"},
    )
    store, browser = Mock(), Mock()
    monkeypatch.setattr(config, "store_token", store)
    monkeypatch.setattr(cli.webbrowser, "open", browser)
    monkeypatch.setattr(cli.time, "sleep", lambda seconds: None)
    result = CliRunner().invoke(
        main, ["--json", "login", "--env", "staging"] + (["--no-browser"] if no_browser else [])
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"email": "ops@example.test"}
    assert "ABCD-EFGH-JKLM" in result.stderr
    assert "private-device" not in result.output and "private-token" not in result.output
    store.assert_called_once_with("staging", "private-token")
    assert browser.call_count == (0 if no_browser else 1)
    client.request.assert_any_call(
        "POST", "/platform/cli/login/exchange", json={"device_code": "private-device"}
    )


def test_expired_login_does_not_replace_existing_session(monkeypatch):
    from unittest.mock import Mock

    client = Mock()
    client.request.side_effect = [
        {"device_code": "device", "user_code": "code", "expires_in": 600, "interval": 3},
        {"status": "expired"},
    ]
    monkeypatch.setattr(cli, "Client", Mock(return_value=client))
    monkeypatch.setattr(
        config,
        "environment",
        lambda env: {"api_url": "https://api.test", "ops_url": "https://ops.test"},
    )
    store = Mock()
    monkeypatch.setattr(config, "store_token", store)
    result = CliRunner().invoke(main, ["login", "--env", "staging", "--no-browser"])
    assert result.exit_code == 1
    assert "Login expired" in result.output
    store.assert_not_called()
