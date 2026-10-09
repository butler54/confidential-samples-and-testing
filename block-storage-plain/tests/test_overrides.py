import pytest

from conftest import CHART, deployment, render


def test_disconnected_consumed_images_and_metadata():
    images = {role: f"mirror.example:8443/{role}:1.0.0" for role in ["application", "storageHelper", "utility"]}
    pod = deployment(render({"images": images, "podLabels": {"team": "samples"},
                             "podAnnotations": {"example.io/note": "test"}}))["spec"]["template"]
    for container in pod["spec"].get("initContainers", []) + pod["spec"]["containers"]:
        assert container["image"].startswith("mirror.example:8443/")
    assert pod["metadata"]["labels"]["team"] == "samples"
    assert pod["metadata"]["annotations"]["example.io/note"] == "test"


def test_named_initdata_and_resources():
    pod = deployment(render({"initdata": {"configMapName": "alternate"},
                             "resources": {"application": {"limits": {"memory": "4096Mi"}}}}))["spec"]["template"]
    assert pod["metadata"]["annotations"]["coco.io/initdata-configmap"] == "alternate"
    assert pod["spec"]["containers"][0]["resources"]["limits"]["memory"] == "4096Mi"


@pytest.mark.parametrize("path", ["/proc/fake", "/dev/fake", "/run/fake", "/opt/sample/fake"])
def test_reserved_mount_path(path):
    render({"storage": {"mountPath": path}}, success=False)


def test_default_images_have_maintained_references():
    import yaml
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert all(x.startswith("registry.") and (":" in x.rsplit("/", 1)[-1] or "@sha256:" in x) for x in values["images"].values())
    for file in (CHART / "scripts").glob("*.sh"):
        text = file.read_text()
        assert "eval " not in text and "set -x" not in text and "set -ex" not in text
        assert "microdnf " not in text and "dnf install" not in text
