from conftest import deployment, render


def test_plain_device_attachment():
    pod = deployment(render())["spec"]["template"]["spec"]
    assert pod["initContainers"][0]["command"][-1].endswith("format-storage.sh")
    for container in [pod["initContainers"][0], pod["containers"][0]]:
        assert container["volumeDevices"] == [{"name": "block", "devicePath": "/dev/block-device"}]
    assert not pod.get("shareProcessNamespace", False)
    assert "lifecycle" not in pod["containers"][0]
    assert all(env["name"] != "PASS" for env in pod["containers"][0]["env"])
