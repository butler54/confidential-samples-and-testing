---
description: "Task list for Confidential Memory-Security Demonstrations (feature 003)"
---

# Tasks: Confidential Memory-Security Demonstrations

**Input**: Design documents from `/specs/003-memory-security-demo/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/values.md, contracts/runtime-and-validation.md, quickstart.md

**Tests**: No behavioural test harness exists per FR-009. Per-chart static validation (`tests/run.sh`, `tests/static.py`) is repo-standard assurance and is generated as implementation tasks here.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Charts at repository root: `memory-security/`, `kbs-client/` (mirror sibling examples' layout: `templates/`, `scripts/`, `tests/`, README)
- Repo-level: `README.md`, `.github/workflows/validate-examples.yml`

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Chart skeletons so all story work has a home; no logic yet.

- [X] T001 [P] Create `memory-security/` skeleton: `.helmignore` (mirror sibling charts: `.git/`, `.venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `tests/`, `*.secret.yaml`, `*.private.json`, `*.key`, `*.crt`, `.pytest_cache/`, `*.tgz`) and `memory-security/tests/requirements.txt` with the exact same pinned parser deps as `nfs-direct/tests/requirements.txt`
- [X] T002 [P] Create `kbs-client/` skeleton: `.helmignore` identical to T001 and `kbs-client/tests/requirements.txt` identical to the sibling pins
- [X] T003 [P] Create `memory-security/Chart.yaml`: apiVersion v2, name `memory-security`, description of graduated memory-visibility demo, type application, version `0.1.0`, `appVersion: "9.6"`, `kubeVersion: ">=1.33.0-0"`
- [X] T004 [P] Create `kbs-client/Chart.yaml`: same conventions, name `kbs-client`, version `0.1.0`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The memory-security values contract that every story's templates render against (contracts/values.md is the normative source).

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create `memory-security/values.yaml` and `memory-security/values.schema.json` implementing contracts/values.md exactly: `runtimeClassNames.{coco:kata-cc,kata:kata}`, `initdata.{configMapName:debug-initdata,encoded:""}` (empty configMapName ⇒ no kyverno annotation; non-empty `encoded` wins with hypervisor `init_data`), `images.{demo:registry.access.redhat.com/ubi9/ubi:9.6, magicServer:registry.access.redhat.com/ubi9/httpd-24:<current 9.6 tag>}`, `imagePullPolicy: IfNotPresent`, `imagePullSecrets: []`, `magic.string: MyMagicKeyIsABanana`, `route.host: ""` (schema MUST reject empty/non-FQDN at render so installs must supply it), sibling-style `resources` defaults (VM tiers sized for 2 vCPU/4Gi guest); add a values comment block stating the route serves plaintext HTTP by design as the documented demonstration exception (no flag values exist)

