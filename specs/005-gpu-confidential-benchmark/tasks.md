---
description: "Task list for feature 005-gpu-confidential-benchmark"
---

# Tasks: GPU Confidential Benchmark

**Input**: Design documents from `/specs/005-gpu-confidential-benchmark/`

**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: No TDD test tasks requested. CI lint/validation wiring (constitution V) is included as delivery tasks; live benchmark correctness is verified by the operator via the quickstart scenarios.

**Organization**: Tasks grouped by user story; each story is independently implementable and testable per spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- All paths are relative to repository root; the example lives in `gpu-benchmark/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the self-contained example directory and its documentation skeleton (constitution I).

- [x] T001 Create the `gpu-benchmark/` directory skeleton per plan.md: `Chart.yaml` (apiVersion v2), empty `values.yaml`, `templates/`, `docs/`, `tests/`, `benchmarks/`, `tools/`
- [x] T002 [P] Author `gpu-benchmark/docs/benchmark-selection.md`: HPL (fp64) + HPL-MxP (mixed) selection rationale, NVIDIA HPC-Benchmarks source, rejected alternatives, and what would change the decision (FR-003; mirrors io-benchmark's fio decision record)
- [x] T003 [P] Author `gpu-benchmark/docs/sizing-guidance.md`: problem-size `N` formula (memory-fill fraction × aggregate GPU memory), default `NB`/`P`/`Q` derivation from GPU count, quoting rules (research R6)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Chart, catalog loader, preflight, and serial case engine that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Implement the declarative benchmark-catalog loader in `gpu-benchmark/tools/bench.py`: enumerate `gpu-benchmark/benchmarks/*.yaml`, validate each definition against the catalog schema (id, precision, version, parameter_inputs, command_template, parser, docs_ref), fail preflight with the available catalog listed for unknown ids (contracts/benchmark-catalog.md; research R9)
- [x] T005 [P] Author the two benchmark definitions `gpu-benchmark/benchmarks/hpl.yaml` and `gpu-benchmark/benchmarks/hpl-mxp.yaml` per the catalog contract (metric + residual-check verification parser mapping, command templates `hpl.sh` / `hpl-mxp.sh`, research R1/R8)
- [x] T006 Implement the Helm chart workload in `gpu-benchmark/`: `templates/pod.yaml` (runtimeClassName from values, GPU resource limit, CPU/mem per process, run-tag label `gpu-benchmark/run-tag`), `templates/configmap-hpl-dat.yaml` (rendered HPL parameters), `templates/NOTES.txt`, and the core `values.yaml` keys (case slug, node, images.workload pinned to `nvcr.io/nvidia/hpc-benchmarks:26.02.01`, gpu resource name, gpu count, runtime class, namespace, runTag, hpl params) (research R2/R7)
- [x] T007 Author `gpu-benchmark/values.schema.json` validating the full values contract (required node, gpu-config enum single|full, tier/runtime-class consistency, image reference format) and wire the comprehensive commented `values.yaml` (FR-013, constitution II)
- [x] T008 [P] Author `gpu-benchmark/tests/run.sh` running `helm lint --strict` and values-schema validation; add `gpu-benchmark/tests/requirements.txt` (mirrors io-benchmark/tests)
- [x] T009 Implement preflight in `gpu-benchmark/tools/bench.py`: GFD node-label gates (`nvidia.com/gpu.product` H100-or-newer allowlist with `--gpu-model-allowlist` override, `gpu.count`, `nvlink.present`), runtime-class existence for selected tiers, GPU resource detection (`nvidia.com/gpu` vs `nvidia.com/pgpu`), image-reference check, warn-only GPU-occupancy census; every failure actionable, exit 1, nothing provisioned (FR-002, FR-010, FR-016; research R2/R3)
- [x] T010 Implement the serial case engine in `gpu-benchmark/tools/bench.py`: per-case Helm render/apply with `manifest-<case>.yaml` archiving, at most one benchmark pod at any time, bounded `oc exec` with `exec-<case>.log` transcripts, pod-log collection before delete, deterministic labeled cleanup with deletion verification, `--cleanup-only <run-tag>`, exit codes 0/1/2/4 (FR-009; contracts/operator-surface.md)
- [x] T011 [P] Author `gpu-benchmark/tools/pyproject.toml`: pinned deps (pyiceberg, pyarrow, typer), `gpu-bench` console script entry point (research R4)

**Checkpoint**: Foundation ready — catalog, chart, preflight, and case engine exist and `gpu-benchmark/tests/run.sh` passes; user story implementation can begin.

---

## Phase 3: User Story 1 - Single-GPU fundamental benchmark, confidential vs standard (Priority: P1) 🎯 MVP

**Goal**: Run HPL and HPL-MxP on one NVIDIA GPU in plain and confidential (`kata-cc-nvidia-gpu`) pods with identical parameters; report verified per-case results and the confidential-vs-standard delta.

**Independent Test**: `gpu-bench --node <gpu-node> --gpu-config single --tiers plain,coco --benchmarks hpl,hpl-mxp --run-tag <tag> --yes` completes all four cases serially; `results/<tag>/summary.md` shows verified Gflops per case and the per-benchmark delta; exit 0; no leftover pods (quickstart Scenario 2).

### Implementation for User Story 1

- [x] T012 [US1] Implement parameter computation in `gpu-benchmark/tools/bench.py`: `N` from memory-fill × aggregate GPU memory, `NB`/`P`/`Q` from GPU count, computed once per (benchmark, gpu-config) and reused verbatim across tiers, with `--hpl-n/--hpl-nb/--hpl-p/--hpl-q` and `--memory-fill` overrides applied to all tiers alike (FR-004; research R6)
- [x] T013 [US1] Implement single-GPU case construction in `gpu-benchmark/tools/bench.py`: tier→runtimeClassName mapping (plain `""`, coco `kata-cc-nvidia-gpu`, optional kata `kata-nvidia-gpu`), GPU limit 1, case slug assembly (`hpl-coco-single` etc.), canonical serial ordering (data-model Benchmark Case)
- [x] T014 [US1] Implement result parsing and verification gating in `gpu-benchmark/tools/bench.py`: extract Gflops and residual-check verdict per the catalog parser mapping; mark iterations `verified`/`invalid`/`env-failed` per the case state machine; env/attestation failures reported distinctly, never as performance (FR-007; research R8)
- [x] T015 [US1] Implement assigned-device evidence capture in `gpu-benchmark/tools/bench.py`: record in-pod `nvidia-smi` device identities into `results/<tag>/<case>/rep<N>/` and the result record (FR-005; research R10)
- [x] T016 [US1] Implement the Markdown report in `gpu-benchmark/tools/bench.py`: `results/<run-tag>/summary.md` with `run.env`, per-case table (Gflops, verified status, devices) and the confidential-vs-standard delta table computed only from verified pairs, gaps shown with status never as numbers (FR-008; data-model Comparison Report)
- [x] T017 [US1] Implement Iceberg appends in `gpu-benchmark/tools/bench.py`: `runs.metadata`, `runs.case_iterations`, `runs.datapoints`, `runs.case_aggregates` (min/max/mean/stddev/spread over verified iterations only) under `results/iceberg-warehouse/` (FR-008; research R5)
- [x] T018 [US1] Author `gpu-benchmark/README.md`: prerequisites table (NFD + GPU Operator with CC manager, sandboxed containers operator, H100-or-newer, isolated node, airgap), external image ownership/approval (NVIDIA hpc-benchmarks, mirror fallback), running instructions, interpretation pointer to docs/sizing-guidance.md (FR-011, FR-016; constitution III/IV)

**Checkpoint**: MVP delivered — single-GPU confidential-vs-standard comparison is fully functional and independently testable.

---

## Phase 4: User Story 2 - Full-system multi-GPU benchmark (Priority: P2)

**Goal**: Run the benchmarks on all node GPUs (4/8, NVLink) in one process set per case, confidential vs standard, with the same verified delta reporting.

**Independent Test**: On a 4- or 8-GPU NVLink node, `gpu-bench --node <node> --gpu-config full --tiers plain,coco --run-tag <tag> --yes` uses all GPUs, reports verified multi-GPU results plus delta; on a non-NVLink node preflight rejects with the topology requirement (quickstart Scenario 3).

### Implementation for User Story 2

- [x] T019 [US2] Implement full-system case construction in `gpu-benchmark/tools/bench.py` and chart values: request the full GFD GPU count in the single pod, run `mpirun -np <count>` with one GPU per process, size CPU/mem per MPI process; never silently benchmark a subset (FR-006; research R7)
- [x] T020 [US2] Implement full-system preflight gates in `gpu-benchmark/tools/bench.py`: require `nvidia.com/nvlink.present=true`, surface actual GPU count against the declared expectation with proceed-with-confirmation, reject with the topology requirement otherwise (FR-010; US2 scenarios 2–3)
- [x] T021 [US2] Extend reporting in `gpu-benchmark/tools/bench.py` for full-system rows: per (benchmark, gpu-config=full) delta rows and device evidence for all assigned GPUs, identical `N/NB/P/Q` across tiers (FR-004/FR-008)

**Checkpoint**: User Stories 1 and 2 both work independently; full-system delta measurable.

---

## Phase 5: User Story 3 - Catalog extensibility for a future physics benchmark (Priority: P3)

**Goal**: Adding a benchmark = adding one YAML definition plus docs, with zero changes to existing definitions, chart, runner core, or reporting.

**Independent Test**: Add a placeholder definition to `gpu-benchmark/benchmarks/`; `gpu-bench --dry-run --benchmarks placeholder` discovers it; `helm lint --strict` and existing definitions untouched; remove the placeholder (quickstart Scenario 5).

### Implementation for User Story 3

- [x] T022 [US3] Verify and document the catalog contract mechanically: placeholder-definition discovery via `--dry-run` and `--benchmarks` selection semantics (unselected benchmarks have no effect), definition-schema validation errors for missing parser/verification fields (FR-012; contracts/benchmark-catalog.md)
- [x] T023 [US3] Author the maintainer guide section in `gpu-benchmark/docs/benchmark-selection.md` (or a dedicated `gpu-benchmark/benchmarks/README.md`): how to add a benchmark under the contract, obligations (verification, image carriage, docs), and the HPCG future-candidate note (FR-012; research R9/future-work)

**Checkpoint**: All user stories independently functional; extensibility contract proven.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Cross-story documentation, CI, and end-to-end validation.

- [x] T024 Extend `gpu-benchmark/README.md` with full-system usage, `--cleanup-only` recovery, non-goals (no attestation/Trustee integration, no AI benchmarks, no multi-node), and the testing-only delete-and-recreate lifecycle note (mirrors io-benchmark README conventions)
- [x] T025 [P] Register `gpu-benchmark` in `.github/workflows/validate-examples.yml`: add `gpu-benchmark/**` to both `paths` filters and `gpu-benchmark` to the `chart` matrix (constitution V)
- [ ] T026 Run the quickstart validation scenarios 1–6 from `specs/005-gpu-confidential-benchmark/quickstart.md` on a suitably provisioned cluster and record evidence (SC-001–SC-006)
- [x] T027 [P] Add the `gpu-benchmark` row to the observability/utility examples table in the repository root `README.md`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **User Stories (Phases 3–5)**: Depend on Phase 2 completion
  - US1 first (MVP); US2 depends on US1's case machinery conceptually but only touches the same tool file, so run sequentially (T012–T018 → T019–T021)
  - US3 depends on the Phase 2 catalog loader (T004) and is independent of US1/US2 outcomes
- **Polish (Phase 6)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: After Phase 2 — no story dependencies
- **User Story 2 (P2)**: After Phase 2 + US1 implementation (shares `gpu-benchmark/tools/bench.py`; extend, don't fork)
- **User Story 3 (P3)**: After Phase 2 (catalog loader T004) — independent of US1/US2

### Within Each User Story

- Parameter computation before case execution (T012 → T013)
- Parsing/gating before reporting (T014 → T016/T017)
- Case construction before preflight gates that consume it (T019 → T020)

### Parallel Opportunities

- Phase 1: T002, T003 in parallel (different doc files)
- Phase 2: T005, T008, T011 in parallel (data/docs files, no code deps); T004/T006/T007/T009/T010 share or gate each other via `bench.py`/chart — run sequentially
- Phase 6: T025 and T027 in parallel (different files)
- Note: most US1/US2 tasks touch `gpu-benchmark/tools/bench.py` and are deliberately sequential to avoid same-file conflicts

---

## Parallel Example: Phase 1 + Phase 2 data files

```bash
# Launch documentation tasks together:
Task: "Author gpu-benchmark/docs/benchmark-selection.md (T002)"
Task: "Author gpu-benchmark/docs/sizing-guidance.md (T003)"

# After Phase 1, launch independent data/tooling files together:
Task: "Author gpu-benchmark/benchmarks/hpl.yaml + hpl-mxp.yaml (T005)"
Task: "Author gpu-benchmark/tests/run.sh (T008)"
Task: "Author gpu-benchmark/tools/pyproject.toml (T011)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: quickstart Scenario 2 (single-GPU comparison) end-to-end
5. Demo-ready: confidential-vs-standard GPU cost measurement

### Incremental Delivery

1. Setup + Foundational → catalog/chart/preflight/engine ready
2. Add User Story 1 → validate independently → **MVP**
3. Add User Story 2 → validate full-system on an NVLink node
4. Add User Story 3 → prove the catalog contract with a placeholder
5. Polish → CI registered, READMEs complete, quickstart evidence recorded

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- Tasks touching `gpu-benchmark/tools/bench.py` are sequenced deliberately (single-file conflict avoidance)
- The one executable script (`bench.py`) is pre-approved by spec FR-015; benchmark catalog entries are declarative data, not scripts (constitution II)
- Commit after each task or logical group; stop at any checkpoint to validate the story independently

---

## Phase 7: Convergence

- [x] T028 Add a best-effort workload-image availability check to preflight in `gpu-benchmark/tools/bench.py`: warn-only reachability probe where tooling permits (e.g., `skopeo`/`oc image` when available), hard-fail on malformed or unpinned references, actionable message pointing at `--workload-image` on failure per FR-010 (partial)
- [x] T029 Reclassify benchmark exec failures in `gpu-benchmark/tools/bench.py` `run_case` (rc != 0 or missing output) as `env-failed` with stage `bench-exec` instead of leaving the case at `invalid`/`no-iterations`, so never-ran cases are reported as environment problems and never conflated with numerical-verification failures per US1/AC3 and the data-model case state machine (partial)
- [x] T030 Document exit code 3 (usage error / operator abort) alongside 0/1/2/4 in `specs/005-gpu-confidential-benchmark/contracts/operator-surface.md` and the `gpu-benchmark/README.md` exit-code list to match `gpu-bench` behavior per contracts/operator-surface.md (partial)

