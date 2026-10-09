from pathlib import Path
import subprocess

import pytest
from conftest import CHART


@pytest.mark.parametrize("value,valid", [(b"dummy-test-value", True), (b"", False),
                                        (b"test\n", False), (b"test\0value", False),
                                        (b"\x01", False), (b"a" * 1025, False), (b"sealed.reserved-prefix", False)])
def test_key_byte_contract(tmp_path, value, valid):
    keyfile = tmp_path / "synthetic-key"
    keyfile.write_bytes(value)
    script = CHART / "scripts/key.sh"
    result = subprocess.run(["sh", "-c", '. "$1"; validate_key_file "$2"', "test", str(script), str(keyfile)],
                            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, capture_output=True)
    assert (result.returncode == 0) == valid
    assert value not in result.stdout if value else not result.stdout


@pytest.mark.parametrize("response,exit_code,http_status,allowed", [(b"dummy-test-value", 0, 200, True),
                                                                    (b"", 0, 200, False), (b"error-body", 22, 403, False),
                                                                    (b"redirect-body", 0, 302, False)])
def test_curl_fail_closed(tmp_path, response, exit_code, http_status, allowed):
    tools = tmp_path / "bin"
    tools.mkdir()
    response_file = tmp_path / "response"
    response_file.write_bytes(response)
    curl = tools / "curl"
    curl.write_text('#!/bin/sh\nwhile [ "$#" -gt 0 ]; do\n'
                    'if [ "$1" = --output ]; then cp "$MOCK_RESPONSE" "$2"; fi\nshift\ndone\nprintf "%s" "$MOCK_STATUS"\nexit "$MOCK_EXIT"\n')
    curl.chmod(0o755)
    control = tmp_path / "control"
    env = {"PATH": f"{tools}:/usr/bin:/bin", "SCRIPTS_DIR": str(CHART / "scripts"),
           "CONTROL_DIR": str(control), "KBS_RESOURCE_PATH": "default/kbsres1/key3",
           "MOCK_RESPONSE": str(response_file), "MOCK_EXIT": str(exit_code), "MOCK_STATUS": str(http_status)}
    result = subprocess.run(["sh", str(CHART / "scripts/fetch-key.sh")], env=env,
                            text=True, capture_output=True)
    assert (result.returncode == 0) == allowed
    assert (control / "key").exists() == allowed
    assert response.decode() not in result.stdout + result.stderr if response else True
