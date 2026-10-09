import os
from pathlib import Path
import subprocess

import pytest
from conftest import CHART
from test_startup import mock_tools
from test_startup import PROSE


@pytest.mark.parametrize("generation,source,allowed", [("123", "/dev/dm-0", True),
                                                     ("999", "/dev/dm-0", False),
                                                     ("123", "/dev/dm-1", False)])
def test_current_helper_identity_required(script_env, tmp_path, generation, source, allowed):
    env = mock_tools(script_env, tmp_path)
    (tmp_path / "bin/readlink").unlink() # Real readlink for the proc-root symlink.
    pid = os.getpid() # Live unprivileged fixture process; no real device/mount is involved.
    proc = tmp_path / "proc"
    root = proc / str(pid)
    (root / "root/mnt/storage").mkdir(parents=True)
    (root / "stat").write_text(f"{pid} (fixture) " + " ".join(["S"] + ["0"] * 18 + ["123"]))
    (root / "mountinfo").write_text(f"36 28 253:0 / /mnt/storage rw - xfs {source} rw\n")
    (Path(env["CONTROL_DIR"]) / "helper.state").write_text(f"{pid} {generation} /dev/dm-0\n")
    env.update({"SAMPLE_KIND": "encrypted", "PROC_ROOT": str(proc)})
    result = subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"],
                            env=env, text=True, capture_output=True, timeout=6)
    assert (result.returncode == 0) == allowed, result.stdout + result.stderr
    assert not (Path(env["DATA_DIR"]) / env["FILE_NAME"]).exists()


def test_restart_invalidates_old_application_readiness(script_env, tmp_path):
    env = mock_tools(script_env, tmp_path)
    (tmp_path / "bin/readlink").unlink()
    pid = os.getpid()
    proc = tmp_path / "proc"
    root = proc / str(pid)
    data = root / "root/mnt/storage"
    data.mkdir(parents=True)
    (data / env["FILE_NAME"]).write_bytes(PROSE)
    (root / "stat").write_text(f"{pid} (fixture) " + " ".join(["S"] + ["0"] * 18 + ["123"]))
    (root / "mountinfo").write_text("36 28 253:0 / /mnt/storage rw - xfs /dev/dm-0 rw\n")
    control = Path(env["CONTROL_DIR"])
    state = f"{pid} 123 /dev/dm-0\n"
    (control / "helper.state").write_text(state)
    (control / "application.ready").write_text(state)
    env.update({"SAMPLE_KIND": "encrypted", "PROC_ROOT": str(proc)})
    subprocess.run(["sh", str(CHART / "scripts/storage-access.sh"), "--wait"], env=env, check=True, capture_output=True)
    command = ["sh", str(CHART / "scripts/readiness.sh")]
    assert subprocess.run(command, env=env, capture_output=True).returncode == 0
    (control / "helper.state").unlink()
    assert subprocess.run(command, env=env, capture_output=True).returncode != 0
    (control / "helper.state").write_text(f"{pid} 124 /dev/dm-0\n")
    (root / "stat").write_text(f"{pid} (fixture) " + " ".join(["S"] + ["0"] * 18 + ["124"]))
    assert subprocess.run(command, env=env, capture_output=True).returncode != 0
