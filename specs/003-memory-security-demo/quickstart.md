# Quickstart: Static Validation Only

The runners are static-only. Nothing here installs a release, contacts a cluster or registry, executes walkthrough commands, or pulls images. Run from a source checkout; chart packages intentionally exclude development checks (`.helmignore` `tests/`).

## Prerequisites

- Helm 3.22.0, Python 3.12 with chart-local pinned parser requirements, ShellCheck, POSIX shell.
- Run from repository root. No kubeconfig, cluster, registry access, route, or Trustee instance needed.
- See [values](contracts/values.md) and [validation boundaries](contracts/runtime-and-validation.md).

Install developer tools (all charts share pins with siblings):

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r memory-security/tests/requirements.txt
```

Install Helm 3.22.0 separately if absent. These are developer tools, not workload dependencies.

## 1. Validate each chart independently

```sh
sh memory-security/tests/run.sh   # passes --set route.host=demo.apps.example.test internally for lint/render
sh kbs-client/tests/run.sh
```

## 2. Full render spot-check

```sh
helm template full ./memory-security \
  --set route.host=full-memory-security-tests.apps.example.test
```

Expected shape (per contract — this is the complete demo; there is no opt-in flag): endpoint Deployment/Service/Route with edge TLS + `Allow`, tier pods `full-standard|full-kata|full-coco`, pair pods `full-fetch-https|full-fetch-http`, exactly one `http://` command (in `full-fetch-http`).

## 3. What success looks like

- `helm lint --strict` reports 0 failures per chart.
- `shellcheck` and `sh -n` pass on all shipped scripts.
- CI matrix `static` goes green for all five charts in `.github/workflows/validate-examples.yml`.

## 4. What is deliberately not here

Every live step (pod installs on a cluster, node debug, dumps, captures, kbs-client runs) is in `memory-security/README.md` and `kbs-client/README.md` for a human to execute manually — see the validation-boundaries contract for why no automation exists.
