# Validation: Confidential Memory-Security Demonstrations

**Date**: 2026-10-13 · **Branch**: `004-memory-security-demo` · **Spec**: [spec.md](spec.md)

Lint/shell and manual-render-spot-check validation, per contracts/runtime-and-validation.md. No cluster, registry, cluster-hosted endpoint, or Trustee was contacted; no workload shell or image was executed.

## Executed checks

| Check | Result |
|---|---|
| `sh memory-security/tests/run.sh` (Helm 3.22.0 lint `--strict`, ShellCheck, `sh -n`) | PASS — 0 failures |
| `sh kbs-client/tests/run.sh` (same pipeline) | PASS — 0 failures |
| `sh {block-storage-plain,block-storage-encrypted,nfs-direct}/tests/run.sh` (regression after repo-wide `static.py` removal) | PASS — 0 failures ×3 |
| Manual render spot-check: `helm template` of memory-security with demo values | PASS — 5 pods rendered (`standard`, `kata`, `coco`, `fetch-https`, `fetch-http`), exactly one `http://` command (in `fetch-http`), plaintext markers present on Route and `fetch-http` pod |
| Multi-release render (`alpha` + `beta` of memory-security) | PASS — 0 shared resource names across releases |

## Post-review changes (PR #5 review)

Per reviewer direction:

1. **Template deduplication** — the three confidential (kata-cc) pod templates (`pod-coco.yaml`, `pod-fetch-https.yaml`, `pod-fetch-http.yaml`) were merged into a single ranged template, `templates/pods-kata-cc.yaml`; rendered output verified identical in shape (pod names/labels, runtime class, initdata logic, transport schemes, markers).
2. **`tests/static.py` removed repo-wide** — all five charts now validate with lint + shell checks only. `tests/requirements.txt` pins `shellcheck-py` only; the CI matrix is unchanged (5 charts), workflow step renamed accordingly. Structural contract items (route policy, HTTP/string confinement, naming) remain documented review contracts in contracts/values.md and are spot-checkable per quickstart.md.

## Tooling-image status (FR-011)

The coredump helper (`quay.io/butler54/coredump:0.1.0`) and kbs-client (`quay.io/butler54/kbs-client:0.1.0`) references are **documented placeholders** of the images to be built in `butler54/containers`. No build happened in this repository and none is validated here; the walkthroughs name the placeholder reference and the required override. `memory-security` chart renders never reference tooling images; `kbs-client` pins its client image as a chart value.

## Explicitly not verified (per contract)

- Memory observations themselves (any tier's dump contents, router haproxy buffers, packet captures) — these are the manual user-run demonstrations.
- Route serving, DNS, TLS trust, ingress plaintext behaviour on any cluster.
- Trustee reachability, attestation, retrieval, and kbs-client runtime behaviour.
- Image existence of the placeholder tooling references until published.
- TDX capability of any host.
- Full README ↔ rendered-name consistency beyond the manual render spot-checks above.
