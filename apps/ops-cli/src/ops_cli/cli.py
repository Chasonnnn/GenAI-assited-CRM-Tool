from __future__ import annotations

import json
import time
import webbrowser
from pathlib import Path

import click

from . import bundle, config
from .client import APIError, Client, resolve_org


class Context:
    json = False


def emit(value: object, *, json_output: bool | None = None) -> None:
    if json_output or Context.json or isinstance(value, (dict, list)):
        click.echo(json.dumps(value, indent=None if json_output else 2, sort_keys=True))
    else:
        click.echo(value)


def fail(exc: Exception) -> None:
    if Context.json:
        click.echo(json.dumps({"error": str(exc)}, sort_keys=True))
        raise click.exceptions.Exit(1)
    raise click.ClickException(str(exc)) from None


def remote(env: str) -> tuple[Client, dict]:
    profile = config.environment(env)
    return Client(profile["api_url"], config.token(env)), profile


def template_path(kind: str, key: str = "") -> str:
    return f"/platform/cli/templates/{kind}" + (f"/{key}" if key else "")


def require_key(key: str) -> None:
    if not bundle.KEY.fullmatch(key):
        raise ValueError("key must be lowercase letters, digits and hyphens (maximum 100)")


@click.group()
@click.option("--json", "json_output", is_flag=True, help="Emit stable JSON on stdout.")
@click.pass_context
def main(ctx: click.Context, json_output: bool) -> None:
    """Manage version-controlled operations templates."""
    ctx.obj = Context()
    Context.json = json_output


@main.group("config")
def config_cmd() -> None:
    """Manage CLI configuration."""


@config_cmd.command("set-env")
@click.argument("name")
@click.option("--api-url", required=True)
@click.option("--ops-url", required=True)
def set_env(name: str, api_url: str, ops_url: str) -> None:
    try:
        config.set_environment(name, api_url, ops_url)
        emit({"environment": name, "configured": True})
    except ValueError as exc:
        fail(exc)


@main.command()
@click.option("--env", required=True)
@click.option("--no-browser", is_flag=True, help="Print the login URL without opening a browser.")
def login(env: str, no_browser: bool) -> None:
    """Sign in through the normal OPS browser login and MFA."""
    try:
        profile = config.environment(env)
        client = Client(profile["api_url"], "")
        grant = client.request("POST", "/platform/cli/login/start")
        url = profile["ops_url"].rstrip("/") + "/ops/cli"
        click.echo(f"Open {url} and enter code {grant['user_code']}", err=True)
        click.echo("Sign in with your OPS account and approve only this terminal's code.", err=True)
        deadline = time.monotonic() + min(grant["expires_in"], 600)
        if not no_browser:
            try:
                webbrowser.open(url)
            except webbrowser.Error:
                pass  # The printed URL also works from another browser.
        while time.monotonic() < deadline:
            result = client.request(
                "POST", "/platform/cli/login/exchange", json={"device_code": grant["device_code"]}
            )
            if result["status"] == "approved":
                token_value = result["token"]
                identity = Client(profile["api_url"], token_value).request(
                    "GET", "/platform/cli/whoami"
                )
                config.store_token(env, token_value)
                emit(identity)
                return
            if result["status"] != "pending":
                break
            time.sleep(max(3, grant["interval"]))
        raise ValueError("Login expired. Run ops login again.")
    except (ValueError, APIError) as exc:
        fail(exc)


@main.command()
@click.option("--env", required=True)
def whoami(env: str) -> None:
    try:
        client, _ = remote(env)
        emit(client.request("GET", "/platform/cli/whoami"))
    except (ValueError, APIError) as exc:
        fail(exc)


@main.command()
@click.option("--env", required=True)
def logout(env: str) -> None:
    """Revoke the token remotely, then remove it locally."""
    try:
        client, _ = remote(env)
        client.request("POST", "/platform/cli/logout")
        config.delete_token(env)
        emit({"environment": env, "logged_out": True})
    except (ValueError, APIError) as exc:
        fail(exc)


EXAMPLES = {
    "email": (
        {"name": "Welcome", "subject": "Welcome, {{first_name}}"},
        "<p>Hello {{first_name}},</p>\n",
    ),
    "form": (
        {
            "name": "Intake form",
            "schema_json": {"pages": [{"title": "About you", "fields": []}]},
        },
        None,
    ),
    "workflow": (
        {
            "name": "Follow-up",
            "trigger_type": "surrogate_created",
            "actions": [{"action_type": "add_note", "content": "Review submission"}],
        },
        None,
    ),
}


@main.group("templates")
def templates() -> None:
    """Manage version-controlled templates."""


