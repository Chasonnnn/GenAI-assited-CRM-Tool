from pathlib import Path
import tomllib

from packaging.requirements import Requirement
from packaging.version import Version


def _requirements_map(dependencies: list[str]) -> dict[str, Requirement]:
    return {
        Requirement(dependency).name.lower(): Requirement(dependency)
        for dependency in dependencies
    }


def test_dependency_pins_match_security_fixes():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)

    dependencies = _requirements_map(pyproject.get("project", {}).get("dependencies", []))
    test_dependencies = _requirements_map(
        pyproject.get("project", {}).get("optional-dependencies", {}).get("test", [])
    )

    expected_minimum_pins = {
        "cryptography": "46.0.6",
        "pyjwt": "2.12.0",
        "requests": "2.33.0",
    }
    expected_exact_pins = {
        "pillow": "12.2.0",
        "pypdf": "6.10.2",
        "python-multipart": "0.0.26",
    }
    expected_test_exact_pins = {"pytest": "9.0.3"}

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
