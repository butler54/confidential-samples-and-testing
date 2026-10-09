"""Chart-local fixtures; no imports from sibling examples."""
from pathlib import Path
import os
import subprocess
import tempfile

import pytest
import yaml

CHART = Path(__file__).resolve().parents[1]


def render(values=None, release="test", namespace="samples", success=True):
    supplied = values or {}
    if CHART.name == "nfs-direct":
        supplied = {"nfs": {"server": "nfs.example.test", "exportPath": "/exports/test"}, **supplied}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml") as f:
        yaml.safe_dump(supplied, f)
        f.flush()
        result = subprocess.run(
            ["helm", "template", release, str(CHART), "--namespace", namespace,
             "--kube-version", "1.33.0", "-f", f.name],
            text=True, capture_output=True, check=False,
        )
    if not success:
        assert result.returncode != 0, "Invalid configuration unexpectedly rendered successfully"
        return result
    assert result.returncode == 0, result.stderr
    return [item for item in yaml.safe_load_all(result.stdout) if item]


def deployment(objects):
    return next(item for item in objects if item["kind"] == "Deployment")


@pytest.fixture
def script_env(tmp_path):
    # Do not expose unrelated operator credentials in pytest fixture diagnostics.
    env = {"PATH": os.environ["PATH"]}
    env.update({"SCRIPTS_DIR": str(CHART / "scripts"), "CONTROL_DIR": str(tmp_path / "control"),
                "DATA_DIR": str(tmp_path / "data"), "FILE_NAME": "test-prose.txt",
                "STARTUP_TIMEOUT": "2", "POLL_SECONDS": "1", "OP_TIMEOUT": "1"})
    (tmp_path / "control").mkdir()
    (tmp_path / "data").mkdir()
    return env
