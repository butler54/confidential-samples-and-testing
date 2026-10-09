"""Static chart assertions: only Helm render/package commands, never workload shell."""
from pathlib import Path
import subprocess
import tarfile
import tempfile
import yaml

CHART = Path(__file__).resolve().parents[1]
RENDERS = 0


def render(values=(), release="encrypted", namespace="examples", reject=False):
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
    assert dep["metadata"]["name"] == "encrypted"
    assert dep["spec"]["replicas"] == 1
    assert dep["spec"]["strategy"]["type"] == "Recreate"
    spec = pod(docs)
    assert [c["name"] for c in spec["initContainers"]] == ["fetch-key", "storage-helper"]
    assert spec["initContainers"][1]["restartPolicy"] == "Always"
    assert spec["shareProcessNamespace"] is True
    assert [c["name"] for c in spec["containers"]] == ["application"]
    assert spec["serviceAccountName"] == "encrypted-sa"
    assert spec["automountServiceAccountToken"] is False
    assert next(d for d in docs if d["kind"] == "ServiceAccount")["metadata"]["name"] == spec["serviceAccountName"]
    assert {d["kind"] for d in docs} == {"Deployment", "ServiceAccount", "ConfigMap", "PersistentVolumeClaim"}
    claim = next(d for d in docs if d["kind"] == "PersistentVolumeClaim")
    assert claim["metadata"]["name"] == "encrypted-block"
    assert claim["spec"]["volumeMode"] == "Block"
    assert claim["spec"]["accessModes"] == ["ReadWriteOnce"]
    assert "storageClassName" not in claim["spec"]
    assert not any(d["kind"] == "Secret" for d in docs)
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert values["images"]["storageHelper"] == "registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1"
    assert values["images"]["utility"] == "registry.access.redhat.com/ubi9/ubi:9.6"
    assert set(values["images"]) == {"storageHelper", "utility"}
    assert "nfs" not in values
    templates = "\n".join(p.read_text() for p in (CHART / "templates").iterdir())
    for unused in ("eq .Chart.Name", "sample.memoryBytes", "sample.cpuMilli", "sample.decodeSegment"):
        assert unused not in templates, unused
    scripts = {p.name: p.read_text() for p in (CHART / "scripts").glob("*.sh")}
    assert all("SAMPLE_KIND" not in text and "mount.expired" not in text for text in scripts.values())
    helper = scripts["encrypted-storage.sh"]
    for guard in ("blank_device", "--test-passphrase", "mapper_source_mismatch", "unprocessed_sealed_token", "unset PASS", "incompatible_filesystem", "helper.state.new"):
        assert guard in helper, guard
    assert helper.index("trap cleanup EXIT") < helper.index("cryptsetup open")
    assert helper.index("unset PASS") < helper.index("mkdir -p")
    for guard in ("generation", "/proc/", "mountinfo", "readlink", "stat --"):
        assert guard in scripts["storage-access.sh"], guard
    for guard in ("cd -P", "set -C", "readback_failed", "content_mismatch", "storage_view_changed"):
        assert guard in scripts["prose-file.sh"], guard
    for guard in ("127.0.0.1:8006/cdh/resource/", "--max-time", "validate_key_file", "chmod 700"):
        assert guard in scripts["fetch-key.sh"], guard
    assert "--fingerprint" in scripts["readiness.sh"] and "cmp -s" in scripts["readiness.sh"]
    assert "helm.sh/resource-policy" not in templates and "helm.sh/hook" not in templates
    # Key alternatives use references only; no real keys or token fixtures.
    for mode in ("sealed", "insecureSecret"):
        selected = render([f"keyDelivery.mode={mode}", "keyDelivery.secret.name=existing-key", "keyDelivery.secret.key=envelope"])
        spec = pod(selected)
        assert [c["name"] for c in spec["initContainers"]] == ["storage-helper"]
        helper_env = {e["name"]: e for e in spec["initContainers"][0]["env"]}
        assert helper_env["KEY_MODE"]["value"] == mode
        assert helper_env["PASS"]["valueFrom"]["secretKeyRef"] == {"name": "existing-key", "key": "envelope"}
        assert not any(d["kind"] == "Secret" for d in selected)
    custom = pod(render(["keyDelivery.resourcePath=tenant/keys/disk"]))
    assert custom["initContainers"][0]["env"] == [{"name": "KBS_RESOURCE_PATH", "value": "tenant/keys/disk"}]
    assert all(e["name"] != "PASS" for e in custom["initContainers"][1]["env"])
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
    overridden = render(["storage.storageClass=test-block-delete", "storage.size=2Gi",
                         "images.storageHelper=mirror.example.test/helper:1.13.1", "images.utility=mirror.example.test/ubi:9.6",
                         "imagePullSecrets[0].name=pull-ref", "imagePullPolicy=Never", "runtimeClassName=custom-kata",
                         "startup.timeoutSeconds=120", "resources.application.requests.cpu=250m"])
    spec = pod(overridden)
    assert spec["runtimeClassName"] == "custom-kata" and spec["imagePullSecrets"] == [{"name": "pull-ref"}]
    assert spec["initContainers"][0]["image"] == "mirror.example.test/ubi:9.6"
    assert spec["initContainers"][1]["image"] == spec["containers"][0]["image"] == "mirror.example.test/helper:1.13.1"
    assert all(c["imagePullPolicy"] == "Never" for c in spec["initContainers"] + spec["containers"])
    assert spec["containers"][0]["resources"]["requests"]["cpu"] == "250m"
    claim = next(d for d in overridden if d["kind"] == "PersistentVolumeClaim")
    assert claim["spec"]["storageClassName"] == "test-block-delete" and claim["spec"]["resources"]["requests"]["storage"] == "2Gi"
    privileged = render(["security.sccBinding.create=true", "security.sccBinding.name=test-scc"])
    role = next(d for d in privileged if d["kind"] == "Role")
    binding = next(d for d in privileged if d["kind"] == "RoleBinding")
    assert role["rules"][0]["resourceNames"] == ["test-scc"] and role["rules"][0]["verbs"] == ["use"]
    assert binding["subjects"] == [{"kind": "ServiceAccount", "name": "encrypted-sa", "namespace": "examples"}]
    for invalid in ("keyDelivery.mode=invalid", "keyDelivery.mode=sealed", "keyDelivery.mode=insecureSecret",
                    "keyDelivery.secret.name=conflicting", "keyDelivery.resourcePath=bad/path", "keyDelivery.resourcePath=bad;path/x/y",
                    "nfs.server=other", "startup.timeoutSeconds=0", "storage.storageClass=", "storage.size=0Gi",
                    "images.utility=mirror.example.test/ubi:latest", "unexpected=true"):
        render([invalid], reject=True)
    identities = []
    for name, namespace in (("encrypted", "examples"), ("encrypted-two", "examples"), ("encrypted", "another"), ("a" * 53, "examples")):
        rendered = render(release=name, namespace=namespace)
        dep = deployment(rendered)
        assert all(len(d["metadata"]["name"]) <= 63 for d in rendered)
        selectors = dep["spec"]["selector"]["matchLabels"]
        assert all(dep["spec"]["template"]["metadata"]["labels"][k] == v for k, v in selectors.items())
        env = {e["name"]: e["value"] for e in pod(rendered)["containers"][0]["env"]}
        identities.append(env["FILE_NAME"])
        assert pod(rendered)["volumes"][-1]["persistentVolumeClaim"]["claimName"] == name + "-block"
    assert len(set(identities)) == 4
    dotted = pod(render(release="a.b"))
    assert dotted["initContainers"][1]["env"][0]["value"] == "sample-a.b"
    assert "*[!A-Za-z0-9_.-]*" in helper
    assert pod(render(release="default"))["serviceAccountName"] == "default-sa"
    metadata = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert metadata["version"] == "0.2.0" and metadata["appVersion"] == "1.13.1"
    assert metadata["kubeVersion"] == ">=1.33.0-0" and not metadata.get("dependencies")
    assert set(next(d for d in docs if d["kind"] == "ConfigMap")["data"]) == set(scripts)
    with tempfile.TemporaryDirectory(prefix="encrypted-static-") as scratch:
        subprocess.run(["helm", "package", str(CHART), "--destination", scratch], capture_output=True, check=True)
        package = next(Path(scratch).glob("*.tgz"))
        with tarfile.open(package) as archive:
            names = archive.getnames()
            assert all("/tests/" not in name and not name.endswith(".py") for name in names)
            assert sum("/scripts/" in name for name in names) == len(scripts)
        result = subprocess.run(["helm", "template", "encrypted", str(package), "--namespace", "examples", "--kube-version", "1.33.0"], capture_output=True, text=True, check=True)
        assert list(yaml.safe_load_all(result.stdout)) == list(yaml.safe_load_all(subprocess.check_output(["helm", "template", "encrypted", str(CHART), "--namespace", "examples", "--kube-version", "1.33.0"], text=True)))
    print(f"encrypted: {RENDERS} static renders/rejections, safety-source and standalone-package checks passed")


if __name__ == "__main__":
    check()
