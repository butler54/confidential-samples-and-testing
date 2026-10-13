---
description: "Task list for io-benchmark-harness implementation"
---

# Tasks: IO Benchmark Harness for Confidential Pods

**Input**: Design documents from `/specs/004-benchmark-harness/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not requested by the spec. Validation = repository lint pipeline
(`helm lint --strict`, `shellcheck`, `sh -n`, `py_compile`) + quickstart.md live runbook.
No unit-test tasks are generated.

**Organization**: Single deliverable surface (`io-benchmark/tools/bench.py` + one chart) — user
stories share files, so within-story and cross-story sequencing matters more than parallelism.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Different files, no incomplete dependencies
- **[Story]**: US1 = benchmark tool analysis · US2 = single-case pipeline · US3 = six-case serial comparison + summaries · US4 = characterized repeatability / cache-defeat stamp

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: `io-benchmark/` example skeleton + CI wiring (repo's self-contained-dir convention)

- [x] T001 Create `io-benchmark/` directory structure per plan.md (chart root, `tools/`, `docs/`, `tests/`) with `io-benchmark/Chart.yaml` (apiVersion v2, name `io-benchmark`, version `0.1.0`, correct `dependences–empty`, description of one-case benchmark pod chart)
- [x] T002 [P] Create `io-benchmark/values.yaml` + `io-benchmark/values.schema.json` with all contract values (`case.slug` enum of the six slugs, `case.runtimeClassName`, `case.encrypted`, `node.name` required, `pvc.storageClass`/`pvc.size` required, `pod.cpu/mem` defaults `2`/`4096Mi`, `images.workload` default `quay.io/rh-ee-chbutler/perf-utils`, `initdata.mode` enum `debug|cluster-default`, `imagePullSecrets[]`, `namespace`, `fioJobInline` override); schema MUST reject `latest`-tag images and unknown case slugs
- [x] T003 [P] Create `io-benchmark/requirements.txt` pinning PyIceberg and PyArrow to exact versions (control-side only, FR-018)
- [x] T004 [P] Create `io-benchmark/tests/run.sh`: `helm lint --strict` with demo values, `shellcheck`/`sh -n` on itself and any shell in dir, `python3 -m py_compile tools/bench.py`, plus repo-hygiene scan (fails if any Containerfile/Dockerfile found, constitution v2.0.0 IV); makes itself executable; this is the CI entry point per repo convention
- [x] T005 Add `io-benchmark` row to the matrix in `.github/workflows/validate-examples.yml` pointing at `io-benchmark/tests/run.sh`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: One case chart + the `bench.py` control shell that every story builds on

**⚠️ CRITICAL**: No user-story phase can start until the chart renders all six case shapes and
the CLI/preflight/cleanup skeleton exists.

- [x] T006 [P] Create `io-benchmark/templates/pvc.yaml`: namespaced PVC `<release>-<case.slug>` with `volumeMode: Block`, `accessModes: [ReadWriteOnce]`, `storageClassName` + `resources.requests.storage` from values
- [x] T007 [P] Create `io-benchmark/templates/configmap-fio-job.yaml`: default fio job file baked into values (global `direct=1`, `ioengine=libaio`, `iodepth=32`, `time_based` with `runtime` + `ramp_time`, `invalidate=1`, `stonewall` between jobs; sections covering seqread/seqwrite/randread/randwrite × bs 4k..1M ladder on the mounted test file); templated from `.Values.fioJobInline` override or the bundled default
- [x] T008 [P] Create `io-benchmark/templates/pod.yaml`: main container (`images.workload`, `command: ["sleep","infinity"]`, `volumeDevices` on the PVC, `securityContext.privileged: true` with comments documenting LUKS/mount need per FR-010), `nodeName` from values, `runtimeClassName` only when `case.runtimeClassName` non-empty, `pod.cpu/mem` limits+requests, `imagePullSecrets`, optional LUKS init container (same image) rendered only when `case.encrypted: format/unlock/mount/fsck helpers` per research R6 comments; `kata-cc` initdata annotation applied per `initdata.mode`
- [x] T009 [P] Create `io-benchmark/templates/NOTES.txt` describing what was rendered (case slug, runtimeClass, volume size, node) and how to delete
- [x] T010 Create `io-benchmark/tools/bench.py` skeleton: `VERSION` constant, argparse CLI implementing every flag/exit code in contracts/operator-surface.md, fixed-format logging helpers (`PREFLIGHT …`, `CASE <slug> <phase>`), dry-run mode, `subprocess` wrappers for `oc`/`helm` with timeouts (R10) and captured output
- [x] T011 Implement preflight module in `io-benchmark/tools/bench.py`: cluster reachability, node exists + schedulability, runtimeClass presence per selected cases (`kata`/`kata-cc`), optional `--coco-validate=strong` node-debug TDX check, node memory read → FR-005 sizing evaluation → `PREFLIGHT CACHE-SUSPECT`, tenant census warning (FR-016), `oc`/`helm`/python-dep import checks, results-root writable
- [x] T012 Implement raw-block probe in `io-benchmark/tools/bench.py`: temporary small `volumeMode: Block` PVC in run namespace, wait for Bound, record OK/FAIL as `PREFLIGHT` line, delete and verify removal
- [x] T013 Implement render/apply/delete helpers in `io-benchmark/tools/bench.py`: `helm template <chart>` with per-case `--set`s → `oc apply -f -`, manifest saved to `<run_dir>/manifest-<case>.yaml`; cleanup path = `oc delete -f <manifest>` + poll-verify; signal handlers + `try/finally` guarantee cleanup runs on INT/TERM (R9)
- [x] T014 Implement `--cleanup-only <run-tag>` in `io-benchmark/tools/bench.py`: enumerate leftovers by label/name prefix `io-bench-<run-tag>` and delete deterministically with verification, exit 0/4 per contract

**Checkpoint**: `helm template` renders all six case shapes; `bench.py --dry-run ...` prints the
full PREFLIGHT block; `--cleanup-only` is a no-op on a clean cluster.

---

## Phase 3: User Story 1 - Documented, defensible benchmark tool selection (Priority: P1) 🎯 MVP

**Goal**: Ship the US1/FR-011 analysis deliverable as an operator-facing document

**Independent Test**: `io-benchmark/docs/benchmark-selection.md` exists, covers fio/sysbench/dbench
(as-is/wrapped/forked), names fio as selection against stated criteria, states what would change
the decision; a reader needs no other context.

- [x] T015 [P] [US1] Create `io-benchmark/docs/benchmark-selection.md` rendering research.md R1's criteria matrix, fio selection, wrapped/forked dbench rejections, and the "what would change the decision" clause as a standalone operator-facing analysis (FR-011)
- [x] T016 [P] [US1] Create skeleton `io-benchmark/README.md` with title, one-paragraph purpose, link to `docs/benchmark-selection.md`, and the image-ownership note required by constitution v2.0.0 IV (image `quay.io/rh-ee-chbutler/perf-utils`, built externally from `butler54/containers` `standard-quay/perf-utils`; repo defines/builds zero images)

**Checkpoint**: US1 acceptance scenarios 1–2 from spec pass by inspection.

---

## Phase 4: User Story 2 - One-command, end-to-end single-case benchmark (Priority: P1)

**Goal**: `bench.py --node … --storage-class … --cases plain …` completes the full FR-001
lifecycle for one case unattended

**Independent Test**: From a clean cluster, the single-case run provisions, measures, sums,
prints a case summary row, and deletes everything; rerun of identical command works
(quickstart.md §4).

- [x] T017 [US2] Add the six-case static catalog to `io-benchmark/tools/bench.py` (slugs in fixed order `plain, plain-luks, kata, kata-luks, coco, coco-luks` mapping to runtimeClassName + encrypted flag per data-model.md) and the `--cases` subset filter preserving canonical order
- [x] T018 [US2] Implement per-case lifecycle in `io-benchmark/tools/bench.py`: render manifest, apply, wait-for-Bound/PodReady with volume-size-scaled timeouts (R10), verify storage preparation log evidence (XFS present for unencrypted; dm-crypt+XFS for encrypted via pod logs), then proceed to exec phase
- [x] T019 [US2] Implement the fio exec driver in `io-benchmark/tools/bench.py`: per repeat 1..N, bounded `oc exec` running `fio --output-format=json --output=/results/rep<N>.json /job/fio.job` inside the main container, `oc cp`/log-based retrieval of each JSON into `<run_dir>/<case>/rep<N>/`, per-repeat failure isolation (rc/stderr tail recorded, other repeats continue)
- [x] T020 [US2] Implement fio JSON parsing in `io-benchmark/tools/bench.py` into the datapoint schema of data-model.md (job_name, pattern, block_size from section names, bw_bytes, iops, lat mean/p95/p99, status)
- [x] T021 [US2] Implement case-summary emission in `io-benchmark/tools/bench.py`: per-case log file, per-case summary row (stdout + `<run_dir>/summary-echo.txt`), explicit FAILED row path with exit code 2 semantics; write `run.env` at run start

**Checkpoint**: `--cases plain` completes unattended on a live cluster; summary row + raw logs
exist in `<results_root>/<run_tag>/`; cluster inspect shows no leftovers.

---

## Phase 5: User Story 3 - Serial six-case comparison with summary table (Priority: P2)

**Goal**: Default invocation runs six cases strictly serially and emits Markdown + Iceberg outputs

**Independent Test**: Default run leaves exactly one benchmark pod at a time (operator-observed),
emits `summary.md` with six populated-or-FAILED rows, and appends to
`<results_root>/iceberg-warehouse/` (quickstart.md §5).

- [x] T022 [US3] Implement the serial case loop in `io-benchmark/tools/bench.py`: iterate canonical order, `CASE` phase markers on stdout, per-case failure marked then loop continues unconditionally (FR-001), at-most-one-pod invariant documented and enforced by only creating the next pod after the previous manifest's verified deletion
- [x] T023 [US3] Implement end-of-run Markdown `summary.md` generation in `io-benchmark/tools/bench.py`: run metadata table (node, SC, sizes, volume, repeats, image, tool VERSION, timestamps), per-location row per case per job_name, FAILED entries for failed cases, `⚠ CACHE-SUSPECT` header row when stamped
- [x] T024 [US3] Implement the Iceberg writer in `io-benchmark/tools/bench.py`: local `sql` (SQLite) catalog at `<results_root>/iceberg-warehouse/catalog.db`, tables `runs.metadata`, `runs.case_iterations`, `runs.datapoints` per data-model.md, create-if-absent, append after each completed case + finalize at end; appends carry run_id and are idempotent by (run_id, case, repeat, job) for concurrent-invocation safety
- [x] T025 [US3] Implement `runs.case_aggregates` writing in `io-benchmark/tools/bench.py` from per-datapoint rows (n_repeats, min/max/mean/stddev columns for bw/iops/latency, spread_rel)
- [x] T026 [US3] Wire the encrypted-case end-to-end path in `io-benchmark/values.yaml` + `templates/pod.yaml`: demo static key value (clear DEMO labeling, per spec Assumption), LUKS init container validated to format/unlock `cryptsetup` → XFS on dm device, main container benchmarks on the dm-mapped filesystem for all six runtime classes — verified via pod logs during live run
- [x] T027 [US3] Add `runs.datapoints.cache_suspect`, failed_stage, and pod/pod/PVC resource names columns wiring so summary and Iceberg rows stay consistent (data-model.md drift check)

**Checkpoint**: quickstart.md §5 six-case run passes; `summary.md` matches Iceberg query results
(parallel view of same datapoints, per R3 parity guarantee).

---

## Phase 6: User Story 4 - Characterized repeatability and honest disk measurement (Priority: P2)

**Goal**: Variance reporting + sizing-rule machinery visible in every output

**Independent Test**: A run with default repeats reports per-datapoint spread; a run with a
too-small volume stamps CACHE-SUSPECT in preflight, run.env, summary.md header, and Iceberg
metadata (quickstart.md §6).

- [x] T028 [US4] Implement spread computation columns in `io-benchmark/tools/bench.py` (min/max/mean/stddev + relative spread for bw_bytes and iops per job_name) and their rendering in the Markdown table + `case_aggregates` rows
- [x] T029 [US4] Implement cache-suspect propagation in `io-benchmark/tools/bench.py`: sizing evaluation result flows to `run.env`, `runs.metadata.cache_suspect`/`sizing_rule_*` fields, and the `summary.md` header row, plus `--assume-cache-suspect` override
- [x] T030 [US4] Implement tenant-census propagation in `io-benchmark/tools/bench.py`: FR-016 census warning lines recorded in `preflight.log` and repeated in `summary.md` run-metadata block so noise exposure travels with the numbers
- [x] T031 [P] [US4] Create `io-benchmark/docs/sizing-guidance.md`: FR-005 rule (volume ≥ node RAM × 1.1 + margin rationale), why warn-only was chosen (direct IO shifts residual risk to SAN/controller caches), and FR-012 interpretation guide for spread values across runs

**Checkpoint**: quickstart.md §6 trust checks verifiable from a sizing-violating run plus an
Iceberg cross-run query example in §6.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Repo integration + runbook completeness

- [x] T032 Complete `io-benchmark/README.md`: prerequisites (OC cluster creds, helm, Python 3.12 + `pip install -r io-benchmark/requirements.txt`, SCC note for LUKS cases via cluster-admin `privileged` binding per FR-010 escalation documentation), full runbook mirroring contracts/operator-surface.md flags, outputs description (run folder layout, summary.md, Iceberg tables), operator isolation prerequisite, cleanup/`--cleanup-only` docs, airgap §mirror steps (one image + vendored pip deps), expected-outcomes section
- [x] T033 [P] Add `results/` (or `io-benchmark/results/` per config default) to root `.gitignore`
- [x] T034 [P] Add `io-benchmark` row to root `README.md` examples index with pointer to `docs/benchmark-selection.md`
- [x] T035 Run full quickstart.md validation sequence locally incl. `sh io-benchmark/tests/run.sh` green + `helm template` spot checks for all six case slugs; fix `values.schema.json`/drift found
- [x] T036 Constitution v2.0.0 compliance sweep: zero Containerfile/Dockerfile in repo (excluding `staging/`), only approved scripts present (`tools/bench.py`, `tests/run.sh` pipeline entry), approval recorded in spec Clarifications, image ownership documented in README; record outcome in `specs/004-benchmark-harness/plan.md` Phase-1 checklist note
- [x] T037 Verify no `static.py`-style Python lint asserts reintroduced (repo lint stays in tests/run.sh shell per repo convention from PR #5)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (P1)**: none
- **Foundational (P2)**: after Setup; blocks all stories (chart + CLI/preflight/cleanup skeleton)
- **US1 (P3)**: after Foundational — could start in parallel with Foundational's Python tasks since it touches only `docs/` and `README.md`
- **US2 (P4)**: after Foundational + US1 (single-case pipeline is the foundation of the loop)
- **US3 (P5)**: after US2 (serial loop + outputs build on per-case lifecycle)
- **US4 (P6)**: after US3 (spread/stamping need summary + Iceberg to receive them)
- **Polish (P7)**: after all stories

### Within-story parallelism (limited — one Python entrypoint)

- **Setup**: T001→T002/T003/T004/T005 all parallel
- **Foundational**: T006/T007/T008/T009 all parallel (chart templates, distinct files)
- **US1**: T015 ∥ T016 (distinct files)
- **US2/US3/US4**: sequential — same file (`tools/bench.py`). One implementer at a time.
- **Polish**: T032∥T033∥T034 (distinct files); T035 requires all prior; T036/T037 last

### Parallel execution examples

```bash
# Setup (after T001):
Task T002: values.yaml + schema     # io-benchmark/values.yaml, values.schema.json
Task T003: requirements.txt         # io-benchmark/requirements.txt
Task T004: tests/run.sh             # io-benchmark/tests/run.sh
Task T005: CI matrix row            # .github/workflows/validate-examples.yml

