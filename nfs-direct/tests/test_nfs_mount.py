import subprocess
from pathlib import Path
import os
import shutil

import pytest
from conftest import CHART
from test_startup import mock_tools, run, PROSE


@pytest.mark.parametrize("source,options,allowed", [
    ("host:/exports", "vers=4.1,hard", True),
    ("[2001:db8::1]:/exports", "vers=4.1,hard", True),
    ("host;id:/exports", "vers=4.1", False),
    ("host:/exports", "hard;id", False),
])
def test_nfs_mount_uses_quoted_validated_arguments(tmp_path, source, options, allowed):
    tools = tmp_path / "bin"
    tools.mkdir()
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "log.sh").write_bytes((CHART / "scripts/log.sh").read_bytes())
    (scripts / "storage-access.sh").write_text("#!/bin/sh\nexit 0\n")
    mocks = {"mount.nfs": "#!/bin/sh\nexit 0\n", "findmnt": "#!/bin/sh\nexit 1\n",
             "mount": '#!/bin/sh\nprintf "%s\\n" "$@" > "$ARGS_FILE"\n'}
    for name, body in mocks.items():
        p = tools / name
        p.write_text(body)
        p.chmod(0o755)
    args_file = tmp_path / "args"
    env = {"PATH": f"{tools}:/usr/bin:/bin", "SCRIPTS_DIR": str(scripts),
           "DATA_DIR": str(tmp_path / "data"), "EXPECTED_SOURCE": source,
           "NFS_OPTIONS": options, "ARGS_FILE": str(args_file)}
    result = subprocess.run(["sh", str(CHART / "scripts/mount-storage.sh")], env=env,
                            capture_output=True, text=True, timeout=5)
    assert (result.returncode == 0) == allowed, result.stdout + result.stderr
    assert args_file.exists() == allowed
    if allowed:
        assert args_file.read_text().splitlines() == ["-t", "nfs", "-o", options, source, env["DATA_DIR"]]


@pytest.mark.parametrize("actual_source,fs,allowed", [
    ("server:/exports", "nfs4", True), ("server:/exports", "nfs", True),
    ("wrong:/exports", "nfs4", False), ("server:/exports", "xfs", False),
])
def test_real_nfs_kind_source_and_filesystem_gate(script_env, tmp_path, actual_source, fs, allowed):
    env = mock_tools(script_env, tmp_path)
    env.update({"SAMPLE_KIND": "nfs", "EXPECTED_SOURCE": "server:/exports", "ACTUAL_SOURCE": actual_source, "ACTUAL_FS": fs})
    probe = tmp_path / "bin/findmnt"
    probe.write_text('#!/bin/sh\nprintf "%s %s\\n" "$ACTUAL_SOURCE" "$ACTUAL_FS"\n')
    result = run(env)
    assert (result.returncode == 0) == allowed
    assert (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists() == allowed


def test_nfs_existing_prose_read_only_export(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    env.update({"SAMPLE_KIND": "nfs", "EXPECTED_SOURCE": "server:/exports"})
    (tmp_path / "bin/findmnt").write_text('#!/bin/sh\nprintf "%s nfs4\\n" "$EXPECTED_SOURCE"\n')
    data = Path(env["DATA_DIR"])
    (data / env["FILE_NAME"]).write_bytes(PROSE)
    data.chmod(0o555)
    try:
        result = run(env)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "file_existing_verified" in result.stdout and "created=false" in result.stdout
    finally:
        data.chmod(0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="Root bypasses simulated export write denial")
def test_nfs_root_squash_like_write_denial(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    env.update({"SAMPLE_KIND": "nfs", "EXPECTED_SOURCE": "server:/exports"})
    (tmp_path / "bin/findmnt").write_text('#!/bin/sh\nprintf "%s nfs4\\n" "$EXPECTED_SOURCE"\n')
    data = Path(env["DATA_DIR"])
    data.chmod(0o555)
    try:
        result = run(env)
        assert result.returncode != 0 and "create_failed" in result.stdout
        assert not (data / env["FILE_NAME"]).exists()
    finally:
        data.chmod(0o755)


def test_nfs_delayed_and_unreachable_mount(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    env.update({"SAMPLE_KIND": "nfs", "EXPECTED_SOURCE": "server:/exports", "ATTEMPTS": str(tmp_path / "attempts")})
    probe = tmp_path / "bin/findmnt"
    probe.write_text('#!/bin/sh\nif [ ! -f "$ATTEMPTS" ]; then touch "$ATTEMPTS"; exit 1; fi\nprintf "%s nfs4\\n" "$EXPECTED_SOURCE"\n')
    result = subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"], env=env, capture_output=True, text=True, timeout=6)
    assert result.returncode == 0 and "storage_accessible" in result.stdout
    probe.write_text('#!/bin/sh\nexit 1\n')
    result = subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"], env=env, capture_output=True, text=True, timeout=6)
    assert result.returncode != 0 and "mount_timeout" in result.stdout
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()


@pytest.mark.skipif(not shutil.which("timeout"), reason="Real GNU timeout case runs on Linux CI; macOS fixture tests are not a substitute")
def test_nfs_operation_supervision_uses_real_timeout(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    (tmp_path / "bin/timeout").unlink() # Use real Linux timeout, not the command-shape fixture.
    env.update({"SAMPLE_KIND": "nfs", "EXPECTED_SOURCE": "server:/exports", "OP_TIMEOUT": "1"})
    (tmp_path / "bin/findmnt").write_text('#!/bin/sh\nexec sleep 30\n')
    result = run(env)
    assert result.returncode != 0
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()