@templates.command("init")
@click.argument("kind", type=click.Choice(sorted(bundle.TYPES)))
@click.argument("name")
def init_template(kind: str, name: str) -> None:
    if not bundle.KEY.fullmatch(name):
        fail(ValueError("NAME must be a lowercase stable slug"))
    directory = Path(name)
    if directory.exists():
        fail(ValueError(f"{directory} already exists"))
    draft, body = EXAMPLES[kind]
    directory.mkdir()
    envelope = {"version": 1, "type": kind, "key": name, "draft": draft}
    if body is not None:
        envelope["body_file"] = "body.html"
        (directory / "body.html").write_text(body)
        (directory / "sample-data.json").write_text('{\n  "first_name": "Alex"\n}\n')
    (directory / "template.json").write_text(json.dumps(envelope, indent=2) + "\n")
    emit({"created": str(directory), "type": kind, "key": name})


@templates.command("validate")
@click.argument("path", type=click.Path(path_type=Path, exists=True), default=".")
@click.option("--env")
def validate(path: Path, env: str | None) -> None:
    try:
        _, templates = bundle.load(path)
        results = []
        client = remote(env)[0] if env else None
        for item in templates:
            result = {
                "type": item.type,
                "key": item.key,
                "valid": True,
                "warnings": [],
                "bindings": [],
            }
            if client:
                checked = client.request(
                    "POST", template_path(item.type, "validate"), json={"draft": item.draft}
                )
                result.update({key: checked[key] for key in ("warnings", "bindings")})
            results.append(result)
        emit({"templates": results})
    except (ValueError, APIError) as exc:
        fail(exc)


def _get(client: Client, kind: str, key: str) -> dict:
    return client.request("GET", template_path(kind, key))


@templates.command("list")
@click.argument("kind", type=click.Choice(sorted(bundle.TYPES)))
@click.option("--env", required=True)
def list_templates(kind: str, env: str) -> None:
    try:
        emit(remote(env)[0].request("GET", template_path(kind)))
    except (ValueError, APIError) as exc:
        fail(exc)


@templates.command()
@click.argument("kind", type=click.Choice(sorted(bundle.TYPES)))
@click.argument("key")
@click.option("--env", required=True)
def show(kind: str, key: str, env: str) -> None:
    try:
        require_key(key)
        emit(_get(remote(env)[0], kind, key))
    except (ValueError, APIError) as exc:
        fail(exc)


@templates.command()
@click.argument("kind", type=click.Choice(sorted(bundle.TYPES)))
@click.argument("key")
@click.option("--env", required=True)
@click.option("--output", type=click.Path(path_type=Path), default=".")
@click.option("--force", is_flag=True)
def pull(kind: str, key: str, env: str, output: Path, force: bool) -> None:
    try:
        require_key(key)
        client, profile = remote(env)
        record = _get(client, kind, key)
        directory = output / key
        if directory.exists() and any(directory.iterdir()) and not force:
            raise ValueError(f"{directory} is not empty; use --force")
        directory.mkdir(parents=True, exist_ok=True)
        envelope = {"version": 1, "type": kind, "key": key, "draft": record["draft"]}
        (directory / "template.json").write_text(
            json.dumps(envelope, indent=2, sort_keys=True) + "\n"
        )
        bundle.update_state(directory, profile["api_url"], bundle.load_template(directory), record)
        emit({"pulled": str(directory), "revision": record["revision"]})
    except (ValueError, APIError) as exc:
        fail(exc)


@templates.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True), default=".")
@click.option("--env", required=True)
@click.option("--published", is_flag=True)
def diff(path: Path, env: str, published: bool) -> None:
    try:
        _, templates = bundle.load(path)
        client, _ = remote(env)
        values = []
        for item in templates:
            canonical = client.request(
                "POST", template_path(item.type, "validate"), json={"draft": item.draft}
            )["draft"]
            record = _get(client, item.type, item.key)
            side = record.get("published") if published else record.get("draft")
            values.append(
                {
                    "type": item.type,
                    "key": item.key,
                    "different": side != canonical,
                    "local": canonical,
                    "remote": side,
                }
            )
        emit({"templates": values})
    except (ValueError, APIError) as exc:
        fail(exc)


