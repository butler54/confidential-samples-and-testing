from conftest import deployment, render


def test_direct_mount_not_persistent_volume_interface():
    objects = render()
    pod = deployment(objects)["spec"]["template"]["spec"]
    assert not pod.get("initContainers")
    assert not pod.get("shareProcessNamespace", False)
    assert not any(x["kind"] in ["PersistentVolume", "PersistentVolumeClaim"] for x in objects)
    assert not any("nfs" in x or "persistentVolumeClaim" in x for x in pod["volumes"])
    assert len(pod["containers"]) == 1


def test_nfs_inputs_and_ipv6():
    render({"nfs": {"server": "", "exportPath": ""}}, success=False)
    render({"nfs": {"server": "host;id", "exportPath": "/exports"}}, success=False)
    render({"nfs": {"server": "host", "exportPath": "/exports/../bad"}}, success=False)
    pod = deployment(render({"nfs": {"server": "2001:db8::1", "exportPath": "/exports"}}))["spec"]["template"]["spec"]
    env = {x["name"]: x["value"] for x in pod["containers"][0]["env"]}
    assert env["EXPECTED_SOURCE"] == "[2001:db8::1]:/exports"
    root = deployment(render({"nfs": {"server": "host", "exportPath": "/"}}))["spec"]["template"]["spec"]
    assert any(e.get("value") == "host:/" for e in root["containers"][0]["env"])
