# Validation: Confidential Memory-Security Demonstrations

**Date**: 2026-10-13 · **Branch**: `004-memory-security-demo` · **Spec**: [spec.md](spec.md)

Static-only validation, per contracts/runtime-and-validation.md. No cluster, registry, cluster-hosted endpoint, or Trustee was contacted; no workload shell or image was executed.

## Executed checks

| Check | Result |
|---|---|
| `sh memory-security/tests/run.sh` (Helm 3.22.0 lint `--strict`, ShellCheck, `sh -n`, static.py) | PASS — "US1+US2 static checks passed across 7 Helm renders" |
| `sh kbs-client/tests/run.sh` (same pipeline) | PASS — "static checks passed across 7 Helm renders" |
| Multi-release render (`alpha` + `beta` of memory-security) | PASS — 0 shared resource names across releases |

## Static render/rejection case inventory

**memory-security** (7 counted renders + 1 raw template call):

1. Default render — endpoint Deployment/Service/Route/ConfigMap; tiers `standard|kata|coco`; pair `fetch-https|fetch-http`; runtime classes correct (`runc`/`kata`/`kata-cc`); hypervisor annotations on VM pods.
2. `initdata.encoded=eA==` → hypervisor `init_data` annotation, no kyverno annotation.
3. `initdata.configMapName=""` → no initdata annotation at all.
4. `initdata.configMapName=custom-initdata` → kyverno annotation with custom name.
5. Reject: missing `route.host`.
6. Reject: `route.host=localhost` (not an FQDN).
7. Reject: `route.host=Demo.apps.example.test` (uppercase).

Plus in-default-render assertions (not separate renders): exactly one `http://` command (in `fetch-http`); TLS only for all other fetchers; route `edge` + `Allow` + `memory-security.dev/plaintext-http=demonstration-only`; magic-string content appears exactly once (ConfigMap only); DEMONSTRATION ONLY markers in route/fetch-http templates, README, NOTES; images pinned, no `:latest`, default-registry only; no personal-registry (`quay.io/rh-ee-…`) content; no `transport` values flag exists.

**kbs-client** (7 counted renders):

1. Default render — single Deployment `demo-client`, `kata-cc`, `debug-initdata`, `sleep infinity`, pinned image, no Service/Route/Secrets, no env when `kbs.address` empty.
2–4. Initdata precedence renders (encoded / empty / custom configMapName).
5. `kbs.address=https://kbs.example.org` → `KBS_ADDRESS` env present.
6. Reject: `images.client=…:latest`.
7. Reject: empty `runtimeClassName`.

## Tooling-image status (FR-011)

The coredump helper (`quay.io/butler54/coredump:0.1.0`) and kbs-client (`quay.io/butler54/kbs-client:0.1.0`) references are **documented placeholders** of the images to be built in `butler54/containers`. No build happened in this repository and none is validated here; the walkthroughs name the placeholder reference and the required override. `memory-security` chart renders never reference tooling images; `kbs-client` pins its client image as a chart value.

## Explicitly not verified (per contract)

- Memory observations themselves (any tier's dump contents, router haproxy buffers, packet captures) — these are the manual user-run demonstrations.
- Route serving, DNS, TLS trust, ingress plaintext behaviour on any cluster.
- Trustee reachability, attestation, retrieval, and kbs-client runtime behaviour.
- Image existence of the placeholder tooling references until published.
- TDX capability of any host.
- `README.md` ↔ rendered-name consistency beyond the marker/notices statically asserted.

Residual follow-ups noted for future validation work: cohort name-uniqueness is currently verified manually (two-release check above) rather than in static.py.
