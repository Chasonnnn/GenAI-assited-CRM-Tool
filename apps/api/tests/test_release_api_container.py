"""Exercise the release command against single-container and sidecar services."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml


@pytest.mark.parametrize("container_name", ["", "api"])
def test_api_release_updates_only_the_application_container(tmp_path, container_name):
    config = yaml.safe_load(
        (Path(__file__).resolve().parents[3] / "cloudbuild/api.yaml").read_text()
    )
    script = next(
        step["args"][-1]
        for step in config["steps"]
        if 'gcloud run services update "$_API_SERVICE"' in step.get("args", [""])[-1]
    )
    image_file = tmp_path / "release-api-image-ref"
    image_file.write_text("registry.example/api@sha256:validated-image\n")
    script = script.replace("/workspace/release-api-image-ref", str(image_file))
    for name, value in config["substitutions"].items():
        script = script.replace(f"${name}", value)
    script = script.replace("$$", "$")
    log = tmp_path / "calls.jsonl"
    stub = tmp_path / "gcloud"
    stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "with open(os.environ['CALL_LOG'], 'a') as stream:\n"
        "    stream.write(json.dumps(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:4] == ['run', 'services', 'describe']:\n"
        "    print(os.environ['API_CONTAINER'])\n"
    )
    stub.chmod(0o700)
    subprocess.run(
        ["bash", "-ceu", script],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "CALL_LOG": str(log),
            "API_CONTAINER": container_name,
        },
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    update = next(call for call in calls if call[:3] == ["run", "services", "update"])
    assert update[update.index("--image") + 1] == "registry.example/api@sha256:validated-image"
    assert "trace-collector" not in update
    if container_name:
        assert update[update.index("--container") + 1] == container_name
    else:
        assert "--container" not in update
    assert "--update-env-vars" in update
    assert "--set-env-vars" not in update
