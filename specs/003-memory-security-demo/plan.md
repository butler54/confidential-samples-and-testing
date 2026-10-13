# Implementation Plan: Confidential Memory-Security Demonstrations

**Branch**: `004-memory-security-demo` | **Date**: 2026-10-09 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-memory-security-demo/spec.md`

## Summary

Fold the coco-baremetal memory-security test workflows into this repository as **two independent, self-contained Helm examples** plus manual step-through documentation:

1. **`memory-security`** — deploys an in-cluster magic-string endpoint (Red Hat httpd serving a ConfigMap file) behind one edge-TLS OpenShift Route that serves plaintext HTTP by design (the documented, confined demonstration target); three graduated-trust fetcher pods (ordinary runc, non-confidential `kata` VM, confidential `kata-cc`); and a dedicated **transport comparison pair** of two `kata-cc` pods (one HTTPS, one HTTP; HTTP confined to that pod only — an explicitly documented, chart-intended exception, not a toggle). A README walkthrough with copy-paste blocks drives host observations: host-filesystem read of the ordinary tier, `gcore` dumps of the two VM tiers' QEMU processes (string present in kata, absent in CoCo/TDX), and the HTTP-vs-HTTPS buffer observation at the router (haproxy process memory) and on the fetching pods' host node (plaintext packet buffering).
2. **`kbs-client`** — a deliberately minimal, standalone chart deploying a single confidential client container for manually running the attestation key-broker client against the cluster's Trustee; independent of the memory demo.

No automated behavioural tests: validation is the repository-standard static pipeline (`helm lint --strict`, `shellcheck`, `sh -n`, per-chart `tests/static.py` render assertions) wired into the existing CI matrix, plus the manual walkthrough documents. Tooling images (coredump helper, kbs-client) are built in `butler54/containers` per FR-011 and consumed pinned; this feature documents the dependency and performs no builds.

## Technical Context

**Language/Version**: Helm 3 (chart apiVersion v2, Kubernetes `>=1.33.0-0`), POSIX shell scripts, Python 3.12 for static validation only

**Primary Dependencies**: Helm, OpenShift Routes (edge termination), Kata runtime classes (`kata`, `kata-cc`) and coco-pattern initdata integration; Red Hat images (`ubi9/ubi`, `ubi9/httpd-24`); external tooling images from `butler54/containers` (coredump helper, kbs-client)

**Storage**: N/A (emptyDir `Memory` volumes for the held magic string; no persistence)

**Testing**: Static only — `helm lint --strict`, `shellcheck`, `sh -n`, per-chart `tests/static.py` render/rejection assertions (mirrors sibling examples); no live cluster tests

**Target Platform**: Red Hat OpenShift ≥ 4.x on bare metal with Intel TDX, running the coco-pattern (Trustee KBS, runtime classes, initdata propagation); cluster-admin access for `oc debug node`

**Project Type**: Helm example charts + documentation + shell debugging tooling

**Performance Goals**: N/A (demonstration workloads; modest pod resources mirroring predecessor: 2 vCPU/4Gi VM pods)

**Constraints**: No image builds in this repo; no GitHub/external-network fetches at runtime; HTTPS is default and HTTP is confined to one designated pod as an explicitly documented chart-intended exception (no feature toggle); offline-capable (all pulls from registries documented as mirrors-overridable); delete/recreate lifecycle only; static validation only

**Scale/Scope**: 2 chart directories (`memory-security/`, `kbs-client/`), ≤10 templates and ≤6 shell scripts total in the memory chart, 1 walkthrough README per chart, CI matrix extended from 3 to 5 charts

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Evidence |
|-----------|---------|----------|
| I. Self-Contained Examples | PASS | Each chart ships its own templates, values, scripts, README/walkthrough, and static checks; no cross-example dependencies |
| II. Helm-First Delivery | PASS | Both deliverables are Helm charts; only host-observation helpers are shell (permitted debugging-tooling exception); no Kustomize |
| III. Downstream-First Dependencies | PASS | Endpoints/fetchers use `registry.access.redhat.com` images; router observation uses the Red Hat network-tools image; the two required non-Red Hat tools (coredump, kbs-client) are built in `butler54/containers` and pinned, per FR-011 |
| IV. External Image Builds | PASS | Zero image builds here; FR-011 documents the `butler54/containers` dependency with pinned references |
| V. CI/CD and Version Discipline | PASS | Both charts carry explicit `version` (0.1.0) and pinned `appVersion`; `.github/workflows/validate-examples.yml` matrix extended so lint/render regressions are caught |
| VI. Simplicity and Explainability | PASS | No shared framework; per-chart concrete templates mirroring the simplified sibling charts; walkthroughs explain every command and expected observation; plaintext HTTP is the only deliberate weakening, loudly documented as demonstration-only |

No violations; Complexity Tracking not required.

## Project Structure

### Documentation (this feature)

```text
specs/003-memory-security-demo/
├── plan.md              # This file
├── research.md          # Phase 0 output: mechanics and sourcing decisions
├── data-model.md        # Phase 1 output: manifest/value entities
├── quickstart.md        # Phase 1 output: static validation runbook
├── contracts/
│   ├── values.md            # values + naming contract for both charts
│   └── runtime-and-validation.md  # static-only validation boundaries
└── tasks.md             # Phase 2 output (/speckit.tasks - NOT created here)
```

### Source Code (repository root)

```text
memory-security/                 # US1 + US2: tiers, endpoint, transport pair
├── Chart.yaml                   # version 0.1.0, appVersion tracks demo image
├── values.yaml / values.schema.json
├── README.md                    # walkthrough (copy-paste blocks), supersedes BAREMETAL-tests.md
├── .helmignore                  # mirrors sibling charts (tests/ excluded from package)
├── templates/
│   ├── deployment-magic-server.yaml   # endpoint (runc tier)
│   ├── service-magic-server.yaml
│   ├── route-magic-server.yaml        # edge TLS; Allow plaintext by design (documented)
│   ├── configmap-magic-string.yaml    # served file content from values
│   ├── pod-standard.yaml              # runc tier
│   ├── pod-kata.yaml                  # non-confidential VM tier
│   ├── pod-coco.yaml                  # confidential tier (initdata annotation)
│   ├── pod-fetch-https.yaml           # transport pair, TLS fetcher
│   ├── pod-fetch-http.yaml            # transport pair, plaintext fetcher (intended exception)
│   └── NOTES.txt
├── scripts/
│   ├── get-pod-mac.sh           # pod → MAC lookup (arg: pod name + namespace)
│   └── get-pod-uid.sh           # pod → UID lookup
└── tests/
    ├── requirements.txt         # pinned parser deps (same pins as siblings)
    ├── run.sh                   # helm lint --strict w/ demo sets, shellcheck, sh -n
    └── static.py                # render/rejection assertions (see contracts/values.md rules)