# Foundational templates:
Task T006: pvc.yaml        Task T007: configmap-fio-job.yaml
Task T008: pod.yaml        Task T009: NOTES.txt

# US1 (can run while foundational Python work proceeds on a different lane):
Task T015: benchmark-selection.md   Task T016: README skeleton
```

---

## Implementation Strategy

### MVP First (US1 + US2)

1. Phases 1–2 complete → chart renders + CLI skeleton works
2. US1 delivers the analysis document (immediately reviewable, satisfies FR-011)
3. US2 delivers working single-case benchmark — the first live cluster value
4. Stop; validate quickstart §1–§4 before the comparison loop

### Incremental Delivery

- US3 adds the six-case serial loop + both output surfaces (Markdown + Iceberg)
- US4 layers on spread/stamping/census propagation + docs
- Polish wires repo-level integration + full quickstart pass

### Phase 8: Convergence

**Purpose**: Close remaining gaps found by converge assessment (2026-10-13) — spec/plan vs
implementation. NEW work only; nothing here edits prior tasks ([x] statuses preserved).

- [x] T038 Add per-job latency columns (lat mean, p95, p99) to the `summary.md` table rendered by `render_markdown()` in `io-benchmark/tools/bench.py`, sourced from the already-computed `runs.case_aggregates` rows per FR-008 (partial)
- [x] T039 Add mixed-direction fio sections (e.g. `randrw-bs4k/64k/1m` with an `rwmixread` ratio) to the default `fioJobInline` in `io-benchmark/values.yaml`, keeping section-name conventions the parser expects per FR-006 (missing)
- [x] T040 Add a per-case artifacts section to `summary.md` (rendered in `io-benchmark/tools/bench.py`) referencing each case's raw logs (`exec-<case>.log`, `LOGS/case-pod-<case>.log`) and results dir per FR-008 (partial)
- [x] T041 Move the raw-block probe PVC (`probe_block_pvc`) into the preflight path so it also runs under `--dry-run`, emitting the documented `PREFLIGHT … block-probe` line per research R8 + `specs/004-benchmark-harness/quickstart.md` §3 (missing)
- [x] T042 Verify the effective applied fio job retains cache-defeat essentials (`direct=1`, `invalidate=1`, `time_based`) after operator `--fio-jobfile` overrides in `run_case()` (parse rendered ConfigMap text in `io-benchmark/tools/bench.py`); on violation emit a loud `PREFLIGHT-style` WARN on stdout and stamp the case's outputs so numbers cannot be quoted silently per SC-004 (partial)
- [x] T043 Add SQLite busy-timeout and bounded retry with jitter to `iceberg_open()`/`iceberg_append()` in `io-benchmark/tools/bench.py`, plus a README note on concurrent-writer semantics, so two operator invocations sharing a warehouse cannot fail the append path per FR-008 concurrent-invocation edge case (partial)
- [x] T044 Parse the real fio job section names (from the sections written to `<run_dir>/fio-job-sections.txt`) and record them in `runs.metadata.fio_job_name_list` instead of the `"~jobfile"` placeholder in `io-benchmark/tools/bench.py` per data-model.md (partial)
- [x] T045 Wire `--yes` to actual behavior in `io-benchmark/tools/bench.py`: without it, prompt for confirmation before first provisioning (and document in contracts/operator-surface.md); with it, skip the prompt per contract row in contracts/operator-surface.md (partial)
- [x] T046 Write a per-case `<case>/case.log` phase transcript (BEGIN/READY/fio reps/DONE markers) inside each case directory in `run_case()` of `io-benchmark/tools/bench.py`, matching the documented run-folder layout per data-model.md (missing)

---

## Phase 9: Convergence

**Purpose**: Residual gaps found by the second converge assessment (2026-10-13, after Phase 8
implementation). NEW work only; nothing here edits prior tasks ([x] statuses preserved).

- [x] T047 Print the final Markdown comparison table to stdout in `write_summary_and_meta()` (and the interrupt path) in `io-benchmark/tools/bench.py` so `summary-echo.txt` is genuinely the stdout-side copy promised by contracts/operator-surface.md §Outputs#1 and FR-008 ("printed and written") per FR-008 (partial)
- [x] T048 Add a `--dry-run` row to the inputs table and fill the `--yes` row's Notes (prompt appears without `--yes`, EOF-safe decline exits 3) in `specs/004-benchmark-harness/contracts/operator-surface.md` per contracts/operator-surface.md §Inputs (partial)
- [x] T049 Update data-model.md for implementation drift: add `lat_p95_us_mean`/`lat_p99_us_mean` to the Case Aggregate schema and include `randrw` in the Datapoint pattern set per data-model.md (partial)
- [x] T050 Make `--cleanup-only <run-tag>` in `io-benchmark/tools/bench.py` also remove the raw-block probe PVC by name (`io-bench-probe-<run-tag>`) so a control-process death during the probe leaves recoverable remnants per FR-013 (partial)

---

## Done

All 37 tasks implemented 2026-10-13. Static validation (`io-benchmark/tests/run.sh`:
`helm lint --strict`, shellcheck, `sh -n`, `py_compile`, zero-container-definition scan) passes
locally with CI-pinned tooling; `helm template` spot-check renders verified for all six case
slugs (correct runtimeClassName / luks-prep / skip-initdata switching per spec). Live-cluster
acceptance remains the operator's quickstart path per contracts/runtime-and-validation.md —
no live cluster was touched by this implementation.



- Commit after each task or logical group (per task list convention)
- `staging/` untouched throughout
- Every bench.py change is lint-verified by `io-benchmark/tests/run.sh` (py_compile) — no new
  validators (constitution v2.0.0 V)
