import importlib.util
import pytest
from conftest import CHART


def support():
    spec = importlib.util.spec_from_file_location("collection_support", CHART / "tests/live_support.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def cohort():
    records = []
    for chart, release in [("block-storage-plain", "plain"), ("block-storage-encrypted", "encrypted"), ("nfs-direct", "direct"), ("nfs-direct", "other")]:
        labels = {"app.kubernetes.io/name": chart, "app.kubernetes.io/instance": release}
        env = [{"name": "DATA_DIR", "value": "/mnt/storage"}, {"name": "FILE_NAME", "value": release + ".txt"}]
        template = {"metadata": {"annotations": {"coco.io/initdata-configmap": "debug-initdata"}},
                    "spec": {"containers": [{"name": "application", "image": "mirror.test/helper:1.13.1", "env": env}]}}
        deployment = {"kind": "Deployment", "metadata": {"name": release, "namespace": "samples", "uid": release,
                      "annotations": {"meta.helm.sh/release-name": release, "meta.helm.sh/release-namespace": "samples"}},
                      "spec": {"selector": {"matchLabels": labels}, "template": template}}
        pod = {"metadata": {"labels": labels.copy(), "annotations": {"io.katacontainers.config.hypervisor.cc_init_data": "synthetic"}},
               "spec": template["spec"], "status": {"conditions": [{"type": "Ready", "status": "True"}]}}
        records.append({"chart": chart, "release": release, "namespace": "samples", "deployment": deployment,
                        "objects": [deployment], "pods": [pod], "expected_initdata": "synthetic"})
    return records


def test_collection_ready_isolated_and_mirrored():
    support().validate_cohort(cohort(), mirror="mirror.test", initdata_mode="configMap")


@pytest.mark.parametrize("problem", ["mirror", "file", "selector", "not-ready", "initdata"])
def test_collection_rejects_wrong_members(problem):
    records = cohort()
    if problem == "mirror": records[0]["pods"][0]["spec"]["containers"][0]["image"] = "registry.redhat.io/helper:1.13.1"
    elif problem == "file": records[1]["deployment"]["spec"]["template"]["spec"]["containers"][0]["env"][1]["value"] = "plain.txt"
    elif problem == "selector": records[0]["pods"][0]["metadata"]["labels"] = records[1]["deployment"]["spec"]["selector"]["matchLabels"].copy()
    elif problem == "not-ready": records[0]["pods"][0]["status"]["conditions"][0]["status"] = "False"
    else: records[0]["pods"][0]["metadata"]["annotations"]["io.katacontainers.config.hypervisor.cc_init_data"] = "other"
    with pytest.raises(RuntimeError): support().validate_cohort(records, mirror="mirror.test", initdata_mode="configMap")


def test_remaining_releases_verify_after_removed_member():
    records = cohort()
    records[-1].update({"removed": True, "objects": [], "pods": []})
    support().validate_cohort(records, mirror="mirror.test", initdata_mode="configMap")
