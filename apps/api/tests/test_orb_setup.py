"""Exercise orb setup without downloading tools or changing the host system."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("version", [None, "2026.4.28", "2026.7.16", "2026.10.1"])
def test_setup_upgrades_only_missing_or_outdated_mise(tmp_path, version):
    repo = tmp_path / "repo"
    home = tmp_path / "home"
    binaries = tmp_path / "bin"
    for directory in (repo / ".agents", home / ".local/bin", binaries):
        directory.mkdir(parents=True)
    # Never fall through to a real mise, curl, or sudo on the test host.
    for tool in ("bash", "dirname", "grep", "sed", "awk", "dpkg", "mktemp", "rm", "cat", "mkdir", "cp"):
        (binaries / tool).symlink_to(shutil.which(tool))
    shutil.copy(ROOT / ".agents/setup", repo / ".agents/setup")
    (repo / "mise.toml").write_text('min_version = "2026.7.16"\n')
    api = repo / "apps/api"
    (api / ".venv/bin").mkdir(parents=True)
    (api / ".env.example").write_text("ENV=dev\n")

    def executable(path, body):
        path.write_text("#!/bin/bash\nset -eu\n" + body)
        path.chmod(0o755)

    def mise_body(release):
        return f'''
if [[ "$1" == --version ]]; then
    echo '{release} linux-x64'
    exit 0
fi
echo '{release}' "$@" >> "$HOME/calls"
[[ '{release}' != 2026.4.28 ]] || exit 1
'''

    if version:
        executable(binaries / "mise", mise_body(version))
    executable(home / "replacement", mise_body("2026.7.16"))
    executable(binaries / "dpkg-query", "echo 'install ok installed'\n")
    executable(api / ".venv/bin/python", "exit 0\n")
    executable(
        binaries / "curl",
        '''
echo download >> "$HOME/downloads"
while [[ "$1" != -o ]]; do shift; done
cat > "$2" <<'INSTALLER'
[[ "$MISE_VERSION" == 2026.7.16 ]]
[[ "$MISE_INSTALL_PATH" == "$HOME/.local/bin/mise" ]]
mkdir -p "$HOME/.local/bin"
cp "$HOME/replacement" "$HOME/.local/bin/mise"
INSTALLER
''',
    )
    env = {**os.environ, "HOME": str(home), "PATH": str(binaries)}
    result = subprocess.run(
        ["/bin/bash", str(repo / ".agents/setup")],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    needs_upgrade = version in (None, "2026.4.28")
    assert (home / "downloads").exists() == needs_upgrade
    expected_version = "2026.7.16" if needs_upgrade else version
    assert f"{expected_version} install --locked" in (home / "calls").read_text()
