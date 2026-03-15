from pathlib import Path
import tomllib

from packaging.version import Version


def test_dependency_pins_meet_security_fix_floors():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)

    dependencies = pyproject.get("project", {}).get("dependencies", [])

    expected_minimums = {
        "pyjwt": "2.12.0",
        "pypdf": "6.8.0",
    }

    for dependency_name, minimum_version in expected_minimums.items():
        pinned_dependency = next(
            (dep for dep in dependencies if dep.startswith(f"{dependency_name}==")),
            None,
        )

        assert (
            pinned_dependency is not None
        ), f"Expected an explicit {dependency_name}== pin in pyproject.toml"

        pinned_version = pinned_dependency.split("==", 1)[1].strip()
        assert Version(pinned_version) >= Version(minimum_version)
