"""Static chart assertions: only Helm render commands, never workload shell."""
from pathlib import Path
import subprocess
import yaml

CHART = Path(__file__).resolve().parents[1]
RENDERS = 0


def render(values=(), release="demo", namespace="examples", reject=False):
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
    assert result.returncode == 0, f"Helm render failed: {result.stderr}"
    return [doc for doc in yaml.safe_load_all(result.stdout) if doc]


def check():
    docs = render()
    dep = next(doc for doc in docs if doc["kind"] == "Deployment")
    assert dep["metadata"]["name"] == "demo-client"
    assert {doc["kind"] for doc in docs} == {"Deployment"}  # no Service/Route/Secret
    template = dep["spec"]["template"]
    assert template["spec"]["runtimeClassName"] == "kata-cc"
    annotations = template["metadata"]["annotations"]
    assert annotations["coco.io/initdata-configmap"] == "debug-initdata"
    container = template["spec"]["containers"][0]
    assert container["image"] == "quay.io/butler54/kbs-client:0.1.0"
    assert container["command"] == ["sleep", "infinity"]
    assert "env" not in container  # KBS_ADDRESS added only when kbs.address set

    # Initdata precedence renders.
    encoded = render(("initdata.encoded=eA==",))[0]["spec"]["template"]["metadata"]["annotations"]
    assert encoded["io.katacontainers.config.hypervisor.init_data"] == "eA=="
    assert "coco.io/initdata-configmap" not in encoded
    empty = render(("initdata.configMapName=",))[0]["spec"]["template"]["metadata"]["annotations"]
    assert "coco.io/initdata-configmap" not in empty
    custom = render(("initdata.configMapName=custom-initdata",))[0]["spec"]["template"]["metadata"]["annotations"]
    assert custom["coco.io/initdata-configmap"] == "custom-initdata"

    # kbs.address maps to the optional environment variable.
    with_address = render(("kbs.address=https://kbs.example.org",))[0]
    env = with_address["spec"]["template"]["spec"]["containers"][0]["env"]
    assert {"name": "KBS_ADDRESS", "value": "https://kbs.example.org"} in env

    # Values discipline: pinned image, no personal-registry leakage.
    values = yaml.safe_load((CHART / "values.yaml").read_text())
    for image in values["images"].values():
        assert ":latest" not in image and ":" in image.rsplit("/", 1)[-1]
    assert values["runtimeClassName"] == "kata-cc"
    chart_text = "".join(p.read_text() for p in CHART.rglob("*")
                         if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts)
    bad_reference = "rh-ee-c" + "hbutler"
    assert bad_reference not in chart_text

    # Mutable-tag rejection, per contract.
    render(("images.client=quay.io/butler54/kbs-client:latest",), reject=True)
    render(("runtimeClassName=",), reject=True)


check()
print(f"kbs-client: static checks passed across {RENDERS} Helm renders")
