import tomllib
from pathlib import Path

import jwt
import pytest
from packaging.requirements import Requirement
from packaging.version import Version


def _requirements_map(dependencies: list[str]) -> dict[str, Requirement]:
    return {
        Requirement(dependency).name.lower(): Requirement(dependency) for dependency in dependencies
    }


@pytest.mark.parametrize("claim", ["exp", "nbf", "iat"])
def test_session_token_rejects_invalid_time_claim_as_invalid_token(claim):
    """Malformed signed JSON stays within the decoder's documented auth-error contract."""
    from app.core.config import settings
    from app.core.security import decode_session_token

    token = jwt.encode({claim: []}, settings.JWT_SECRET.get_secret_value(), algorithm="HS256")
    with pytest.raises(jwt.InvalidTokenError):
        decode_session_token(token)


def test_dependency_pins_match_security_fixes():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)

    dependencies = _requirements_map(pyproject.get("project", {}).get("dependencies", []))
    test_dependencies = _requirements_map(
        pyproject.get("project", {}).get("optional-dependencies", {}).get("test", [])
    )

    expected_minimum_pins = {
        "cryptography": "50.0.0",
        "mako": "1.3.12",
        "pyjwt": "2.15.1",
        "python-dotenv": "1.2.2",
        "requests": "2.33.0",
        "urllib3": "2.8.0",
    }
    expected_exact_pins = {
        "fastapi": "0.142.2",
        "idna": "3.18",
        "pillow": "12.3.0",
        "pydantic-settings": "2.14.2",
        "pypdf": "6.19.0",
        "python-multipart": "0.0.31",
        "starlette": "1.3.1",
    }
    expected_test_exact_pins = {"httpx2": "2.12.0", "pytest": "9.0.3"}

    for dependency_name, version in expected_minimum_pins.items():
        requirement = dependencies.get(dependency_name)
        assert requirement is not None, f"Expected {dependency_name} in pyproject.toml dependencies"
        specifier = str(requirement.specifier)
        assert specifier.startswith("=="), f"Expected {dependency_name} to be exactly pinned"
        assert Version(specifier.removeprefix("==")) >= Version(version)

    for dependency_name, version in expected_exact_pins.items():
        requirement = dependencies.get(dependency_name)
        assert requirement is not None, f"Expected {dependency_name} in pyproject.toml dependencies"
        assert str(requirement.specifier) == f"=={version}"

    for dependency_name, version in expected_test_exact_pins.items():
        requirement = test_dependencies.get(dependency_name)
        assert requirement is not None, f"Expected {dependency_name} in test optional dependencies"
        assert str(requirement.specifier) == f"=={version}"
