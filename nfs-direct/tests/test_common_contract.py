import pytest
from conftest import CHART, deployment, render


def test_default_workload_contract():
    objects = render()
    d = deployment(objects)
    assert d["spec"]["replicas"] == 1
    assert d["spec"]["strategy"]["type"] == "Recreate"
    pod = d["spec"]["template"]
    assert pod["metadata"]["annotations"]["coco.io/initdata-configmap"] == "debug-initdata"
    assert pod["spec"]["runtimeClassName"] == "kata-cc"
    assert pod["spec"]["automountServiceAccountToken"] is False
    assert pod["spec"]["serviceAccountName"] != "default"
    assert d["spec"]["selector"]["matchLabels"].items() <= pod["metadata"]["labels"].items()
    assert not {"Namespace", "StorageClass", "PersistentVolume", "SecurityContextConstraints", "ClusterRoleBinding"}.intersection(x["kind"] for x in objects)
    assert not any(x["kind"] == "RoleBinding" for x in objects)


def test_initdata_modes():
    p = deployment(render({"initdata": {"mode": "inline", "encoded": "H4sIAAAAAAAA"}}))["spec"]["template"]
    assert p["metadata"]["annotations"]["io.katacontainers.config.hypervisor.cc_init_data"] == "H4sIAAAAAAAA"
    assert p["metadata"]["labels"]["coco.io/skip-initdata"] == "true"
    assert "coco.io/initdata-configmap" not in p["metadata"]["annotations"]
    p = deployment(render({"initdata": {"mode": "clusterDefault"}}))["spec"]["template"]
    assert "coco.io/initdata-configmap" not in p["metadata"]["annotations"]
    assert p["metadata"]["labels"]["coco.io/skip-initdata"] == "true"


@pytest.mark.parametrize("values", [
    {"initdata": {"mode": "invalid"}}, {"initdata": {"mode": "inline"}},
    {"storage": {"mountPath": "/mnt/../wrong"}}, {"startup": {"timeoutSeconds": 0}},
    {"startup": {"timeoutSeconds": 1, "pollSeconds": 2}},
    {"images": {"application": "registry.test/image:latest"}},
    {"podLabels": {"app.kubernetes.io/instance": "other"}},
    {"podAnnotations": {"coco.io/initdata-configmap": "other"}},
    {"serviceAccount": {"create": False, "name": ""}},
])
def test_reject_invalid(values):
    render(values, success=False)


def test_block_claim_contract():
    if CHART.name == "nfs-direct":
        assert not any(x["kind"] == "PersistentVolumeClaim" for x in render())
        return
    claim = next(x for x in render() if x["kind"] == "PersistentVolumeClaim")
    assert claim["spec"]["volumeMode"] == "Block"
    assert claim["spec"]["accessModes"] == ["ReadWriteOnce"]
    assert "storageClassName" not in claim["spec"]
    claim = next(x for x in render({"storage": {"storageClass": "explicit"}}) if x["kind"] == "PersistentVolumeClaim")
    assert claim["spec"]["storageClassName"] == "explicit"
    render({"storage": {"storageClass": ""}}, success=False)


def test_scc_binding_is_scoped():
    objects = render({"security": {"sccBinding": {"create": True}}})
    role = next(x for x in objects if x["kind"] == "Role")
    assert role["rules"] == [{"apiGroups": ["security.openshift.io"], "resources": ["securitycontextconstraints"], "resourceNames": ["privileged"], "verbs": ["use"]}]
    binding = next(x for x in objects if x["kind"] == "RoleBinding")
    assert binding["subjects"][0]["namespace"] == "samples"
    assert binding["subjects"][0]["name"] == deployment(objects)["spec"]["template"]["spec"]["serviceAccountName"]


@pytest.mark.parametrize("values", [
    {"storage": {"mountPath": "/usr"}}, {"storage": {"mountPath": "/usr/local/data"}},
    {"resources": {"application": {"limits": {"memory": None}}}},
    {"resources": {"application": {"requests": {"cpu": None}}}},
    {"resources": {"application": {"limits": {"memory": "512Mi"}}}},
    {"resources": {"application": {"requests": {"memory": "3Gi"}, "limits": {"memory": "2560Mi"}}}},
    {"images": {"application": "registry.example/image:nightly"}},
])
def test_safe_override_invariants(values):
    render(values, success=False)


def test_annotations_on_all_owned_objects():
    objects = render({"security": {"sccBinding": {"create": True}},
                      "resourceAnnotations": {"example.io/note": "test"}})
    assert all(x["metadata"].get("annotations", {}).get("example.io/note") == "test" for x in objects)
