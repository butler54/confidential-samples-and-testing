"""Chart-local deadline, ownership and preservation helpers."""
from __future__ import annotations

import hashlib
import json
import time


class Deadline:
    def __init__(self, seconds, *, clock=time.monotonic, sleep=time.sleep):
        self.clock = clock
        self.sleep = sleep
        self.end = clock() + seconds

    def remaining(self):
        remaining = self.end - self.clock()
        if remaining <= 0:
            raise RuntimeError("Cleanup deadline expired; no finalizer or policy workaround attempted")
        return remaining

    def wait(self, condition):
        while True:
            self.remaining()
            if condition():
                return
            self.sleep(min(2, self.remaining()))


def poll_backend(run, command, deadline):
    def absent():
        result = run(command, allow_failure=True, timeout=deadline.remaining())
        if result.returncode == 0:
            return True
        if result.returncode == 3:  # Explicit adapter contract: asset still present.
            return False
        raise RuntimeError("Backend checker failed; absence was not proven")
    deadline.wait(absent)


def helm_owned(obj, release, namespace):
    metadata = obj.get("metadata", {})
    annotations = metadata.get("annotations", {})
    return (metadata.get("namespace") == namespace
            and annotations.get("meta.helm.sh/release-name") == release
            and annotations.get("meta.helm.sh/release-namespace") == namespace)


def identity(obj):
    m = obj["metadata"]
    return obj["kind"], m.get("namespace"), m["name"], m["uid"]


def controller_owned(obj, owner_uids):
    return any(ref.get("controller") and ref.get("uid") in owner_uids
               for ref in obj.get("metadata", {}).get("ownerReferences", []))


def stable_fingerprint(obj):
    # Keep actual protected content/identity private. Ignore incidental controller status.
    stable = {key: obj[key] for key in ["spec", "data", "binaryData", "type", "immutable"] if key in obj}
    stable["uid"] = obj["metadata"]["uid"]
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def referenced_resources(spec, annotations):
    result = set()
    if annotations.get("coco.io/initdata-configmap"):
        result.add(("ConfigMap", annotations["coco.io/initdata-configmap"]))
    result.add(("ServiceAccount", spec["serviceAccountName"]))
    for ref in spec.get("imagePullSecrets", []):
        result.add(("Secret", ref["name"]))
    for volume in spec.get("volumes", []):
        if "configMap" in volume:
            result.add(("ConfigMap", volume["configMap"]["name"]))
        if "secret" in volume:
            result.add(("Secret", volume["secret"]["secretName"]))
    for container in spec.get("initContainers", []) + spec.get("containers", []):
        for env in container.get("env", []):
            source = env.get("valueFrom", {})
            if "secretKeyRef" in source:
                result.add(("Secret", source["secretKeyRef"]["name"]))
            if "configMapKeyRef" in source:
                result.add(("ConfigMap", source["configMapKeyRef"]["name"]))
    return result


def validate_cohort(records, *, mirror=None, initdata_mode=None):
    """Read-only checks for explicitly supplied member snapshots, not auto-discovery."""
    kinds = {record["chart"] for record in records}
    if len(records) < 4 or kinds != {"block-storage-plain", "block-storage-encrypted", "nfs-direct"}:
        raise RuntimeError("Collection requires all three charts plus another release")
    resources, files = set(), set()
    active = [r for r in records if not r.get("removed")]
    for record in records:
        owned = [o for o in record["objects"] if helm_owned(o, record["release"], record["namespace"])]
        if record.get("removed"):
            if owned or record["pods"]:
                raise RuntimeError("Removed member still has owned objects or selected pods")
            continue
        deployment = record["deployment"]
        selector = deployment["spec"]["selector"]["matchLabels"]
        spec = deployment["spec"]["template"]["spec"]
        env = {e["name"]: e.get("value") for e in spec["containers"][0]["env"]}
        file_identity = (env["DATA_DIR"], env["FILE_NAME"])
        if file_identity in files:
            raise RuntimeError("Demonstration file identity overlaps another release")
        files.add(file_identity)
        for obj in owned:
            key = identity(obj)[:3]
            if key in resources:
                raise RuntimeError("Owned resource identity overlaps another member")
            resources.add(key)
        claim_names = {o["metadata"]["name"] for o in owned if o["kind"] == "PersistentVolumeClaim"}
        for volume in spec.get("volumes", []):
            if "persistentVolumeClaim" in volume and volume["persistentVolumeClaim"]["claimName"] not in claim_names:
                raise RuntimeError("Workload references a claim not owned by this release")
        for pod in record["pods"]:
            labels = pod["metadata"].get("labels", {})
            if not all(labels.get(k) == v for k, v in selector.items()):
                raise RuntimeError("Selected pod does not match its immutable selector")
            for other in active:
                if other is record:
                    continue
                other_selector = other["deployment"]["spec"]["selector"]["matchLabels"]
                if all(labels.get(k) == v for k, v in other_selector.items()):
                    raise RuntimeError("Pod is cross-selected by another member")
            if not any(c.get("type") == "Ready" and c.get("status") == "True" for c in pod.get("status", {}).get("conditions", [])):
                raise RuntimeError("Remaining member is not Ready")
            if mirror:
                for c in pod["spec"].get("initContainers", []) + pod["spec"]["containers"]:
                    if not c["image"].startswith(mirror.rstrip("/") + "/"):
                        raise RuntimeError("Consumed admitted image is outside the expected mirror")
            metadata = pod["metadata"]
            selected = deployment["spec"]["template"]["metadata"].get("annotations", {})
            if initdata_mode == "inline":
                if metadata.get("annotations", {}).get("io.katacontainers.config.hypervisor.cc_init_data") != selected.get("io.katacontainers.config.hypervisor.cc_init_data"):
                    raise RuntimeError("Inline initdata was not preserved")
            elif initdata_mode == "configMap":
                expected = record.get("expected_initdata")
                if not expected or metadata.get("annotations", {}).get("io.katacontainers.config.hypervisor.cc_init_data") != expected:
                    raise RuntimeError("Named initdata was not injected as expected")
            elif initdata_mode == "clusterDefault":
                if selected.get("coco.io/initdata-configmap") or selected.get("io.katacontainers.config.hypervisor.cc_init_data") or metadata.get("labels", {}).get("coco.io/skip-initdata") != "true":
                    raise RuntimeError("Cluster-default selection did not opt out of pattern injection")
        if not record["pods"]:
            raise RuntimeError("Active member has no observed pod")
