from pathlib import Path
import subprocess

from conftest import CHART
from test_startup import mock_tools


def test_mount_gate_success(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    result = subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"],
                            env=env, text=True, capture_output=True, timeout=6)
    assert result.returncode == 0, result.stderr
    assert "event=storage_accessible" in result.stdout


def test_directory_is_not_mount(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    env["MOCK_MOUNT"] = "no"
    result = subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"],
                            env=env, text=True, capture_output=True, timeout=6)
    assert result.returncode != 0
    assert "mount_timeout" in result.stdout
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()


def test_readiness_requires_file_verification(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    result = subprocess.run(["sh", str(CHART / "scripts/readiness.sh")], env=env,
                            text=True, capture_output=True, timeout=6)
    assert result.returncode != 0


def test_delayed_mount_waits_for_verified_source(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    checks = tmp_path / "checks"
    checks.write_text("0")
    mount = tmp_path / "bin/findmnt"
    mount.write_text('#!/bin/sh\nn=$(cat "$CHECKS"); n=$((n+1)); printf "%s" "$n" > "$CHECKS"\n'
                     '[ "$n" -ge 2 ] || exit 1\nprintf "%s xfs\\n" "$EXPECTED_SOURCE"\n')
    env["CHECKS"] = str(checks)
    result = subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"],
                            env=env, text=True, capture_output=True, timeout=6)
    assert result.returncode == 0, result.stdout + result.stderr
    assert int(checks.read_text()) >= 2
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()
