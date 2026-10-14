#!/bin/sh
# Static-only validation: Helm render + lint + python byte-compile + catalog
# contract check. Never a live cluster.
set -eu
chart=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
command -v helm >/dev/null
command -v shellcheck >/dev/null
command -v python3 >/dev/null
# The runner passes per-case values via a generated file (values-<case>.yaml);
# lint does the same so string-typed values (command, paramsJson) stay strings.
VALUES_FILE=$(mktemp)
trap 'rm -f "$VALUES_FILE"' EXIT
cat >"$VALUES_FILE" <<'EOF'
case:
  slug: hpl-plain-single
  runtimeClassName: ""
  gpuResource: nvidia.com/gpu
  gpuCount: 1
node:
  name: static.example.test
pod:
  cpu: "8000m"
  mem: "32768Mi"
benchmark:
  id: hpl
  command: "cd /workspace/hpl-linux-x86_64 && ./hpl.sh --n 92160 --nb 384 --nprow 1 --npcol 1"
  paramsJson: '{"n": 92160, "nb": 384, "p": 1, "q": 1}'
images:
  workload: nvcr.io/nvidia/hpc-benchmarks:26.02.01
namespace: default
runTag: static-lint
coco:
  skipInitdata: true
EOF
helm lint "$chart" --strict --kube-version 1.33.0 -f "$VALUES_FILE"
shellcheck -x "$chart/tests/run.sh"
sh -n "$chart/tests/run.sh"
python3 -m py_compile "$chart/tools/bench.py" "$chart/tools/catalog.py"
python3 -c "import tomllib,sys; tomllib.load(open(sys.argv[1],'rb'))" "$chart/tools/pyproject.toml"

# Catalog contract (FR-012/SC-004, quickstart Scenario 5, static form):
# validated through the runner's own loader (tools/catalog.py), which only
# needs stdlib + PyYAML (tests/requirements.txt).
TOOLS="$chart/tools"
CATALOG_CHECK="$(python3 - "$TOOLS" <<'PYEOF'
import sys, tempfile, pathlib
sys.path.insert(0, sys.argv[1])
import catalog

# 1. Real catalog loads and validates; both first-release ids present.
cat = catalog.load_catalog()
assert "hpl" in cat and "hpl-mxp" in cat, sorted(cat)

# 2. Malformed definitions are rejected with actionable errors (contract
#    obligations: parser + verification are mandatory).
try:
    catalog.validate_definition({"id": "broken"})
    raise SystemExit("FAIL: malformed definition accepted")
except catalog.DefinitionValidationError:
    pass

# 3. Discovery guarantee: a NEW yaml file in a catalog directory is a NEW
#    selectable benchmark — zero changes to existing definitions (SC-004).
with tempfile.TemporaryDirectory() as tmp:
    tmpdir = pathlib.Path(tmp)
    placeholder = tmpdir / "placeholder.yaml"
    placeholder.write_text(
        "id: placeholder\n"
        "precision: fp64\n"
        "version: \"0\"\n"
        "docs_ref: docs/benchmark-selection.md\n"
        "parameter_inputs: {memory_fill: 0.1, default_nb: 128, process_grid: square-ish}\n"
        "command_template: 'run.sh --n {n} --nb {nb} --nprow {p} --npcol {q}'\n"
        "parser:\n"
        "  metric: {pattern: 'Gflops:\\\\s+([0-9.eE+-]+)', group: 1}\n"
        "  verification: {pattern: '(PASSED|FAILED)', group: 1, pass_value: PASSED}\n",
        encoding="utf-8")
    discovered = catalog.load_catalog(tmpdir)
    assert "placeholder" in discovered, sorted(discovered)
    assert catalog.load_catalog() == cat  # real catalog untouched

# 4. Parameter math + verification-gated parsing stay sane.
params = catalog.compute_params(cat["hpl"], 1, 81920)
assert params["n"] > 0 and params["nb"] == 384 and (params["p"], params["q"]) == (1, 1)
params8 = catalog.compute_params(cat["hpl"], 8, 81920)
assert params8["p"] * params8["q"] == 8 and params8["n"] > params["n"]
sample = ("T/V                N    NB     P     Q               Time                 Gflops\n"
          "--------------------------------------------------------------------------------\n"
          "W11C2C2        92160   384     1     1             123.45            5.000e+01\n"
          "||Ax-b||_1/(N*(||A||_1*||x||_1+||b||_1)) =        0.0000e+00 ...... PASSED\n")
metric, verdict = catalog.parse_output(cat["hpl"], sample)
assert metric == 50.0 and verdict == "PASSED", (metric, verdict)
metric, verdict = catalog.parse_output(cat["hpl"], sample.replace("PASSED", "FAILED"))
assert verdict == "FAILED"
print("catalog-contract OK: load, reject-malformed, placeholder-discovery, params, parse")
PYEOF
)"
echo "$CATALOG_CHECK"

# Constitution v2.0.0 IV: this repository defines/builds no containers.
if find "$chart" -iname 'Containerfile' -o -iname 'Dockerfile' | grep -q .; then
  echo "FAIL: container definition found in $chart" >&2
  exit 1
fi
