"""Static chart assertions: only Helm render commands, never workload shell."""
from pathlib import Path
import subprocess
import yaml

CHART = Path(__file__).resolve().parents[1]
HOST = "route.host=static.apps.example.test"
RENDERS = 0


def render(values=(), release="demo", namespace="examples", reject=False, base=(HOST,)):
    global RENDERS
    RENDERS += 1
    args = ["helm", "template", release, str(CHART), "--namespace", namespace,
            "--kube-version", "1.33.0"]
    for value in (*base, *values):
        args += ["--set", value]
    result = subprocess.run(args, capture_output=True, text=True, check=False)
    if reject:
        assert result.returncode, "invalid values unexpectedly rendered"
        return []
    assert result.returncode == 0, f"Helm render failed: {result.stderr}"
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def by_name(docs, kind, name):
    return next(doc for doc in docs if doc["kind"] == kind
                and doc["metadata"]["name"] == name)


def commands(doc):
    spec = doc["spec"] if doc["kind"] == "Pod" else None
    out = []
    for group in ("initContainers", "containers"):
        for container in spec.get(group, []):
            out.extend(str(part) for part in (container.get("command") or []) + list(container.get("args") or []))
    return out


def check():
    docs = render(release="demo", namespace="examples")

    # Endpoint objects.
    config = by_name(docs, "ConfigMap", "demo-magic-string")
    assert config["data"]["magic.txt"].strip() == "MyMagicKeyIsABanana"
    dep = by_name(docs, "Deployment", "demo-magic")
    svc = by_name(docs, "Service", "demo-magic")
    assert dep["spec"]["selector"]["matchLabels"] == svc["spec"]["selector"]
    server = dep["spec"]["template"]["spec"]["containers"][0]
    assert server["image"].startswith("registry.access.redhat.com/ubi9/httpd-24:")
    route = by_name(docs, "Route", "demo-magic")
    assert route["spec"]["host"] == "static.apps.example.test"
    assert route["spec"]["tls"]["termination"] == "edge"
    assert route["spec"]["tls"]["insecureEdgeTerminationPolicy"] == "Allow"

    # US1 tier pods, graduated trust.
    standard = by_name(docs, "Pod", "demo-standard")
    kata = by_name(docs, "Pod", "demo-kata")
    coco = by_name(docs, "Pod", "demo-coco")
    assert "runtimeClassName" not in standard["spec"]
    assert kata["spec"]["runtimeClassName"] == "kata"
    assert coco["spec"]["runtimeClassName"] == "kata-cc"
    for tier in (kata, coco):
        annotations = tier["metadata"]["annotations"]
        assert annotations["io.katacontainers.config.hypervisor.default_vcpus"] == "2"
        assert annotations["io.katacontainers.config.hypervisor.default_memory"] == "4096"
    assert coco["metadata"]["annotations"]["coco.io/initdata-configmap"] == "debug-initdata"
    assert "demo.tier" in kata["metadata"]["labels"]

    # Every tier fetched with TLS from the cluster-internal endpoint.
    for pod in (standard, kata, coco):
        cmds = " ".join(commands(pod))
        assert "https://static.apps.example.test/magic.txt" in cmds
        assert "emptyDir" not in cmds
        assert pod["spec"]["volumes"][0]["emptyDir"]["medium"] == "Memory"

    # US2 transport pair (chart-inherent — there is no flag): exactly one
    # plaintext fetcher ever exists and everything else uses TLS.
    https_pod = by_name(docs, "Pod", "demo-fetch-https")
    http_pod = by_name(docs, "Pod", "demo-fetch-http")
    assert https_pod["spec"]["runtimeClassName"] == "kata-cc"
    assert http_pod["spec"]["runtimeClassName"] == "kata-cc"
    https_cmds = " ".join(commands(https_pod))
    http_cmds = " ".join(commands(http_pod))
    assert "curl -ks https://static.apps.example.test/magic.txt" in https_cmds
    assert "curl -s http://static.apps.example.test/magic.txt" in http_cmds
    for tier in (standard, kata, coco, https_pod):
        assert "http://" not in " ".join(commands(tier))
    all_commands = " ".join(part for doc in docs if doc["kind"] == "Pod"
                            for part in commands(doc))
    assert all_commands.count("http://") == 1
    assert route["metadata"]["annotations"]["memory-security.dev/plaintext-http"] == "demonstration-only"
    assert http_pod["metadata"]["annotations"]["memory-security.dev/plaintext-http"] == "demonstration-only"
    for template in ("route-magic-server.yaml", "pod-fetch-http.yaml"):
        assert "DEMONSTRATION ONLY" in (CHART / "templates" / template).read_text(), template
    assert "DEMONSTRATION ONLY" in (CHART / "README.md").read_text()
    assert "DEMONSTRATION ONLY" in (CHART / "templates" / "NOTES.txt").read_text()

    # Initdata precedence renders.
    encoded = by_name(render(("initdata.encoded=eA==",)),
                      "Pod", "demo-coco")["metadata"]["annotations"]
    assert encoded["io.katacontainers.config.hypervisor.init_data"] == "eA=="
    assert "coco.io/initdata-configmap" not in encoded
    empty = by_name(render(("initdata.configMapName=",)),
                    "Pod", "demo-coco")["metadata"]["annotations"]
    assert "coco.io/initdata-configmap" not in empty
    assert "io.katacontainers.config.hypervisor.init_data" not in empty
    custom = by_name(render(("initdata.configMapName=custom-initdata",)),
                     "Pod", "demo-coco")["metadata"]["annotations"]
    assert custom["coco.io/initdata-configmap"] == "custom-initdata"

    # Magic string content is confined to the ConfigMap.
    rendered = subprocess.run(
        ["helm", "template", "demo", str(CHART), "--namespace", "examples",
         "--kube-version", "1.33.0", "--set", HOST],
        capture_output=True, text=True, check=False)
    assert rendered.returncode == 0
    assert rendered.stdout.count("MyMagicKeyIsABanana") == 1

    # route.host is required and rejected when empty or malformed.
    render(base=(), reject=True)
    render(base=("route.host=localhost",), reject=True)  # not a FQDN (no dot)
    render(base=("route.host=Demo.apps.example.test",), reject=True)  # uppercase

    # Values discipline: pinned images, no personal-registry leakage.
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    assert values["images"]["demo"] == "registry.access.redhat.com/ubi9/ubi:9.6"
    for image in values["images"].values():
        assert image.startswith("registry.access.redhat.com/") and ":latest" not in image
    assert "transport" not in values  # plaintext HTTP is chart-inherent, not a flag
    chart_text = "".join(p.read_text() for p in CHART.rglob("*")
                         if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts)
    bad_reference = "rh-ee-c" + "hbutler"  # personal-registry snapshot prefix
    assert bad_reference not in chart_text


check()
print(f"memory-security: US1+US2 static checks passed across {RENDERS} Helm renders")
