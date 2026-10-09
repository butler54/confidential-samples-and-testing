import subprocess

import pytest
import os
from pathlib import Path
import time
from conftest import CHART


@pytest.mark.parametrize("signature,probe,status,key_exit", [
    ("ext4", 0, 1, 0), ("", 1, 1, 0),
    ("crypto_LUKS", 0, 1, 1), ("crypto_LUKS", 0, 0, 1),
])
def test_no_format_on_bad_signature_probe_or_key(tmp_path, signature, probe, status, key_exit):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ["log.sh", "key.sh"]:
        (scripts / name).write_bytes((CHART / "scripts" / name).read_bytes())
    (scripts / "device.sh").write_text('device_type() { [ "$PROBE_EXIT" = 0 ] || return 1; printf "%s" "$SIGNATURE"; }\nblank_device() { return 1; }\n')
    tools = tmp_path / "bin"
    tools.mkdir()
    mocks = {"timeout": '#!/bin/sh\nshift 3\nexec "$@"\n',
             "cryptsetup": '#!/bin/sh\ncase "$1" in open) exit "$KEY_EXIT" ;; status) exit "$STATUS_EXIT" ;; luksFormat) touch "$FORMATTED" ;; esac\n'}
    for name, body in mocks.items():
        p = tools / name
        p.write_text(body)
        p.chmod(0o755)
    result = subprocess.run(["sh", str(CHART / "scripts/encrypted-storage.sh")], env={
        "PATH": f"{tools}:/usr/bin:/bin", "SCRIPTS_DIR": str(scripts),
        "CONTROL_DIR": str(tmp_path / "control"), "PASS": "synthetic-test-value", "KEY_MODE": "insecureSecret",
        "SIGNATURE": signature, "PROBE_EXIT": str(probe), "KEY_EXIT": str(key_exit), "STATUS_EXIT": str(status),
        "FORMATTED": str(tmp_path / "formatted")}, capture_output=True, text=True, timeout=5)
    assert result.returncode != 0
    assert not (tmp_path / "formatted").exists()
    assert "synthetic-test-value" not in result.stdout + result.stderr


def successful_scenario(tmp_path, raw="crypto_LUKS", fs="xfs", opened=False,
                        backing="/dev/mock", source="/dev/mapper/sample-test", fail_fs=False):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ["log.sh", "key.sh"]:
        (scripts / name).write_bytes((CHART / "scripts" / name).read_bytes())
    (scripts / "device.sh").write_text(
        'device_type() { if [ "$1" = /dev/mock ]; then printf "%s" "$RAW_TYPE"; else printf "%s" "$FS_TYPE"; fi; }\n'
        'blank_device() { return 0; }\n')
    tools = tmp_path / "bin"
    tools.mkdir()
    mocks = {
        "timeout": '#!/bin/sh\nshift 3\nexec "$@"\n',
        "mkdir": '#!/bin/sh\n[ "${2:-}" != /mnt/storage ] || exit 0\nexec /bin/mkdir "$@"\n',
        "cryptsetup": '#!/bin/sh\nprintf "cryptsetup %s\\n" "$*" >> "$CALLS"\n'
            'if [ "$1" = status ]; then [ "$ALREADY_OPEN" = yes ] || exit 1; printf " device: %s\\n" "$BACKING"; fi\n',
        "mkfs.xfs": '#!/bin/sh\nprintf "mkfs\\n" >> "$CALLS"\n[ "$FAIL_FS" != yes ]\n',
        "mount": '#!/bin/sh\nprintf "mount\\n" >> "$CALLS"\ntouch "$MOUNTED"\n',
        "umount": '#!/bin/sh\nprintf "umount\\n" >> "$CALLS"\n',
        "readlink": '#!/bin/sh\n[ "$1" != -f ] || shift\nprintf "%s\\n" "$1"\n',
        "findmnt": '#!/bin/sh\ncase "$*" in *SOURCE,FSTYPE*) printf "%s xfs\\n" "$SOURCE" ;; *) [ -f "$MOUNTED" ] ;; esac\n',
        "sed": """#!/bin/sh
if [ "$1" = 's/.*) //' ]; then
  printf "0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 713\\n"
else
  exec /usr/bin/sed "$@"
fi
""",
    }
    for name, body in mocks.items():
        file = tools / name
        file.write_text(body)
        file.chmod(0o755)
    control = tmp_path / "control"
    env = {"PATH": f"{tools}:/usr/bin:/bin", "SCRIPTS_DIR": str(scripts), "CONTROL_DIR": str(control),
           "DEVICE": "/dev/mock", "MAPPER_NAME": "sample-test", "KEY_MODE": "insecureSecret",
           "PASS": "synthetic-test-value", "RAW_TYPE": raw, "FS_TYPE": fs,
           "ALREADY_OPEN": "yes" if opened else "no", "BACKING": backing, "SOURCE": source,
           "FAIL_FS": "yes" if fail_fs else "no", "CALLS": str(tmp_path / "calls"), "MOUNTED": str(tmp_path / "mounted")}
    process = subprocess.Popen(["sh", str(CHART / "scripts/encrypted-storage.sh")], env=env,
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    end = time.monotonic() + 5
    while time.monotonic() < end and process.poll() is None and not (control / "helper.state").exists():
        time.sleep(0.02)
    state = (control / "helper.state").read_text() if (control / "helper.state").exists() else None
    if process.poll() is None:
        process.terminate()
    stdout, stderr = process.communicate(timeout=5)
    return state, (tmp_path / "calls").read_text(), stdout + stderr, control


@pytest.mark.parametrize("raw,fs,opened", [("", "", False), ("crypto_LUKS", "xfs", False), ("crypto_LUKS", "xfs", True)])
def test_initialize_reopen_and_mapper_reuse(tmp_path, raw, fs, opened):
    state, calls, logs, control = successful_scenario(tmp_path, raw, fs, opened)
    assert state and "713 /dev/mapper/sample-test" in state, logs
    assert "synthetic-test-value" not in calls + logs
    assert ("luksFormat" in calls) == (not raw)
    assert ("mkfs\n" in calls) == (not fs)
    assert calls.index("--test-passphrase") < calls.index("mount\n")
    if not raw:
        assert calls.index("luksFormat") < calls.index("mkfs\n") < calls.index("mount\n")
    assert not (control / "helper.state").exists(), "Stopped helper must invalidate its own state"


@pytest.mark.parametrize("options", [
    {"opened": True, "backing": "/dev/wrong"},
    {"source": "/dev/mapper/wrong"},
    {"raw": "", "fs": "", "fail_fs": True},
])
def test_wrong_mapper_mount_or_post_open_error_never_publishes(tmp_path, options):
    state, calls, logs, _ = successful_scenario(tmp_path, **options)
    assert state is None
    assert "encrypted_storage_mounted" not in logs
    if options.get("backing"):
        assert "mapper_source_mismatch" in logs and "mkfs" not in calls
