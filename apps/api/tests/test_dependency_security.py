from pathlib import Path
import tomllib

from packaging.version import Version


def test_pypdf_pin_meets_cve_2026_fix_floor():
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)

    dependencies = pyproject.get("project", {}).get("dependencies", [])
    pypdf_pin = next((dep for dep in dependencies if dep.startswith("pypdf==")), None)

    assert pypdf_pin is not None, "Expected an explicit pypdf== pin in pyproject.toml"
    pinned_version = pypdf_pin.split("==", 1)[1].strip()
    assert Version(pinned_version) >= Version("6.7.3")
