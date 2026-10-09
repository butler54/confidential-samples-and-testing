import subprocess
import sys

import pytest
from conftest import CHART


@pytest.mark.parametrize("arguments", [
    ["verify", "--namespace", "samples", "--release", "test"],
    ["verify", "--context", "explicit", "--namespace", "samples", "--release", "test", "--replace-pods"],
    ["uninstall", "--context", "explicit", "--namespace", "samples", "--release", "test"],
    ["verify", "--context", "explicit", "--namespace", "bad;name", "--release", "test"],
    ["verify", "--context", "explicit", "--namespace", "samples", "--release", "test", "--expect-failure"],
])
def test_explicit_context_and_destructive_authorization_required(arguments):
    result = subprocess.run([sys.executable, str(CHART / "tests/live.py"), *arguments],
                            capture_output=True, text=True, check=False, timeout=5)
    assert result.returncode == 2
