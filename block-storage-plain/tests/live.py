"""Opt-in, explicit-context verification. Never invoked by the offline runner."""
from __future__ import annotations

import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from live_support import Deadline, controller_owned, helm_owned, identity, poll_backend, referenced_resources, stable_fingerprint, validate_cohort

CHART = Path(__file__).resolve().parents[1].name
PROSE = "This file demonstrates persistent storage for this confidential container example.\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prerequisites", "verify", "uninstall", "collection"])
    parser.add_argument("--context", required=True, help="Explicit approved kubeconfig context")
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--scc", default="privileged", help="Existing SCC used for the sample; override for a custom SCC")
    parser.add_argument("--expect-existing", action="store_true")
    parser.add_argument("--replace-pods", action="store_true")
    parser.add_argument("--confirm-disposable", action="store_true")
    parser.add_argument("--confirm-destructive", action="store_true")
    parser.add_argument("--backend-check", type=Path,
                        help="Trusted executable: args are CSI driver and saved volume handle; exit 0 only when absent")
    parser.add_argument("--logs-only", action="store_true",
                        help="Collect startup evidence without exec; not complete mount/encryption verification")
    parser.add_argument("--chart-identity", choices=["block-storage-plain", "block-storage-encrypted", "nfs-direct"], default=CHART)
    parser.add_argument("--cohort", action="append", default=[], help="Explicit chart:release member; supply all three plus another release")
    parser.add_argument("--removed-member", help="chart:release already removed by a separately approved operation; this command never removes it")
    parser.add_argument("--expected-mirror", help="Exact registry[:port]/repository-prefix expected for every consumed pod image")
    parser.add_argument("--expected-initdata-mode", choices=["configMap", "inline", "clusterDefault"])
    parser.add_argument("--allow-existing-initial", action="store_true", help="Initial pod may have a retained file; replacements still require existing-file logs")
    parser.add_argument("--expect-failure", action="store_true", help="Observe a separately prepared negative-test release")
    parser.add_argument("--failure-window", type=int, default=30)
    parser.add_argument("--failure-reason", choices=["unlock_failed", "key_denied", "key_empty_or_invalid",
                        "content_mismatch", "create_failed", "mount_timeout", "agent_unseal_failed"])
    args = parser.parse_args()
    chart_name = args.chart_identity
    if args.action == "uninstall" and chart_name != CHART:
        parser.error("Use the owning chart's cleanup script; cross-chart uninstall is not supported")
    for name in [args.namespace, args.release]:
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", name):
            parser.error("namespace and release must be valid names, not options")
    if not 1 <= args.timeout <= 7200:
        parser.error("timeout must be between 1 and 7200 seconds")
    if args.expect_failure and (not args.failure_reason or not 5 <= args.failure_window <= 300):
        parser.error("negative verification requires --failure-reason and a 5–300 second observation window")
    if args.expect_failure and args.replace_pods:
        parser.error("negative verification does not replace pods automatically")
    if args.replace_pods and not args.confirm_disposable:
        parser.error("pod replacement requires --confirm-disposable")
    if args.action == "uninstall" and not args.confirm_destructive:
        parser.error("uninstall requires --confirm-destructive")
    if args.action == "uninstall" and CHART != "nfs-direct":
        if not args.backend_check or not args.backend_check.is_absolute() or not os.access(args.backend_check, os.X_OK):
            parser.error("block uninstall requires an absolute executable --backend-check before deleting anything")

    base = ["oc", f"--context={args.context}", f"--namespace={args.namespace}"]
    selector = f"app.kubernetes.io/name={chart_name},app.kubernetes.io/instance={args.release}"

    def call(command: list[str], *, allow_failure: bool = False, timeout: float = 60) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(command, text=True, capture_output=True, timeout=timeout, check=False)
        if result.returncode and not allow_failure:
            # Do not echo arbitrary API responses, config, or Secret-bearing manifests.
            raise RuntimeError(f"Command failed: {command[0]} (exit {result.returncode}); inspect locally")
        return result

    def get(kind: str, name: str | None = None) -> dict:
        cmd = [*base, "get", kind]
        cmd += [name] if name else ["-l", selector]
        return json.loads(call([*cmd, "-o", "json"]).stdout)

    def wait_until(condition) -> None:
        end = time.monotonic() + args.timeout
        while time.monotonic() < end:
            if condition():
                return
            time.sleep(2)
        raise RuntimeError("Verification deadline expired; no destructive workaround attempted")

    if args.action == "collection":
        members = []
        for item in args.cohort:
            kind, separator, release = item.partition(":")
            if not separator or kind not in ["block-storage-plain", "block-storage-encrypted", "nfs-direct"] or not re.fullmatch(r"[a-z0-9][a-z0-9.-]*", release):
                parser.error("cohort members must be supported chart:release names")
            if (kind, release) in members:
                parser.error("duplicate cohort member")
            members.append((kind, release))
        if len(members) < 4 or {kind for kind, _ in members} != {"block-storage-plain", "block-storage-encrypted", "nfs-direct"}:
            parser.error("collection requires all three charts plus another explicit release")
        if args.removed_member and args.removed_member not in args.cohort:
            parser.error("removed member must be explicitly present in the cohort")
        records = []
        for kind, release in members:
            member_selector = f"app.kubernetes.io/name={kind},app.kubernetes.io/instance={release}"
            def selected(resource):
                return json.loads(call([*base, "get", resource, "-l", member_selector, "-o", "json"]).stdout)["items"]
            removed = args.removed_member == f"{kind}:{release}"
            objects = selected("deployments,pvc,configmaps,secrets,serviceaccounts,roles,rolebindings")
            pods = [p for p in selected("pods") if not p["metadata"].get("deletionTimestamp")]
            deployments = [o for o in objects if o["kind"] == "Deployment"]
            if not removed and len(deployments) != 1:
                raise RuntimeError("Each active cohort member requires one observed Deployment")
            deployment = deployments[0] if deployments else None
            record = {"chart": kind, "release": release, "namespace": args.namespace,
                      "deployment": deployment, "objects": objects, "pods": pods, "removed": removed}
            if deployment:
                selected_data = deployment["spec"]["template"]["metadata"].get("annotations", {})
                if selected_data.get("coco.io/initdata-configmap"):
                    record["expected_initdata"] = get("configmap", selected_data["coco.io/initdata-configmap"]).get("data", {}).get("INITDATA")
            records.append(record)
        validate_cohort(records, mirror=args.expected_mirror, initdata_mode=args.expected_initdata_mode)
        for kind, release in members:
            if args.removed_member == f"{kind}:{release}":
                continue
            command = [sys.executable, str(Path(__file__).resolve()), "verify", "--context", args.context,
                       "--namespace", args.namespace, "--release", release, "--chart-identity", kind,
                       "--timeout", str(args.timeout), "--scc", args.scc, "--allow-existing-initial"]
            if args.replace_pods:
                command += ["--replace-pods", "--confirm-disposable"]
            call(command, timeout=args.timeout * (3 if args.replace_pods else 1) + 60)
        print("Explicit cohort isolation, admitted images/initdata and every remaining member's storage/prose verified.")
        return 0

    deployments = get("deployments")["items"]
    if len(deployments) != 1:
        raise RuntimeError("Exactly one existing Deployment of this chart/release is required")
    deployment = deployments[0]
    spec = deployment["spec"]["template"]["spec"]
    account = spec["serviceAccountName"]
    annotations = deployment["spec"]["template"]["metadata"].get("annotations", {})
    config_name = annotations.get("coco.io/initdata-configmap")
    if args.action != "uninstall":
        call([*base, "get", "runtimeclass", spec["runtimeClassName"]])
        if config_name and not get("configmap", config_name).get("data", {}).get("INITDATA"):
            raise RuntimeError("Selected same-namespace initdata ConfigMap lacks INITDATA")
        allowed = call([*base, "auth", "can-i", "use", f"securitycontextconstraints/{args.scc}",
                        f"--as=system:serviceaccount:{args.namespace}:{account}"], allow_failure=True)
        if allowed.returncode or allowed.stdout.strip() != "yes":
            raise RuntimeError("Release service account lacks expected SCC permission, or impersonation check is unauthorized")
        if chart_name == "block-storage-encrypted" and not args.expect_failure:
            helper = next(c for c in spec["initContainers"] if c["name"] == "storage-helper")
            mode = next(e["value"] for e in helper["env"] if e["name"] == "KEY_MODE")
            if mode == "sealed":
                ref = next(e["valueFrom"]["secretKeyRef"] for e in helper["env"] if e["name"] == "PASS")
                token = base64.b64decode(get("secret", ref["name"])["data"][ref["key"]], validate=True).decode("ascii")
                parts = token.split(".")
                if len(parts) != 4 or parts[0] != "sealed":
                    raise RuntimeError("Sealed mode source is not an actual CoCo token")
                payload = json.loads(base64.urlsafe_b64decode(parts[2] + "=" * (-len(parts[2]) % 4)))
                expected_resource = next(e["value"] for e in helper["env"] if e["name"] == "KBS_RESOURCE_PATH")
                if payload.get("name") != f"kbs:///{expected_resource}" or payload.get("type") != "vault":
                    raise RuntimeError("Sealed source selects a different resource; token contents not logged")

    claims = get("pvc")["items"]
    if args.action == "uninstall":
        claims = [claim for claim in claims if helm_owned(claim, args.release, args.namespace)]
    claim_ids = {(c["metadata"]["uid"], c["spec"].get("volumeName")) for c in claims}
    backend: list[tuple[str, str, str]] = []
    for claim in claims:
        if claim["spec"].get("volumeMode") != "Block" or not claim["spec"].get("volumeName"):
            raise RuntimeError("Bound Block claim required")
        pv = get("pv", claim["spec"]["volumeName"])
        if pv["spec"].get("persistentVolumeReclaimPolicy") != "Delete":
            raise RuntimeError("Selected PV does not use Delete reclamation")
        csi = pv["spec"].get("csi", {})
        backend.append((pv["metadata"]["name"], csi.get("driver", ""), csi.get("volumeHandle", "")))
    if chart_name == "nfs-direct" and (claims or any("nfs" in v for v in spec.get("volumes", []))):
        raise RuntimeError("Direct NFS must not use a persistent-volume interface")
    if chart_name != "nfs-direct" and len(claims) != 1:
        raise RuntimeError("Exactly one bound release-owned Block claim required")
    if args.action == "prerequisites":
        print("Read-only runtime/initdata/SCC/claim checks passed; guest/NFS/trust/backend behavior still requires live tests.")
        if chart_name == "block-storage-encrypted":
            print("Sealed mode requires corrected upstream initdata and verified local signing trust: coco-pattern #153.")
        return 0

    application = next(c for c in spec["containers"] if c["name"] == "application")
    env = {e["name"]: e.get("value") for e in application["env"]}
    file = f"{env['DATA_DIR']}/{env['FILE_NAME']}"
    old: set[str] = set()

    if args.expect_failure:
        observed = False
        end = time.monotonic() + args.failure_window
        while time.monotonic() < end:
            pods = get("pods")["items"]
            for pod in pods:
                if any(c["type"] == "Ready" and c["status"] == "True" for c in pod.get("status", {}).get("conditions", [])):
                    raise RuntimeError("Negative-test release became Ready")
                if args.failure_reason == "agent_unseal_failed":
                    statuses = pod.get("status", {}).get("initContainerStatuses", []) + pod.get("status", {}).get("containerStatuses", [])
                    for status in statuses:
                        message = status.get("state", {}).get("waiting", {}).get("message", "")
                        # Inspect privately; never print sealed tokens or arbitrary runtime responses.
                        observed |= bool(re.search(r"failed.*unseal|sealed.secret.*verification|sealed.*signature", message, re.I))
                else:
                    for container in ["application", "storage-helper", "fetch-key"]:
                        log = call([*base, "logs", pod["metadata"]["name"], "-c", container], allow_failure=True).stdout
                        observed |= f"reason={args.failure_reason}" in log
            time.sleep(2)
        if not observed:
            raise RuntimeError("Expected specific failure was not observed; ordinary pending startup is not proof")
        print("Specific negative outcome observed without Ready status; no key/config/storage mutation was performed.")
        return 0

    def ready_pod() -> dict | None:
        pods = [p for p in get("pods")["items"] if not p["metadata"].get("deletionTimestamp")]
        for pod in pods:
            if pod["metadata"]["uid"] in old:
                continue
            if args.logs_only and any(c.get("name") == "application" and "running" in c.get("state", {}) for c in pod.get("status", {}).get("containerStatuses", [])):
                return pod
            if any(c["type"] == "Ready" and c["status"] == "True" for c in pod.get("status", {}).get("conditions", [])):
                return pod
        return None

    if args.action == "uninstall":
        if any(not driver or not handle for _, driver, handle in backend):
            raise RuntimeError("CSI identifiers are missing; refuse deletion without verifiable backend identity")
        tracked_kinds = "deployments,replicasets,pods,pvc,configmaps,secrets,serviceaccounts,roles,rolebindings"
        inventory = get(tracked_kinds)["items"]
        owned = [obj for obj in inventory if helm_owned(obj, args.release, args.namespace)]
        if not helm_owned(deployment, args.release, args.namespace):
            raise RuntimeError("Deployment is not owned by the named Helm release; refuse teardown")
        owner_uids = {obj["metadata"]["uid"] for obj in owned}
        # Follow Deployment → ReplicaSet → Pod ownership without adopting label-only objects.
        for _ in range(2):
            for obj in inventory:
                if controller_owned(obj, owner_uids):
                    owner_uids.add(obj["metadata"]["uid"])
        owned_ids = {identity(obj) for obj in inventory if obj["metadata"]["uid"] in owner_uids}
        external = {}
        for kind, name in referenced_resources(spec, annotations):
            obj = get(kind, name)
            if obj["metadata"]["uid"] not in owner_uids:
                external[(kind, name)] = stable_fingerprint(obj)
        deadline = Deadline(args.timeout)
        call(["helm", "uninstall", args.release, f"--namespace={args.namespace}",
              f"--kube-context={args.context}", "--wait", f"--timeout={args.timeout}s"], timeout=deadline.remaining())
        def owned_gone():
            remaining = json.loads(call([*base, "get", tracked_kinds, "-l", selector, "-o", "json"],
                                       timeout=min(60, deadline.remaining())).stdout)["items"]
            return not any(helm_owned(obj, args.release, args.namespace) or identity(obj) in owned_ids
                           or controller_owned(obj, owner_uids) for obj in remaining)
        deadline.wait(owned_gone)
        for pv_name, driver, handle in backend:
            deadline.wait(lambda: call([*base, "get", "pv", pv_name, "--ignore-not-found", "-o", "name"],
                                       timeout=min(60, deadline.remaining())).stdout.strip() == "")
            assert args.backend_check is not None
            poll_backend(call, [str(args.backend_check), driver, handle], deadline)
        for (kind, name), fingerprint in external.items():
            current = json.loads(call([*base, "get", kind, name, "-o", "json"],
                                     timeout=min(60, deadline.remaining())).stdout)
            if stable_fingerprint(current) != fingerprint:
                raise RuntimeError("Referenced external resource changed or was replaced during teardown")
        print("Owned objects deleted; backend deletion confirmed where applicable. External NFS/Trustee/initdata resources were not deleted.")
        return 0

    for cycle in range(3 if args.replace_pods else 1):
        wait_until(lambda: ready_pod() is not None)
        pod = ready_pod()
        assert pod is not None
        name = pod["metadata"]["name"]
        if args.expected_mirror:
            for container in pod["spec"].get("initContainers", []) + pod["spec"]["containers"]:
                if not container["image"].startswith(args.expected_mirror.rstrip("/") + "/"):
                    raise RuntimeError("Admitted image is outside the expected mirror")
        current_claims = get("pvc")["items"]
        if {(c["metadata"]["uid"], c["spec"].get("volumeName")) for c in current_claims} != claim_ids:
            raise RuntimeError("Claim/PV identity changed during pod replacement")
        expected_initdata = annotations.get("io.katacontainers.config.hypervisor.cc_init_data")
        mode = "inline" if expected_initdata else ("configMap" if config_name else "clusterDefault")
        if args.expected_initdata_mode and args.expected_initdata_mode != mode:
            raise RuntimeError("Workload selected a different initdata mode")
        if mode == "clusterDefault" and pod["metadata"].get("labels", {}).get("coco.io/skip-initdata") != "true":
            raise RuntimeError("Cluster-default selection must skip pattern injection")
        if config_name:
            expected_initdata = get("configmap", config_name)["data"]["INITDATA"]
        if expected_initdata and pod["metadata"].get("annotations", {}).get("io.katacontainers.config.hypervisor.cc_init_data") != expected_initdata:
            raise RuntimeError("Admitted pod did not use the selected initdata")
        logs = call([*base, "logs", name, "-c", "application"]).stdout
        event = "file_existing_verified" if args.expect_existing or cycle else "file_created"
        if not cycle and args.allow_existing_initial and "event=file_existing_verified" in logs:
            event = "file_existing_verified"
        if f"event={event}" not in logs or "event=storage_accessible" not in logs:
            raise RuntimeError("Expected ordered mount/file verification events are missing")
        if logs.index("event=storage_accessible") > logs.index(f"event={event}"):
            raise RuntimeError("File outcome preceded confirmed storage access")
        if not args.logs_only:
            call([*base, "exec", name, "-c", "application", "--", "sh", "/opt/sample/storage-access.sh", "--check"])
            content = call([*base, "exec", name, "-c", "application", "--", "cat", file]).stdout
            if content != PROSE:
                raise RuntimeError("Expected public prose did not match; actual content not logged")
            if chart_name == "block-storage-encrypted":
                call([*base, "exec", name, "-c", "storage-helper", "--", "cryptsetup", "isLuks", "/dev/block-device"])
        if cycle < 2 and args.replace_pods:
            old.add(pod["metadata"]["uid"])
            call([*base, "delete", "pod", name])
    if args.logs_only:
        print("Startup log evidence collected only; independent mount/encryption verification NOT completed.")
    else:
        print("Intended mount and exact public prose verified; replacement cycles completed when requested.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.TimeoutExpired, KeyError, ValueError) as error:
        print(f"Validation failed: {error}", file=sys.stderr)
        sys.exit(1)
