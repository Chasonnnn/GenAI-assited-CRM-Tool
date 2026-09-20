from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse


def config_dir() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "surrogacy-force"


def _read(name: str, default: dict | None = None) -> dict:
    path = config_dir() / name
    if not path.exists():
        return default or {}
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid configuration file {path}") from exc
    return value if isinstance(value, dict) else (default or {})


def _atomic(name: str, data: dict, mode: int = 0o600) -> None:
    directory = config_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(dir=directory, prefix=f".{name}.")
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, directory / name)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_url(url: str, label: str, *, origin_only: bool = False) -> str:
    parsed = urlparse(url)
    loopback = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
        raise ValueError(f"{label} must use HTTPS (HTTP is allowed only for loopback development)")
    if (
        not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or (origin_only and parsed.path not in ("", "/"))
    ):
        raise ValueError(f"invalid {label}")
    return url.rstrip("/")


def set_environment(name: str, api_url: str, ops_url: str) -> None:
    environments = _read("config.json", {"environments": {}})
    environments.setdefault("environments", {})[name] = {
        "api_url": validate_url(api_url, "API URL", origin_only=True),
        "ops_url": validate_url(ops_url, "Ops URL", origin_only=True),
    }
    _atomic("config.json", environments)


def environment(name: str) -> dict:
    try:
        profile = _read("config.json")["environments"][name]
        return {
            "api_url": validate_url(profile["api_url"], "API URL", origin_only=True),
            "ops_url": validate_url(profile["ops_url"], "Ops URL", origin_only=True),
        }
    except KeyError as exc:
        raise ValueError(f"environment {name!r} is not configured") from exc


def store_token(name: str, token: str) -> None:
    identity = environment(name)["api_url"]
    try:
        import keyring  # type: ignore[import-not-found]

        keyring.set_password("surrogacy-force-ops", identity, token)
        return
    except Exception:
        pass
    tokens = _read("tokens.json")
    tokens[identity] = token
    _atomic("tokens.json", tokens)


def token(name: str) -> str:
    identity = environment(name)["api_url"]
    try:
        import keyring  # type: ignore[import-not-found]

        value = keyring.get_password("surrogacy-force-ops", identity)
        if value:
            return value
    except Exception:
        pass
    value = _read("tokens.json").get(identity)
    if not isinstance(value, str) or not value:
        raise ValueError(f"not logged in to environment {name!r}")
    return value


def delete_token(name: str) -> None:
    identity = environment(name)["api_url"]
    try:
        import keyring  # type: ignore[import-not-found]

        keyring.delete_password("surrogacy-force-ops", identity)
    except Exception:
        pass
    tokens = _read("tokens.json")
    if identity in tokens:
        del tokens[identity]
        _atomic("tokens.json", tokens)
