"""Static chart assertions: only Helm render/package commands, never workload shell."""
from pathlib import Path
import subprocess
import tarfile
import tempfile
import yaml

CHART = Path(__file__).resolve().parents[1]
NFS = ("nfs.server=192.0.2.10", "nfs.exportPath=/exports/example")
RENDERS = 0


def render(values=(), release="nfs", namespace="examples", reject=False):
    global RENDERS
    RENDERS += 1
    args = ["helm", "template", release, str(CHART), "--namespace", namespace,
            "--kube-version", "1.33.0"]
    for value in (*NFS, *values):
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
    assert dep["metadata"]["name"] == "nfs"
    assert dep["spec"]["replicas"] == 1
    assert dep["spec"]["strategy"]["type"] == "Recreate"
    spec = pod(docs)
    assert not spec.get("initContainers")
    assert [c["name"] for c in spec["containers"]] == ["application"]
    assert spec["serviceAccountName"] == "nfs-sa"
    assert spec["automountServiceAccountToken"] is False
    assert next(d for d in docs if d["kind"] == "ServiceAccount")["metadata"]["name"] == spec["serviceAccountName"]
    assert {d["kind"] for d in docs} == {"Deployment", "ServiceAccount", "ConfigMap"}
    assert all("nfs" not in v and "persistentVolumeClaim" not in v for v in spec["volumes"])
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert values["images"]["storageHelper"] == "registry.redhat.io/openshift-sandboxed-containers/osc-storage-helper:1.13.1"
    assert set(values["images"]) == {"storageHelper"}
    assert set(values["resources"]) == {"application"}
    assert "storage" not in values and "keyDelivery" not in values
    templates = "\n".join(p.read_text() for p in (CHART / "templates").iterdir())
    for unused in ("eq .Chart.Name", "sample.memoryBytes", "sample.cpuMilli", "sample.decodeSegment"):
        assert unused not in templates, unused
    scripts = {p.name: p.read_text() for p in (CHART / "scripts").glob("*.sh")}
    assert all("SAMPLE_KIND" not in text and "mount.expired" not in text for text in scripts.values())
    assert 'mount -t nfs -o "$NFS_OPTIONS" "$EXPECTED_SOURCE"' in scripts["mount-storage.sh"]
    assert "mount_source_mismatch" in scripts["mount-storage.sh"]
    assert '"${info% *}" = "$EXPECTED_SOURCE"' in scripts["storage-access.sh"]
    for guard in ("cd -P", "set -C", "readback_failed", "content_mismatch", "storage_view_changed"):
        assert guard in scripts["prose-file.sh"], guard
    main = scripts["main.sh"]
    assert main.index("--prepare") < main.index("prose-file.sh") < main.index("application.ready.new")
    assert 'timeout -k 1 5 umount "$DATA_DIR"' in main
    assert "--fingerprint" in scripts["readiness.sh"] and "cmp -s" in scripts["readiness.sh"]
    assert "helm.sh/hook" not in templates
    env = {e["name"]: e["value"] for e in spec["containers"][0]["env"]}
    assert env["EXPECTED_SOURCE"] == "192.0.2.10:/exports/example"
    ipv6 = pod(render(["nfs.server=2001:db8::10", "nfs.exportPath=/"]))
    env = {e["name"]: e["value"] for e in ipv6["containers"][0]["env"]}
    assert env["EXPECTED_SOURCE"] == "[2001:db8::10]:/"
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
    spec = pod(render(["images.storageHelper=mirror.example.test/helper:1.13.1", "imagePullSecrets[0].name=pull-ref",
                       "imagePullPolicy=Never", "runtimeClassName=custom-kata", "startup.timeoutSeconds=120",
                       "resources.application.requests.cpu=250m", "nfs.options={vers=4.1,hard}"]))
    assert spec["containers"][0]["image"] == "mirror.example.test/helper:1.13.1"
    assert spec["runtimeClassName"] == "custom-kata" and spec["imagePullSecrets"] == [{"name": "pull-ref"}]
    assert spec["containers"][0]["imagePullPolicy"] == "Never"
    assert spec["containers"][0]["resources"]["requests"]["cpu"] == "250m"
    assert {e["name"]: e["value"] for e in spec["containers"][0]["env"]}["NFS_OPTIONS"] == "vers=4.1,hard"
    privileged = render(["security.sccBinding.create=true", "security.sccBinding.name=test-scc"])
    role = next(d for d in privileged if d["kind"] == "Role")
    binding = next(d for d in privileged if d["kind"] == "RoleBinding")
    assert role["rules"][0]["resourceNames"] == ["test-scc"] and role["rules"][0]["verbs"] == ["use"]
    assert binding["subjects"] == [{"kind": "ServiceAccount", "name": "nfs-sa", "namespace": "examples"}]
    for invalid in ("nfs.server=", "nfs.server=server;bad", "nfs.exportPath=", "nfs.exportPath=relative",
                    "nfs.options[0]=bad;option", "storage.size=1Gi", "keyDelivery.mode=curl", "images.utility=example:1",
                    "startup.timeoutSeconds=0", "images.storageHelper=mirror.example.test/helper:latest", "unexpected=true"):
        render([invalid], reject=True)
    identities = []
    for name, namespace in (("nfs", "examples"), ("nfs-two", "examples"), ("nfs", "another"), ("a" * 53, "examples")):
        rendered = render(release=name, namespace=namespace)
        dep = deployment(rendered)
        assert all(len(d["metadata"]["name"]) <= 63 for d in rendered)
        selectors = dep["spec"]["selector"]["matchLabels"]
        assert all(dep["spec"]["template"]["metadata"]["labels"][k] == v for k, v in selectors.items())
        env = {e["name"]: e["value"] for e in pod(rendered)["containers"][0]["env"]}
        identities.append(env["FILE_NAME"])
    assert len(set(identities)) == 4
    assert deployment(render(release="a.b"))["metadata"]["name"] == "a.b"
    assert pod(render(release="default"))["serviceAccountName"] == "default-sa"
    metadata = yaml.safe_load((CHART / "Chart.yaml").read_text())
    assert metadata["version"] == "0.2.0" and metadata["appVersion"] == "1.13.1"
    assert metadata["kubeVersion"] == ">=1.33.0-0" and not metadata.get("dependencies")
    assert set(next(d for d in docs if d["kind"] == "ConfigMap")["data"]) == set(scripts)
    with tempfile.TemporaryDirectory(prefix="nfs-static-") as scratch:
        subprocess.run(["helm", "package", str(CHART), "--destination", scratch], capture_output=True, check=True)
        package = next(Path(scratch).glob("*.tgz"))
        with tarfile.open(package) as archive:
            names = archive.getnames()
            assert all("/tests/" not in name and not name.endswith(".py") for name in names)
            assert sum("/scripts/" in name for name in names) == len(scripts)
        args = ["helm", "template", "nfs", str(package), "--namespace", "examples", "--kube-version", "1.33.0"]
        for value in NFS:
            args += ["--set", value]
        result = subprocess.run(args, capture_output=True, text=True, check=True)
        assert [d for d in yaml.safe_load_all(result.stdout) if d] == docs
    print(f"nfs: {RENDERS} static renders/rejections, safety-source and standalone-package checks passed")


if __name__ == "__main__":
    check()
