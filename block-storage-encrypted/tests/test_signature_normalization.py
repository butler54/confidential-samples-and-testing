import subprocess
from conftest import CHART


def test_duplicate_luks2_headers_preserve_single_type():
    result = subprocess.run(["sh", "-c", '. "$1"; normalize_device_types "$2"', "test",
                             str(CHART / "scripts/device.sh"), "crypto_LUKS\ncrypto_LUKS"],
                            capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "crypto_LUKS"


def test_conflicting_types_are_not_hidden():
    result = subprocess.run(["sh", "-c", '. "$1"; normalize_device_types "$2"', "test",
                             str(CHART / "scripts/device.sh"), "crypto_LUKS\nxfs"],
                            capture_output=True, text=True, check=True)
    assert set(result.stdout.splitlines()) == {"crypto_LUKS", "xfs"}