kbs-client/                      # US3: independent minimal client chart
├── Chart.yaml                   # version 0.1.0
├── values.yaml / values.schema.json
├── README.md                    # brief install/exec/retrieve/cleanup doc
├── .helmignore
├── templates/
│   ├── deployment-client.yaml   # single confidential client container
│   └── NOTES.txt
└── tests/
    ├── requirements.txt
    ├── run.sh
    └── static.py

README.md                        # root index gains both examples + predecessor-successor note
.github/workflows/validate-examples.yml   # matrix + paths extended to both new dirs
```

**Structure Decision**: Two independent example directories at repo root, mirroring the simplified sibling charts (concrete templates, `scripts/`, `tests/`, README). No shared chart framework, no Python at workload runtime, and no changes to the three existing storage examples. The memory chart's helper shell scripts stay in-chart as documented debugging tooling (constitution II exception).

## Phase 0 — Research

See [research.md](research.md). Headline decisions:

1. **Endpoint**: `ubi9/httpd-24` Deployment serving a ConfigMap-mounted file behind Service + single edge-TLS Route (`insecureEdgeTerminationPolicy: Allow` — HTTP served by design as the documented demonstration target). No GitHub dependency anywhere.
2. **Route host determinism**: `route.host` is a required value (no auto-assigned hosts), so fetcher pods can be templated with the exact URL; distinct hosts per release documented for coexistence.
3. **Route authentication for the HTTPS fetcher**: `curl -k` documented explicitly — TLS still encrypts (the buffer observation is unaffected); CA trust setup is an optional documented extension, not a default.
4. **Observation mechanics**: router = `gcore` dump of the haproxy process on the ingress node via the coredump-helper tooling image; host node = plaintext packet capture from the fetch pod's egress path via the Red Hat network-tools debug image (deterministic for HTTP, ciphertext for HTTPS); VM tiers = `gcore` of the QEMU processes found via pod MAC.
5. **Transport pair by design**: Both fetch pods and the `Allow` route policy are always rendered — HTTPS is default behaviour, HTTP is the single explicitly documented exception; there is no flag. Plain `helm install` (with the required `route.host`) produces the complete demo. This implements FR-003's documented-intent model literally and keeps the testing-only delete/recreate lifecycle simple.
6. **Tooling images**: coredump helper and kbs-client are values with pinned defaults referencing `butler54/containers` builds (FR-011); interrupted until those builds exist is documented in the walkthroughs' prerequisites.

## Phase 1 — Design

1. **Entities**: see [data-model.md](data-model.md) — release-scoped pods/tiers, endpoint (Deployment/Service/Route/ConfigMap), transport pair, values contract, initdata selection, helper scripts, static assertions.
2. **Contracts**: see [contracts/values.md](contracts/values.md) (values surface, naming, route policy rules, static-check expectations) and [contracts/runtime-and-validation.md](contracts/runtime-and-validation.md) (what static validation proves vs. explicitly does not).
3. **Walkthroughs**: `memory-security/README.md` is the copy-paste walkthrough fulfilling FR-006..FR-008 (prereq checks → install → three-tier dumps → transport comparison at router+host node → expected outputs → cleanup); `kbs-client/README.md` is its brief independent doc; root `README.md` indexes both.
4. **Validation**: [quickstart.md](quickstart.md) documents running the static pipeline for both charts; live steps remain manual per FR-009.

### Constitution Check (post-design)

Re-evaluated against the table above: all six principles still PASS. The `network-tools` observation step is downstream-first and user-invoked; plaintext HTTP on the route is the chart's single deliberate weakening — always rendered, loudly documented as demonstration-only and confined to one designated pod — consistent with principle VI's documented-purpose rule.

## Complexity Tracking

No constitution violations — nothing to justify.
