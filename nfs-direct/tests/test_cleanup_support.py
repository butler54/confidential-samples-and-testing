import importlib.util
from pathlib import Path

import pytest
import json
import subprocess
import sys

from conftest import CHART


def support():
    spec = importlib.util.spec_from_file_location("cleanup_support", CHART / "tests/live_support.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_backend_pending_retried_under_one_deadline():
    module = support()
    now = [0.0]
    deadline = module.Deadline(20, clock=lambda: now[0], sleep=lambda t: now.__setitem__(0, now[0] + t))
    calls = []
    def run(command, **kwargs):
        calls.append(kwargs["timeout"])
        return type("Result", (), {"returncode": 3 if len(calls) < 3 else 0})()
    module.poll_backend(run, ["/checker", "driver", "handle"], deadline)
    assert calls == [20, 18, 16]


def test_backend_error_is_not_pending_or_success():
    module = support()
    with pytest.raises(RuntimeError, match="Backend checker failed"):
        module.poll_backend(lambda *a, **k: type("Result", (), {"returncode": 1})(), ["checker"], module.Deadline(20))


def test_backend_pending_cannot_outlive_deadline():
    module = support()
    now = [0.0]
    deadline = module.Deadline(3, clock=lambda: now[0], sleep=lambda t: now.__setitem__(0, now[0] + t))
    with pytest.raises(RuntimeError, match="deadline expired"):
        module.poll_backend(lambda *a, **k: type("Result", (), {"returncode": 3})(), ["checker"], deadline)
    assert now[0] == 3


def test_labels_alone_do_not_prove_ownership():
    module = support()
    external = {"kind": "Secret", "metadata": {"name": "operator", "uid": "external", "namespace": "samples",
                "labels": {"app.kubernetes.io/instance": "test"}}}
    owned = {"kind": "ConfigMap", "metadata": {"name": "scripts", "uid": "owned", "namespace": "samples",
             "annotations": {"meta.helm.sh/release-name": "test", "meta.helm.sh/release-namespace": "samples"}}}
    assert not module.helm_owned(external, "test", "samples")
    assert module.helm_owned(owned, "test", "samples")


def test_external_fingerprint_ignores_status_not_data():
    module = support()
    first = {"metadata": {"uid": "same", "resourceVersion": "1"}, "data": {"public": "one"}}
    second = {"metadata": {"uid": "same", "resourceVersion": "2"}, "data": {"public": "one"}, "status": {"ready": True}}
    assert module.stable_fingerprint(first) == module.stable_fingerprint(second)
    second["data"]["public"] = "changed"
    assert module.stable_fingerprint(first) != module.stable_fingerprint(second)


@pytest.mark.parametrize("external_changed,backend_error", [(False, False), (True, False), (False, True)])
def test_complete_teardown_flow_preserves_external_objects(monkeypatch, external_changed, backend_error):
    module_spec = importlib.util.spec_from_file_location("cleanup_flow", CHART / "tests/live.py")
    live = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(live)
    namespace, release = "samples", "test"
    def obj(kind, name, owned=True, **fields):
        metadata = {"name": name, "namespace": namespace, "uid": name + "-uid",
                    "labels": {"app.kubernetes.io/name": CHART.name, "app.kubernetes.io/instance": release}}
        if owned:
            metadata["annotations"] = {"meta.helm.sh/release-name": release, "meta.helm.sh/release-namespace": namespace}
        return {"kind": kind, "metadata": metadata, **fields}
    spec = {"serviceAccountName": "account", "volumes": [{"name": "scripts", "configMap": {"name": "scripts"}}],
            "containers": [{"name": "application", "env": [{"name": "DATA_DIR", "value": "/mnt/storage"}, {"name": "FILE_NAME", "value": "sample.txt"},
                           {"name": "EXTERNAL", "valueFrom": {"secretKeyRef": {"name": "operator-key", "key": "key"}}}]}]}
    deployment = obj("Deployment", "workload", spec={"template": {"metadata": {"annotations": {"coco.io/initdata-configmap": "debug-initdata"}}, "spec": spec}})
    claim = obj("PersistentVolumeClaim", "block", spec={"volumeMode": "Block", "volumeName": "pv"})
    owned_objects = [deployment, obj("ServiceAccount", "account"), obj("ConfigMap", "scripts"), claim]
    externals = {"operator-key": obj("Secret", "operator-key", False, data={"key": "synthetic"}),
                 "debug-initdata": obj("ConfigMap", "debug-initdata", False, data={"INITDATA": "synthetic"})}
    stopped = [False]
    polls, backend_calls, commands = [0], [0], []
    now = [0.0]
    support_module = support()
    live.Deadline = lambda seconds: support_module.Deadline(seconds, clock=lambda: now[0], sleep=lambda t: now.__setitem__(0, now[0] + t))
    def run(command, **kwargs):
        commands.append((command, kwargs.get("timeout")))
        code, output = 0, ""
        if command[0] == "helm":
            stopped[0] = True
        elif command[0] == sys.executable:
            backend_calls[0] += 1
            code = 1 if backend_error else (3 if backend_calls[0] == 1 else 0)
        else:
            at = command.index("get")
            kind = command[at + 1]
            name = command[at + 2] if len(command) > at + 2 and not command[at + 2].startswith("-") else None
            if kind == "deployments": value = {"items": [deployment]}
            elif kind == "pvc": value = {"items": [] if CHART.name == "nfs-direct" else [claim]}
            elif kind == "pv":
                if stopped[0]:
                    polls[0] += 1
                    return subprocess.CompletedProcess(command, 0, "pv\n" if polls[0] == 1 else "", "")
                value = {"kind": "PersistentVolume", "metadata": {"name": "pv", "uid": "pv-uid"},
                         "spec": {"persistentVolumeReclaimPolicy": "Delete", "csi": {"driver": "test-driver", "volumeHandle": "test-handle"}}}
            elif "," in kind:
                # Matching-label external objects remain after Helm teardown and must not block ownership checks.
                value = {"items": list(externals.values()) if stopped[0] else owned_objects + list(externals.values())}
            elif name in externals:
                value = json.loads(json.dumps(externals[name]))
                if stopped[0] and external_changed and name == "operator-key": value["data"]["key"] = "changed"
            else: value = next(x for x in owned_objects if x["metadata"]["name"] == name)
            output = json.dumps(value)
        return subprocess.CompletedProcess(command, code, output, "")
    monkeypatch.setattr(live.subprocess, "run", run)
    monkeypatch.setattr(sys, "argv", ["live", "uninstall", "--context", "explicit", "--namespace", namespace, "--release", release,
                                      "--confirm-destructive", "--backend-check", sys.executable, "--timeout", "120"])
    if external_changed or (backend_error and CHART.name != "nfs-direct"):
        with pytest.raises(RuntimeError): live.main()
    else:
        assert live.main() == 0
    helm_timeout = next(timeout for command, timeout in commands if command[0] == "helm")
    assert helm_timeout == 120, "Configured cleanup timeout must not be capped at 60 seconds"
    assert all(not (command[0] == "oc" and "delete" in command) for command, _ in commands)
    if CHART.name != "nfs-direct" and not backend_error:
        assert backend_calls[0] == 2 and polls[0] >= 2