def _apply_one(
    client: Client, root: Path, item: bundle.Template, origin: str, payload: dict
) -> dict:
    base = bundle.state_record(root, origin, item)
    payload["expected_revision"] = base["revision"] if base else None
    try:
        record = client.request("PUT", template_path(item.type, f"{item.key}/apply"), json=payload)
    except APIError as original:
        if not original.recoverable:
            raise
        # A lost response is recoverable only by exact, whole desired-state equality.
        try:
            current = _get(client, item.type, item.key)
        except APIError:
            raise original
        audience = payload.get("audience")
        desired = current.get("draft") == payload["draft"]
        if payload["mode"] == "publish":
            desired = desired and current.get("published") == payload["draft"]
        if audience is not None:
            desired = desired and current.get("audience") == audience
        if not desired:
            raise
        record = {**current, "result": "unchanged", "recovered": True}
    bundle.update_state(root, origin, item, record)
    return record


def _write(
    path: Path,
    env: str,
    mode: str,
    orgs: tuple[str, ...],
    all_orgs: bool,
    keep_audience: bool,
    replace_audience: bool,
) -> None:
    try:
        root, templates = bundle.load(path)
        client, profile = remote(env)
        canonical: dict[tuple[str, str], dict] = {}
        for item in templates:  # Batch validation is deliberately completed before any write.
            canonical[(item.type, item.key)] = client.request(
                "POST", template_path(item.type, "validate"), json={"draft": item.draft}
            )["draft"]
        audience = None
        if all_orgs:
            audience = {"publish_all": True, "org_ids": []}
        elif orgs:
            audience = {
                "publish_all": False,
                "org_ids": sorted({resolve_org(client, x)["id"] for x in orgs}),
            }
        snapshots: dict[tuple[str, str], dict | None] = {}
        for item in templates:
            base = bundle.state_record(root, profile["api_url"], item)
            try:
                current = _get(client, item.type, item.key)
            except APIError as exc:
                if exc.status_code != 404:
                    raise
                current = None
            if current is not None and base is None:
                if current.get("draft") != canonical[(item.type, item.key)]:
                    raise ValueError(
                        f"{item.type}/{item.key} exists remotely without a local baseline; pull or bind first"
                    )
                bundle.update_state(root, profile["api_url"], item, current)
            if keep_audience and (current is None or not current.get("published_version")):
                raise ValueError(f"cannot keep audience for unpublished {item.type}/{item.key}")
            if (
                mode == "publish"
                and current
                and current.get("published_version")
                and not keep_audience
                and current.get("audience") != audience
                and not replace_audience
            ):
                raise ValueError(
                    f"{item.type}/{item.key}: changing the audience requires --replace-audience"
                )
            snapshots[(item.type, item.key)] = current
        results = []
        failure = None
        for index, item in enumerate(templates):
            item_audience = audience
            if keep_audience:
                item_audience = snapshots[(item.type, item.key)]["audience"]  # type: ignore[index]
            payload = {
                "draft": canonical[(item.type, item.key)],
                "mode": mode,
                "audience": item_audience,
                "keep_audience": False,
                "replace_audience": replace_audience,
                "bind_id": None,
            }
            try:
                record = _apply_one(client, root, item, profile["api_url"], payload)
                results.append(
                    {
                        "type": item.type,
                        "key": item.key,
                        "status": record["result"],
                        "revision": record["revision"],
                    }
                )
            except APIError as exc:
                failure = str(exc)
                results.append({"type": item.type, "key": item.key, "status": "failed"})
                results.extend(
                    {"type": x.type, "key": x.key, "status": "unattempted"}
                    for x in templates[index + 1 :]
                )
                break
        emit({"mode": mode, "templates": results, "complete": failure is None})
        if failure:
            click.echo(f"Error: {failure}", err=True)
            raise click.exceptions.Exit(1)
    except (ValueError, APIError) as exc:
        fail(exc)


@templates.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True), default=".")
@click.option("--env", required=True)
def push(path: Path, env: str) -> None:
    _write(path, env, "draft", (), False, False, False)


@templates.command()
@click.argument("path", type=click.Path(path_type=Path, exists=True), default=".")
@click.option("--env", required=True)
@click.option("--org", "orgs", multiple=True)
@click.option("--all-orgs", is_flag=True)
@click.option("--keep-audience", is_flag=True)
@click.option("--replace-audience", is_flag=True)
def publish(
    path: Path,
    env: str,
    orgs: tuple[str, ...],
    all_orgs: bool,
    keep_audience: bool,
    replace_audience: bool,
) -> None:
    if sum((bool(orgs), all_orgs, keep_audience)) != 1:
        fail(ValueError("choose exactly one of --org, --all-orgs, or --keep-audience"))
    _write(path, env, "publish", orgs, all_orgs, keep_audience, replace_audience)


@main.group()
def orgs() -> None:
    """Inspect organizations."""


