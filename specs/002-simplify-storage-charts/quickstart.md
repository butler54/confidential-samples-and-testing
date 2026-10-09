# Quickstart: Static Validation Only

The implemented runners are static-only. Nothing here installs a release, accesses a cluster, executes workload shell or runs/pulls workload images. Run from a source checkout; chart packages intentionally exclude development checks.

## Prerequisites

- Helm 3.22.0, Python 3.12 with chart-local pinned static parser requirements, ShellCheck and a POSIX shell.
- Run from repository root. No kubeconfig, cluster, registry credentials, NFS export, Trustee instance or backend-deletion adapter needed.
- See [values](contracts/values.md), [validation boundaries](contracts/runtime-and-validation.md), and [data model](data-model.md).

For a source checkout, install the development tools in a local environment if needed (all three charts use the same pins):

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r block-storage-plain/tests/requirements.txt
```

Install Helm 3.22.0 separately if absent. These are developer tools, not workload dependencies.

## 1. Validate independently

```sh
sh block-storage-plain/tests/run.sh
sh block-storage-encrypted/tests/run.sh
sh nfs-direct/tests/run.sh
```

Expected: strict lint, applicable positive/negative renders, YAML/resource checks, shell syntax/lint, explicit versions and standalone package checks pass. NFS static fixtures provide documentation-only server/export values; encrypted fixtures use Secret references, never real keys/tokens. Verify the runner is static before invocation.

## 2. Inspect the normal flows

```sh
helm template plain block-storage-plain --namespace examples --kube-version 1.33.0
helm template encrypted block-storage-encrypted --namespace examples --kube-version 1.33.0
helm template nfs nfs-direct --namespace examples --kube-version 1.33.0 \
  --set nfs.server=192.0.2.10 --set nfs.exportPath=/exports/example
```

Expected: concrete per-chart topology, default `debug-initdata`, default class omitted for block claims, no NFS PV/PVC, no unused-role images or multi-chart conditionals. Nothing is applied to the cluster.

## 3. Render essential alternatives

```sh
helm template encrypted block-storage-encrypted --namespace examples --kube-version 1.33.0 \
  --set keyDelivery.mode=sealed --set keyDelivery.secret.name=existing-envelope \
  --set keyDelivery.secret.key=envelope
helm template encrypted block-storage-encrypted --namespace examples --kube-version 1.33.0 \
  --set keyDelivery.mode=insecureSecret --set keyDelivery.secret.name=existing-test-key
helm template plain block-storage-plain --namespace examples --kube-version 1.33.0 \
  --set storage.storageClass=example-block-delete --set storage.size=2Gi \
  --set images.storageHelper=mirror.example.test/osc-storage-helper:1.13.1
```

Expected: precisely selected key references/containers, existing resources remain unowned, all applicable helper/application references use the mirror. Static fixtures/checks also exercise inline initdata precedence, explicit cluster-default selection, utility mirrors, pull Secrets, SCC opt-in, resources and invalid input rejection. No real signed token or secret value is needed.

## 4. Review isolation and readability

- Compare four renders: `plain`, `encrypted`, `nfs`, and `plain-two` in `examples`; repeat a filename render in another namespace. Check names, selectors, claim/Secret references and namespace-scoped prose identity. Do not deploy them.
- Measure template lines/actions/helper definitions and values leaves using the same method as the [plan baseline](plan.md#simplification-acceptance). Review schema/script totals to rule out relocated complexity.
- Within 10 minutes per example, trace storage source → preparation → main-visible access → prose outcome → readiness/cleanup. Confirm failure paths preserve data and do not leak keys or write on temporary storage.
- Confirm docs prescribe delete/recreate only, explain that block uninstall deletes data while pod replacement retains it, and state upstream/platform prerequisites without live-validation claims.

## Completion evidence

See [validation.md](validation.md) for the recorded local static checks, reductions and source-review limitations. Rerun these checks after changes, and require actual revised static CI success before merge. Do not append cluster acceptance tasks or report intended runtime behavior as tested.
