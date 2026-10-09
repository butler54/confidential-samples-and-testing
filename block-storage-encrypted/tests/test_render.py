import pytest
import base64
import json
from conftest import deployment, render


def envelope(resource="default/kbsres1/key3"):
    # Metadata transport fixture only; signature is deliberately fake, not a live token.
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip("=")
    return "sealed." + encode({"alg": "ES256", "kid": "storage-signing"}) + "." + encode({
        "type": "vault", "version": "0.1.0", "provider": "kbs", "name": "kbs:///" + resource,
        "provider_settings": {}, "annotations": {}}) + ".c3ludGhldGlj"


def test_curl_topology():
    pod = deployment(render())["spec"]["template"]["spec"]
    assert pod["shareProcessNamespace"]
    assert [c["name"] for c in pod["initContainers"]] == ["fetch-key", "storage-helper"]
    assert pod["initContainers"][1]["restartPolicy"] == "Always"
    assert pod["volumes"][1]["emptyDir"]["medium"] == "Memory"
    assert "volumeDevices" not in pod["containers"][0]
    assert "lifecycle" not in pod["containers"][0]


@pytest.mark.parametrize("mode", ["sealed", "insecureSecret"])
def test_secret_modes(mode):
    field = "existingSecret" if mode == "sealed" else None
    values = {"keyDelivery": {"mode": mode}}
    values["keyDelivery"][mode] = {field: {"name": "operator-secret"}} if field else {"name": "operator-secret"}
    objects = render(values)
    pod = deployment(objects)["spec"]["template"]["spec"]
    assert len(pod["initContainers"]) == 1
    secret_env = next(e for e in pod["initContainers"][0]["env"] if e["name"] == "PASS")
    assert secret_env["valueFrom"]["secretKeyRef"]["name"] == "operator-secret"
    assert not any(item["kind"] == "Secret" for item in objects)


@pytest.mark.parametrize("values", [
    {"keyDelivery": {"mode": "invalid"}},
    {"keyDelivery": {"mode": "sealed"}},
    {"keyDelivery": {"mode": "insecureSecret"}},
    {"keyDelivery": {"mode": "curl", "insecureSecret": {"name": "bad"}}},
    {"keyDelivery": {"mode": "sealed", "sealed": {"envelope": "plaintext"}}},
    {"keyDelivery": {"mode": "sealed", "sealed": {"envelope": "sealed.a.b.c", "existingSecret": {"name": "both"}}}},
    {"keyDelivery": {"kbs": {"resourcePath": "../../other"}}},
    {"keyDelivery": {"plaintext": "not-supported"}},
])
def test_key_source_validation(values):
    render(values, success=False)


def test_owned_envelope():
    token = envelope()
    secret = next(x for x in render({"keyDelivery": {"mode": "sealed", "sealed": {"envelope": token}}}) if x["kind"] == "Secret")
    assert secret["stringData"]["envelope"] == token


def test_owned_envelope_cannot_select_another_resource():
    render({"keyDelivery": {"mode": "sealed", "sealed": {"envelope": envelope("default/other/key")}}}, success=False)