@orgs.command("list")
@click.option("--env", required=True)
@click.option("--search", default="")
def orgs_list(env: str, search: str) -> None:
    try:
        emit(
            remote(env)[0].request(
                "GET", "/platform/cli/orgs", params={"search": search, "limit": 100, "offset": 0}
            )
        )
    except (ValueError, APIError) as exc:
        fail(exc)


@main.command()
@click.option("--env", required=True)
@click.option("--org", "organization", required=True)
def status(env: str, organization: str) -> None:
    try:
        client, _ = remote(env)
        org = resolve_org(client, organization)
        records = []
        for kind in sorted(bundle.TYPES):
            for record in client.request("GET", template_path(kind)):
                audience = record.get("audience", {})
                eligible = bool(
                    audience.get("publish_all") or org["id"] in audience.get("org_ids", [])
                )
                hidden = org["id"] in record.get("hidden_org_ids", [])
                visible = eligible and not hidden and record.get("published_version", 0) > 0
                records.append(
                    {
                        "type": kind,
                        "key": record["key"],
                        "status": record["status"],
                        "eligible": eligible,
                        "hidden": hidden,
                        "visible": bool(visible),
                    }
                )
        emit({"organization": org, "templates": records})
    except (ValueError, APIError) as exc:
        fail(exc)


@templates.command()
@click.argument("kind", type=click.Choice(sorted(bundle.TYPES)))
@click.argument("key")
@click.option("--id", "record_id", required=True)
@click.option("--env", required=True)
@click.option("--path", type=click.Path(path_type=Path, exists=True), default=".")
def bind(kind: str, key: str, record_id: str, env: str, path: Path) -> None:
    try:
        require_key(key)
        root, templates = bundle.load(path)
        item = next(x for x in templates if x.type == kind and x.key == key)
        client, profile = remote(env)
        existing = client.request("GET", template_path(kind, f"by-id/{record_id}"))
        payload = {
            "draft": existing["draft"],
            "expected_revision": existing["revision"],
            "mode": "draft",
            "audience": None,
            "keep_audience": True,
            "replace_audience": False,
            "bind_id": record_id,
        }
        record = client.request("PUT", template_path(kind, f"{key}/apply"), json=payload)
        bundle.update_state(root, profile["api_url"], item, record)
        emit(record)
    except (ValueError, APIError, StopIteration) as exc:
        fail(ValueError("template not found in path") if isinstance(exc, StopIteration) else exc)


@templates.group()
def preview() -> None:
    """Preview without sending or executing."""


@preview.command("email")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--env", required=True)
@click.option("--output", type=click.Path(path_type=Path), default=Path("preview.html"))
def preview_email(path: Path, env: str, output: Path) -> None:
    try:
        _, templates = bundle.load(path)
        item = templates[0]
        if item.type != "email" or len(templates) != 1:
            raise ValueError("email preview requires one email template directory")
        result = remote(env)[0].request(
            "POST",
            "/platform/cli/templates/email/preview",
            json={"draft": item.draft, "variables": item.sample_data or {}},
        )
        output.write_text(result["html"])
        emit({"output": str(output), "subject": result["subject"], "warnings": result["warnings"]})
    except (ValueError, APIError) as exc:
        fail(exc)


@preview.command("form")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
@click.option("--env", required=True)
@click.option("--open/--no-open", "open_browser", default=True)
def preview_form(path: Path, env: str, open_browser: bool) -> None:
    try:
        root, templates = bundle.load(path)
        item = templates[0]
        profile = config.environment(env)
        base = bundle.state_record(root, profile["api_url"], item)
        if item.type != "form" or len(templates) != 1 or not base:
            raise ValueError("form preview requires one previously pushed form")
        client, profile = remote(env)
        current = client.request("GET", template_path("form", f"by-id/{base['id']}"))
        canonical = client.request(
            "POST", template_path("form", "validate"), json={"draft": item.draft}
        )["draft"]
        if current["draft"] != canonical:
            raise ValueError("local form differs from saved form; push it before previewing")
        url = f"{profile['ops_url']}/ops/templates/forms/{base['id']}"
        if open_browser:
            webbrowser.open(url)
        emit({"url": url, "id": base["id"]})
    except (ValueError, APIError) as exc:
        fail(exc)


@preview.command("workflow")
@click.argument("path", type=click.Path(path_type=Path, exists=True))
def preview_workflow(path: Path) -> None:
    try:
        _, templates = bundle.load(path)
        item = templates[0]
        if item.type != "workflow" or len(templates) != 1:
            raise ValueError("workflow preview requires one workflow template")
        emit({"type": "workflow", "key": item.key, "summary": item.draft, "executed": False})
    except ValueError as exc:
        fail(exc)


if __name__ == "__main__":
    main()
