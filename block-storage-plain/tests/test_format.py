from pathlib import Path
import subprocess

import pytest
from conftest import CHART


@pytest.mark.parametrize("kind,inspect,blank,allowed", [
    ("xfs", "0", "0", True), ("", "0", "0", True),
    ("ext4", "0", "0", False), ("", "1", "0", False), ("", "0", "1", False),
])
def test_format_state_machine(tmp_path, kind, inspect, blank, allowed):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    (scripts / "log.sh").write_bytes((CHART / "scripts/log.sh").read_bytes())
    (scripts / "device.sh").write_text(
        'device_type() { [ "$MOCK_INSPECT" = 0 ] || return 1; printf "%s" "$MOCK_KIND"; }\n'
        'blank_device() { [ "$MOCK_BLANK" = 0 ]; }\n')
    tools = tmp_path / "bin"
    tools.mkdir()
    t = tools / "timeout"
    t.write_text('#!/bin/sh\nshift 3\nexec "$@"\n')
    t.chmod(0o755)
    t = tools / "mkfs.xfs"
    t.write_text('#!/bin/sh\ntouch "$FORMATTED"\n')
    t.chmod(0o755)
    env = {"PATH": f"{tools}:/usr/bin:/bin", "SCRIPTS_DIR": str(scripts), "DEVICE": "/dev/mock",
           "MOCK_KIND": kind, "MOCK_INSPECT": inspect, "MOCK_BLANK": blank,
           "FORMATTED": str(tmp_path / "formatted")}
    result = subprocess.run(["sh", str(CHART / "scripts/format-storage.sh")], env=env,
                            text=True, capture_output=True, check=False)
    assert (result.returncode == 0) == allowed
    assert (tmp_path / "formatted").exists() == (allowed and not kind)


def test_device_inspection_guards():
    text = (CHART / "scripts/device.sh").read_text()
    assert '[ -b "$1" ]' in text
    assert "blockdev --getsize64" in text
    assert 'cmp -n "$bytes" "$1" /dev/zero' in text
    assert "mkfs" not in text


def test_duplicate_luks2_headers_normalized():
    result = subprocess.run(["sh", "-c", '. "$1"; normalize_device_types "$2"', "test",
                             str(CHART / "scripts/device.sh"), "crypto_LUKS\ncrypto_LUKS"],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "crypto_LUKS"
