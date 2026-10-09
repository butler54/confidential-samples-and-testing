import os
from pathlib import Path
import subprocess
import pytest
import sys

from conftest import CHART

PROSE = b"This file demonstrates persistent storage for this confidential container example.\n"


def mock_tools(env, tmp_path):
    tools = tmp_path / "bin"
    tools.mkdir()
    # No mounts/devices are touched. Mock only the OS inspection commands.
    scripts = {
        "timeout": '#!/bin/sh\n[ "$1" != "-k" ] || shift 2\nshift\nexec "$@"\n',
        "findmnt": '#!/bin/sh\n[ "${MOCK_MOUNT:-yes}" = yes ] || exit 1\nprintf "%s xfs\\n" "$EXPECTED_SOURCE"\n',
        "readlink": '#!/bin/sh\n[ "$1" != -f ] || shift\nprintf "%s\\n" "$1"\n',
        "stat": """#!/bin/sh
if [ "$1" = -Lc ]; then
  shift 2
  [ "$1" != -- ] || shift
  exec "$TEST_PYTHON" -c 'import os,sys; s=os.stat(sys.argv[1]); print(str(s.st_dev)+":"+str(s.st_ino))' "$1"
fi
exec /usr/bin/stat "$@"
""",
    }
    for name, content in scripts.items():
        p = tools / name
        p.write_text(content)
        p.chmod(0o755)
    env.update({"PATH": f"{tools}:{os.environ['PATH']}", "SAMPLE_KIND": "plain",
                "EXPECTED_SOURCE": "/dev/block-device", "SKIP_MOUNT": "1", "TEST_PYTHON": sys.executable})
    return env


def run(env, name="prose-file.sh"):
    return subprocess.run(["sh", str(CHART / "scripts" / name)], env=env,
                          text=True, capture_output=True, timeout=6, check=False)


def test_creation_and_replacement(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    first = run(env)
    assert first.returncode == 0, first.stderr
    assert "event=file_created" in first.stdout
    p = Path(env["DATA_DIR"]) / env["FILE_NAME"]
    assert p.read_bytes() == PROSE
    before = p.stat().st_mtime_ns
    second = run(env)
    assert second.returncode == 0
    assert "event=file_existing_verified" in second.stdout
    assert "created=false" in second.stdout
    assert p.stat().st_mtime_ns == before


def test_mismatch_does_not_overwrite_or_log_content(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    p = Path(env["DATA_DIR"]) / env["FILE_NAME"]
    p.write_text("private-content-not-for-logs")
    result = run(env)
    assert result.returncode != 0
    assert "content_mismatch" in result.stdout
    assert "private-content-not-for-logs" not in result.stdout + result.stderr
    assert p.read_text() == "private-content-not-for-logs"


def test_symlink_refused(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    target = tmp_path / "outside"
    target.write_bytes(PROSE)
    (Path(env["DATA_DIR"]) / env["FILE_NAME"]).symlink_to(target)
    result = run(env)
    assert result.returncode != 0
    assert "file_type_invalid" in result.stdout


def test_false_mount_never_touches_file(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    env["MOCK_MOUNT"] = "no"
    result = run(env)
    assert result.returncode != 0
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()


def test_nonregular_file_refused(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    (Path(env["DATA_DIR"]) / env["FILE_NAME"]).mkdir()
    result = run(env)
    assert result.returncode != 0
    assert "file_type_invalid" in result.stdout


def test_readback_and_read_errors_are_distinct(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    cmp_tool = tmp_path / "bin/cmp"
    cmp_tool.write_text("#!/bin/sh\nexit 2\n")
    cmp_tool.chmod(0o755)
    first = run(env)
    assert first.returncode != 0
    assert "readback_failed" in first.stdout and "created=true" in first.stdout
    second = run(env)
    assert second.returncode != 0
    assert "read_failed" in second.stdout and "created=false" in second.stdout
    assert (Path(env["DATA_DIR"]) / env["FILE_NAME"]).read_bytes() == PROSE


@pytest.mark.skipif(os.geteuid() == 0, reason="Root bypasses ordinary filesystem permission denial")
def test_creation_permission_denied(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    data = Path(env["DATA_DIR"])
    data.chmod(0o555)
    try:
        result = run(env)
        assert result.returncode != 0
        assert "create_failed" in result.stdout
        assert not (data / env["FILE_NAME"]).exists()
    finally:
        data.chmod(0o755)


def test_concurrent_creation_does_not_clobber(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    command = ["sh", str(CHART / "scripts/prose-file.sh")]
    processes = [subprocess.Popen(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(2)]
    outputs = [process.communicate(timeout=6)[0] for process in processes]
    assert sum("event=file_created" in output for output in outputs) == 1
    assert (Path(env["DATA_DIR"]) / env["FILE_NAME"]).read_bytes() == PROSE


def test_failed_verification_never_launches_application(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for source in (CHART / "scripts").glob("*.sh"):
        (scripts / source.name).write_bytes(source.read_bytes())
    (scripts / "mount-storage.sh").write_text("#!/bin/sh\nexit 0\n")
    env["SCRIPTS_DIR"] = str(scripts)
    started = tmp_path / "application-started"
    sleeper = tmp_path / "bin/sleep"
    sleeper.write_text('#!/bin/sh\nif [ "$1" = infinity ]; then touch "$APP_STARTED"; exit 0; fi\nexec /bin/sleep "$@"\n')
    sleeper.chmod(0o755)
    env["APP_STARTED"] = str(started)
    file = Path(env["DATA_DIR"]) / env["FILE_NAME"]
    file.write_text("synthetic-mismatch")
    result = subprocess.run(["sh", str(scripts / "main.sh")], env=env,
                            capture_output=True, text=True, timeout=6)
    assert result.returncode != 0
    assert not started.exists()
    assert not (Path(env["CONTROL_DIR"]) / "application.ready").exists()
    assert file.read_text() == "synthetic-mismatch"


def test_storage_path_replaced_between_check_and_open(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    original = tmp_path / "original-storage"
    env["ORIGINAL_STORAGE"] = str(original)
    replacement = tmp_path / "bin/mktemp"
    replacement.write_text('#!/bin/sh\nfile=$(/usr/bin/mktemp "$@") || exit 1\n'
                           'mv "$DATA_DIR" "$ORIGINAL_STORAGE" || exit 1\n'
                           'mkdir "$DATA_DIR" || exit 1\nprintf "%s\\n" "$file"\n')
    replacement.chmod(0o755)
    result = run(env)
    assert result.returncode != 0
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()
    assert "event=file_created" not in result.stdout
    assert not (Path(env["CONTROL_DIR"]) / "application.ready").exists()


def test_error_paths_include_full_file_and_mount(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    file = Path(env["DATA_DIR"]) / env["FILE_NAME"]
    file.write_text("synthetic-mismatch")
    result = run(env)
    assert f"path={file}" in result.stdout
    assert f"mount_path={env['DATA_DIR']}" in result.stdout
    assert "file_check=failed" in result.stdout


def test_outer_timeout_explicitly_skips_file_check(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    timeout = tmp_path / "bin/timeout"
    timeout.write_text('#!/bin/sh\ncase "$*" in *--prepare*) exit 124 ;; esac\n[ "$1" != -k ] || shift 2\nshift\nexec "$@"\n')
    result = run(env, "main.sh")
    assert result.returncode != 0
    assert "file_check=not_run" in result.stdout
    assert "timeout_seconds=2" in result.stdout
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()
