import subprocess
import tarfile

from conftest import CHART, deployment, render


def test_similar_long_names_keep_identity():
    first = render(release="a" * 52 + "b")
    second = render(release="a" * 52 + "c")
    names1 = {(x["kind"], x["metadata"]["name"]) for x in first}
    names2 = {(x["kind"], x["metadata"]["name"]) for x in second}
    assert not names1.intersection(names2)
    assert all(len(x["metadata"]["name"]) <= 63 for x in first + second)
    assert deployment(first)["spec"]["selector"] != deployment(second)["spec"]["selector"]


def test_namespace_identity_and_filename():
    first = deployment(render(namespace="one"))["spec"]["template"]
    second = deployment(render(namespace="two"))["spec"]["template"]
    def filename(pod):
        return next(e["value"] for e in pod["spec"]["containers"][0]["env"] if e["name"] == "FILE_NAME")
    assert filename(first) != filename(second)
    assert filename(first) == filename(deployment(render(namespace="one"))["spec"]["template"])


def test_standalone_package_contains_only_own_runtime(tmp_path):
    subprocess.run(["helm", "package", str(CHART), "--destination", str(tmp_path)], check=True, capture_output=True)
    with tarfile.open(next(tmp_path.glob("*.tgz"))) as package:
        names = package.getnames()
    assert all(x.startswith(CHART.name + "/") for x in names)
    assert any("/scripts/main.sh" in x for x in names)
    assert not any("/tests/" in x or "staging/" in x or "private" in x for x in names)
