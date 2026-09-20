from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

KEY = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")
TYPES = {"email", "form", "workflow"}
STATE = ".ops-state.json"


class BundleError(ValueError):
    pass


def _object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise BundleError(f"cannot read valid JSON from {path}") from exc
    if not isinstance(value, dict):
        raise BundleError(f"{path} must contain a JSON object")
    return value


def _contained(root: Path, candidate: Path) -> Path:
    root = root.resolve()
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise BundleError(f"path escapes bundle: {candidate}") from exc
    return resolved


@dataclass(frozen=True)
class Template:
    directory: Path
    type: str
    key: str
    draft: dict
    sample_data: dict | None = None

    def wire_draft(self) -> dict:
        return self.draft


def load_template(directory: Path, root: Path | None = None) -> Template:
    directory = _contained(root or directory, directory)
    envelope = _object(_contained(directory, directory / "template.json"))
    allowed = {"version", "type", "key", "draft", "body_file"}
    unknown = set(envelope) - allowed
    if unknown:
        raise BundleError(f"unknown template fields: {', '.join(sorted(unknown))}")
    if envelope.get("version") != 1 or envelope.get("type") not in TYPES:
        raise BundleError(f"unsupported template envelope in {directory}")
    key = envelope.get("key")
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise BundleError("key must be lowercase letters, digits and hyphens (maximum 100)")
    draft = envelope.get("draft")
    if not isinstance(draft, dict):
        raise BundleError("draft must be an object")
    body_file = envelope.get("body_file")
    if body_file is not None:
        if envelope["type"] != "email" or not isinstance(body_file, str) or not body_file:
            raise BundleError("body_file is supported only for email templates")
        if "body" in draft:
            raise BundleError("email may specify draft.body or body_file, not both")
        draft = {**draft, "body": _contained(directory, directory / body_file).read_text()}
    sample_path = directory / "sample-data.json"
    sample = _object(_contained(directory, sample_path)) if sample_path.exists() else None
    return Template(directory, envelope["type"], key, draft, sample)


def load(path: Path) -> tuple[Path, list[Template]]:
    path = path.resolve()
    if path.is_dir() and (path / "template.json").exists():
        return path, [load_template(path)]
    manifest_path = path / "bundle.json" if path.is_dir() else path
    root = manifest_path.parent.resolve()
    manifest = _object(manifest_path)
    if set(manifest) != {"version", "templates"} or manifest.get("version") != 1:
        raise BundleError("bundle.json requires exactly version and templates")
    entries = manifest["templates"]
    if not isinstance(entries, list) or not entries or not all(isinstance(x, str) for x in entries):
        raise BundleError("bundle templates must be a nonempty list of relative directories")
    templates = [load_template(_contained(root, root / item), root) for item in entries]
    identities = [(item.type, item.key) for item in templates]
    if len(identities) != len(set(identities)):
        raise BundleError("bundle contains duplicate template type/key")
    return root, templates


def state(root: Path) -> dict:
    path = root / STATE
    return _object(path) if path.exists() else {"version": 1, "environments": {}}


def save_state(root: Path, value: dict) -> None:
    temporary = root / f"{STATE}.tmp"
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(root / STATE)


def state_record(root: Path, origin: str, template: Template) -> dict | None:
    del root  # State follows each template when standalone and bundle layouts are interchanged.
    return state(template.directory).get("origins", {}).get(origin)


def update_state(root: Path, origin: str, template: Template, record: dict) -> None:
    del root
    value = state(template.directory)
    value["version"] = 1
    values = value.setdefault("origins", {})
    values[origin] = {"id": record["id"], "revision": record["revision"]}
    save_state(template.directory, value)