**Checkpoint**: Values contract complete - template work for all stories can now begin (chart lint only passes with `--set route.host=...`, like siblings' required values)

---

## Phase 3: User Story 1 - Observe graduated memory visibility across three workload tiers (Priority: P1) 🎯 MVP

**Goal**: Chart installs endpoint + three graduated-trust tiers; the walkthrough lets a reader observe host-side exposure per tier (filesystem, kata QEMU dump with string, coco QEMU dump without string + TDX evidence).

**Independent Test**: `sh memory-security/tests/run.sh` passes with US1 assertions (endpoint objects, exactly three tier pods with correct runtime classes and initdata rules, route with edge TLS + `Allow`, zero `http://` commands at this phase — upgraded to exactly one by US2, string confined to ConfigMap); README US1 sections reference only rendered resource names.

### Implementation for User Story 1

- [X] T006 [US1] Create `memory-security/templates/configmap-magic-string.yaml` (key `magic.txt` from `.Values.magic.string`) and `memory-security/templates/deployment-magic-server.yaml` + `memory-security/templates/service-magic-server.yaml` (httpd-24 image, port 8080→80, ConfigMap docroot mount, restricted securityContext, names `<release>-magic`, labels by release)
- [X] T007 [US1] Create `memory-security/templates/route-magic-server.yaml`: `spec.host: {{ .Values.route.host }}`, `tls.termination: edge`, `tls.insecureEdgeTerminationPolicy: Allow` (plaintext HTTP served by design — the chart's documented demonstration target)
- [X] T008 [P] [US1] Create `memory-security/templates/pod-standard.yaml`: no runtimeClassName; `fetch-key` initContainer running `curl -ks https://{{ .Values.route.host }}/magic.txt -o /keys/magickey.txt` on `images.demo`; main container `sleep infinity`; `emptyDir{medium: Memory}` at `/keys`; restricted-compatible securityContext
- [X] T009 [P] [US1] Create `memory-security/templates/pod-kata.yaml`: same shape as T008 plus `runtimeClassName: {{ .Values.runtimeClassNames.kata }}` and hypervisor vCPU/memory annotations from values
- [X] T010 [US1] Create `memory-security/templates/pod-coco.yaml`: same shape as T009 plus `runtimeClassNames.coco` and initdata rendering per data-model.md (`encoded` wins, quoted hypervisor annotation; else non-empty `configMapName` kyverno annotation; else none)
- [X] T011 [P] [US1] Create `memory-security/scripts/get-pod-uid.sh` and `memory-security/scripts/get-pod-mac.sh`: positional args `<pod> <namespace>`; UID script prints JSONPath UID; MAC script parses the `k8s.ovn.org/pod-networks` annotation to the primary MAC (as predecessor get-mac scripts did); both fail loudly on empty args/missing pod
- [X] T012 [US1] Create `memory-security/templates/NOTES.txt`: post-install summary — release pod names, endpoint URL, and pointer to README walkthrough sections
- [X] T013 [US1] Create `memory-security/tests/run.sh` (sibling pattern: `helm lint --strict --kube-version 1.33.0 --set route.host=static.apps.example.test`, shellcheck incl. run.sh, `sh -n`, invokes static.py) and `memory-security/tests/static.py` with US1 assertions per contracts: default render contains endpoint Deployment/Service/Route + pods `<rel>-standard|kata|coco` (no fetch pods yet at this phase), correct runtime classes, initdata precedence renders (three variants rendered via template calls), zero `http://` substrings in container commands at this phase, route has `tls.termination: edge` + `insecureEdgeTerminationPolicy: Allow`, `magic.string` appears only in the ConfigMap, schema rejects missing `route.host`, all images tag-pinned default-registry only
- [X] T014 [US1] Create `memory-security/README.md` US1 sections: repo-successor note (supersedes butler54/coco-baremetal BAREMETAL-tests.md), prerequisites (TDX cluster, coco-pattern, cluster-admin, `oc debug node`, coredump-helper tooling image pin + network-tools note), single-mode install copy-paste block (with the documented-intent warning that the route serves plaintext HTTP by design, confined to a designated pod introduced in the US2 section), three-tier observation walkthrough (host fs path via get-pod-uid.sh; per-VM-tier node → privileged coredump container → MAC→QEMU PID via get-pod-mac.sh → `gcore` → `strings|grep` with expected counts, kata ≥1 / coco 0 + TDX flags evidence), expected-output table per FR-008, delete/recreate cleanup

**Checkpoint**: `sh memory-security/tests/run.sh` green; US1 document complete - MVP deployable as a document+chart artifact

---

## Phase 4: User Story 2 - Compare plaintext versus encrypted transport visibility in memory buffers (Priority: P2)

**Goal**: The chart-inherent transport pair fetches the same route over HTTPS vs HTTP (HTTP serving and usage are intended, documented chart behavior); walkthrough shows string in buffers (router gcore, host-node packet capture) for HTTP only.

**Independent Test**: static.py US2 cases pass — every render contains both fetch pods, exactly one `http://` command (in `<rel>-fetch-http`, never zero or two, and no other pod touches HTTP), route carries `Allow` plus the demonstration-intent markers, and README/NOTES contain the demonstration-only HTTP notice; US1 assertions remain green.

### Implementation for User Story 2

- [X] T015 [P] [US2] Create `memory-security/templates/pod-fetch-https.yaml`: always rendered; same kata-cc/initdata/resource shape as pod-coco.yaml; command fetches `https://{{ .Values.route.host }}/magic.txt` with `curl -k`
- [X] T016 [P] [US2] Create `memory-security/templates/pod-fetch-http.yaml`: always rendered (the chart's single intended HTTP exception); identical shape but `http://` scheme and **no** `-k`; loud demonstration-only warning comment
- [X] T017 [US2] Update `memory-security/templates/route-magic-server.yaml` and `memory-security/templates/NOTES.txt`: add the demonstration-intent warning comment/annotation on the route's plaintext HTTP (rendered since T007) and a NOTES pointer to the README warning section; no behavior change
- [X] T018 [US2] Extend `memory-security/tests/static.py` with US2 cases: every render contains both `<rel>-fetch-https` and `<rel>-fetch-http`; exactly one rendered `http://` command (in the http pod; assert zero occurrences in any other pod) and US1's zero-`http://` phase assertion is upgraded accordingly; route has `tls.termination: edge` + `Allow` + the intent-marker comment/annotation; README and NOTES contain the demonstration-only HTTP notice string
- [X] T019 [US2] Extend `memory-security/README.md` with the transport-comparison section: statement that the route serves plaintext HTTP by design as the chart's intended demonstration (HTTPS is default everywhere else; HTTP confined to `<rel>-fetch-http`), fresh-fetch trigger per freshness edge case, router observation (locate router pod/node → coredump container → haproxy `gcore` → string search, expected present/absent for HTTP/HTTPS), host-node observation (`network-tools` debug container → `tcpdump -i any -A` on pod egress during re-fetch, expected plaintext vs ciphertext), secured-cluster prerequisite note (ingress configurations that reject plaintext, failure symptom, secure posture returns on uninstall), expected-output table rows

**Checkpoint**: US1 and US2 both validated statically; walkthrough covers both stories end-to-end on paper

---

## Phase 5: User Story 3 - Deploy the key-broker client utility as an independent minimal chart (Priority: P3)

**Goal**: Standalone `kbs-client` chart deploys one confidential client container; its README gives copy-paste exec/retrieve/cleanup commands against the cluster Trustee.

**Independent Test**: `sh kbs-client/tests/run.sh` passes (single kata-cc Deployment with initdata rules, pinned image, no net objects); README commands reference only the rendered `<release>-client` name.

### Implementation for User Story 3

- [X] T020 [US3] Create `kbs-client/values.yaml` and `kbs-client/values.schema.json`: `images.client` pinned `butler54/containers` kbs-client build reference (documented placeholder tag until build exists), `runtimeClassName: kata-cc`, same `initdata.*` contract as memory-security, `kbs.address: ""` optional override, modest `resources`, `imagePullSecrets`/`imagePullPolicy`
- [X] T021 [US3] Create `kbs-client/templates/deployment-client.yaml` (single container, `sleep infinity`, kata-cc + initdata precedence rendering identical to memory-security rules) and `kbs-client/templates/NOTES.txt` (pod name + `oc exec` pointer)
- [X] T022 [US3] Create `kbs-client/tests/run.sh` + `kbs-client/tests/static.py`: default render = one Deployment `<rel>-client`, `runtimeClassName: kata-cc`, initdata precedence variants, image tag-pinned, no Service/Route/Secret objects, entrypoint `sleep infinity`
- [X] T023 [US3] Create `kbs-client/README.md`: prerequisites (Trustee via coco-pattern, tooling image published per FR-011), install block, `kbs.address` default-construction one-liner for the Trustee route, copy-paste `oc exec` retrieval of a demo resource, expected attestation-success output, delete/recreate cleanup, independence note

**Checkpoint**: All three stories independently validatable statically

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Repo-level integration, CI, and honest evidence.

- [X] T024 Update root `README.md`: add `memory-security` and `kbs-client` rows to the example index, predecessor-successor note, and offline-capability mention; keep delete/recreate warning
- [X] T025 Update `.github/workflows/validate-examples.yml`: rename workflow to `Validate examples`, extend path filters and matrix with `memory-security` and `kbs-client` (keep pinned actions/versions)
- [X] T026 Write `specs/003-memory-security-demo/validation.md`: run `sh memory-security/tests/run.sh` and `sh kbs-client/tests/run.sh`, record case counts and results, list runtime behaviors explicitly unverified (per contracts/runtime-and-validation.md), and note the pending `butler54/containers` tooling builds as documented prerequisites

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on T001/T003 (values land in memory-security/) - BLOCKS US1 and US2 templates
- **User Stories**: US1 (Phase 3) → US2 (Phase 4) is sequential by files (route-magic-server.yaml, README.md, static.py are shared); US3 (Phase 5) is file-independent of US1/US2 and can run in parallel with them after Phase 1
- **Polish (Phase 6)**: Depends on all stories complete

### User Story Dependencies

- **US1 (P1)**: memory-security values (T005) → endpoint (T006, T007) → pods (T008–T010, parallel) → helpers (T011) → NOTES (T012) → static checks (T013) → README (T014)
- **US2 (P2)**: US1 route file exists (T007) → pair pods (T015, T016, parallel) → route/NOTES intent markers (T017) → static cases (T018) → README section (T019)
- **US3 (P3)**: kbs-client skeleton (T002, T004) → values (T020) → deployment (T021) → static checks (T022) → README (T023)

### Parallel Opportunities

- T001–T004 all parallel (distinct files)
- T008, T009 (US1 pods) and T011 (scripts) parallel after T005
- T015, T016 (US2 pair) parallel after T005
- Entire US3 phase (T020–T023) parallel to US1/US2 phases after Phase 1

### Parallel Example: User Story 1

```bash
# After T005:
Task: "Create memory-security/templates/pod-standard.yaml (T008)"
Task: "Create memory-security/templates/pod-kata.yaml (T009)"
Task: "Create memory-security/scripts/get-pod-uid.sh + get-pod-mac.sh (T011)"
```

### Parallel Example: Cross-story

```bash
# After Phase 1 (skeletons) and T005 (values):
Track A: T006→T014 (US1), then T015→T019 (US2)
Track B: T020→T023 (US3)   # no shared files with Track A
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1 (T001–T004) and Phase 2 (T005)
2. Complete Phase 3 (T006–T014) — endpoint, tiers, helpers, static checks, US1 walkthrough
3. **STOP and VALIDATE**: `sh memory-security/tests/run.sh` green; README walks US1 independently
4. This alone delivers the core memory-encryption demonstration

### Incremental Delivery

1. Setup + Foundational → contract ready
2. US1 → MVP (graduated memory visibility)
3. US2 → adds transport comparison (pod pair + route intent markers + walkthrough section)
4. US3 → adds independent kbs-client chart (fully parallel track)
5. Polish → repo index, CI, validation evidence

---

## Notes

- [P] tasks = different files, no dependencies
- US1/US2 share `route-magic-server.yaml`, `static.py`, and `README.md` — keep sequential within memory-security
- All static validation is offline; no cluster, registry, or Trustee access at any point
- Tooling images from `butler54/containers` are documented inputs; chart renders never reference them
- Delete/recreate only; no upgrade flows anywhere
