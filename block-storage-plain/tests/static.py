"""Static chart assertions: only Helm render/package commands, never workload shell."""
from pathlib import Path
import subprocess
import tarfile
import tempfile
import yaml

CHART = Path(__file__).resolve().parents[1]
RENDERS = 0


def render(values=(), release="plain", namespace="examples", reject=False):
    global RENDERS
    RENDERS += 1
    args = ["helm", "template", release, str(CHART), "--namespace", namespace,
            "--kube-version", "1.33.0"]
    for value in values:
        args += ["--set", value]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if reject:
        assert result.returncode, "invalid values unexpectedly rendered"
        return []
    assert result.returncode == 0, "Helm render failed (no values/output echoed)"
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def deployment(docs):
    return next(doc for doc in docs if doc["kind"] == "Deployment")


def pod(docs):
    return deployment(docs)["spec"]["template"]["spec"]


def check():
    docs = render()
    dep = deployment(docs)
    assert dep["metadata"]["name"] == "plain"
    assert dep["spec"]["replicas"] == 1
    assert dep["spec"]["strategy"]["type"] == "Recreate"
    spec = pod(docs)
    assert [c["name"] for c in spec["initContainers"]] == ["storage-helper"]
    assert [c["name"] for c in spec["containers"]] == ["application"]
    assert spec["serviceAccountName"] == "plain-sa"
    assert spec["automountServiceAccountToken"] is False
    assert next(d for d in docs if d["kind"] == "ServiceAccount")["metadata"]["name"] == spec["serviceAccountName"]
    claim = next(d for d in docs if d["kind"] == "PersistentVolumeClaim")
    assert claim["metadata"]["name"] == "plain-block"
    assert claim["spec"]["volumeMode"] == "Block"
    assert claim["spec"]["accessModes"] == ["ReadWriteOnce"]
    assert "storageClassName" not in claim["spec"]
    assert {d["kind"] for d in docs} == {"Deployment", "ServiceAccount", "ConfigMap", "PersistentVolumeClaim"}
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert values["images"]["storageHelper"] == "registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1"
    assert set(values["images"]) == {"storageHelper"}
    assert set(values["resources"]) == {"application", "storageHelper"}
    assert "keyDelivery" not in values and "nfs" not in values
    templates = "\n".join(p.read_text() for p in (CHART / "templates").iterdir())
    for unused in ("eq .Chart.Name", "sample.memoryBytes", "sample.cpuMilli", "sample.decodeSegment"):
        assert unused not in templates, unused
    scripts = {p.name: p.read_text() for p in (CHART / "scripts").glob("*.sh")}
    assert all("SAMPLE_KIND" not in text and "mount.expired" not in text for text in scripts.values())
    device = scripts["device.sh"]
    for guard in ("wipefs --no-act", "blockdev --getsize64", "cmp -n", "/dev/zero", "return 1"):
        assert guard in device, guard
    assert "blank_device" in scripts["format-storage.sh"]
    assert "incompatible_signature" in scripts["format-storage.sh"]
    assert "mount -t xfs" in scripts["mount-storage.sh"]
    for guard in ("cd -P", "set -C", "readback_failed", "content_mismatch", "storage_view_changed", "check_view"):
        assert guard in scripts["prose-file.sh"], guard
    main = scripts["main.sh"]
    assert main.index("--prepare") < main.index("prose-file.sh") < main.index("application.ready.new")
    assert "--fingerprint" in scripts["readiness.sh"] and "cmp -s" in scripts["readiness.sh"]
    assert "helm.sh/resource-policy" not in templates and "helm.sh/hook" not in templates
    # Essential overrides, not an exhaustive arbitrary-policy matrix.
    annotations = dep["spec"]["template"]["metadata"]["annotations"]
    assert annotations["coco.io/initdata-configmap"] == "debug-initdata"
    for overrides, expected in ((["initdata.encoded=eA=="], "inline"),
                                (["initdata.configMapName="], "cluster"),
                                (["initdata.configMapName=custom-initdata"], "config")):
        metadata = deployment(render(overrides))["spec"]["template"]["metadata"]
        annotations = metadata["annotations"]
        if expected == "inline":
            assert annotations["io.katacontainers.config.hypervisor.cc_init_data"] == "eA=="
        if expected != "config":
            assert "coco.io/initdata-configmap" not in annotations
            assert metadata["labels"]["coco.io/skip-initdata"] == "true"
        else:
            assert annotations["coco.io/initdata-configmap"] == "custom-initdata"
    overrides = render(["storage.storageClass=test-block-delete", "storage.size=2Gi",
                        "images.storageHelper=mirror.example.test/helper:1.13.1",
                        "imagePullSecrets[0].name=pull-ref", "imagePullPolicy=Never",
                        "runtimeClassName=custom-kata", "startup.timeoutSeconds=120",
                        "resources.application.requests.cpu=250m"])
    spec = pod(overrides)
    assert spec["runtimeClassName"] == "custom-kata"
    assert spec["imagePullSecrets"] == [{"name": "pull-ref"}]
    for container in spec["initContainers"] + spec["containers"]:
        assert container["image"] == "mirror.example.test/helper:1.13.1"
        assert container["imagePullPolicy"] == "Never"
    assert spec["containers"][0]["resources"]["requests"]["cpu"] == "250m"
    claim = next(d for d in overrides if d["kind"] == "PersistentVolumeClaim")
    assert claim["spec"]["storageClassName"] == "test-block-delete"
    assert claim["spec"]["resources"]["requests"]["storage"] == "2Gi"
    privileged = render(["security.sccBinding.create=true", "security.sccBinding.name=test-scc"])
    role = next(d for d in privileged if d["kind"] == "Role")
    binding = next(d for d in privileged if d["kind"] == "RoleBinding")
    assert role["rules"] == [{"apiGroups": ["security.openshift.io"], "resources": ["securitycontextconstraints"], "resourceNames": ["test-scc"], "verbs": ["use"]}]
    assert binding["subjects"] == [{"kind": "ServiceAccount", "name": "plain-sa", "namespace": "examples"}]
    for invalid in ("nfs.server=other", "keyDelivery.mode=curl", "startup.timeoutSeconds=0",
                    "startup.timeoutSeconds=3601", "storage.storageClass=", "storage.size=0Gi",
                    "images.storageHelper=mirror.example.test/helper:latest", "unexpected=true"):
        render([invalid], reject=True)
    identities = []
    for name, namespace in (("plain", "examples"), ("plain-two", "examples"), ("plain", "another"), ("a" * 53, "examples")):
        rendered = render(release=name, namespace=namespace)
        dep = deployment(rendered)
        assert all(len(d["metadata"]["name"]) <= 63 for d in rendered)
        selectors = dep["spec"]["selector"]["matchLabels"]
        assert all(dep["spec"]["template"]["metadata"]["labels"][k] == v for k, v in selectors.items())
        env = {e["name"]: e["value"] for e in pod(rendered)["containers"][0]["env"]}
        identities.append(env["FILE_NAME"])
        assert pod(rendered)["volumes"][-1]["persistentVolumeClaim"]["claimName"] == name + "-block"
    assert len(set(identities)) == 4
    assert deployment(render(release="a.b"))["metadata"]["name"] == "a.b"
    assert pod(render(release="default"))["serviceAccountName"] == "default-sa"
    metadata = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert metadata["version"] == "0.2.0" and metadata["appVersion"] == "1.13.1"
    assert metadata["kubeVersion"] == ">=1.33.0-0" and not metadata.get("dependencies")
    assert set(next(d for d in docs if d["kind"] == "ConfigMap")["data"]) == set(scripts)
    with tempfile.TemporaryDirectory(prefix="plain-static-") as scratch:
        subprocess.run(["helm", "package", str(CHART), "--destination", scratch], capture_output=True, check=True)
        package = next(Path(scratch).glob("*.tgz"))
        with tarfile.open(package) as archive:
            names = archive.getnames()
            assert all("/tests/" not in name and not name.endswith(".py") for name in names)
            assert sum("/scripts/" in name for name in names) == len(scripts)
        result = subprocess.run(["helm", "template", "plain", str(package), "--namespace", "examples", "--kube-version", "1.33.0"], capture_output=True, text=True, check=True)
        assert list(yaml.safe_load_all(result.stdout)) == list(yaml.safe_load_all(subprocess.check_output(["helm", "template", "plain", str(CHART), "--namespace", "examples", "--kube-version", "1.33.0"], text=True)))
    print(f"plain: {RENDERS} static renders/rejections, safety-source and standalone-package checks passed")


if __name__ == "__main__":
    check()
