# Research: IO Benchmark Harness

**Date**: 2026-10-13 · **Feature**: [spec.md](spec.md) — decisions R1–R10 (plus R2b) resolve every unknown for implementation planning. R1 is also the formal deliverable of **US1 / FR-011** (benchmark tool selection analysis, binding on the implementation). Decisions were updated 2026-10-13 for constitution v2.0.0 and spec FR-017/FR-018: R2b added (existing `perf-utils` image instead of building a fio image), R3 revised (approved local Python tool instead of a fio-summarizer image), R8/R9 adjusted accordingly.

## R1 — Benchmark tool selection (fio vs sysbench vs dbench) — US1/FR-011 deliverable

**Decision**: **fio 3.x** is the single benchmark tool carried by the harness end-to-end.

**Criteria** (drawn from spec FR-006/FR-007/FR-009 and the confidential-IO context):

| Criterion | fio 3.x | sysbench (fileio) | dbench |
|---|---|---|---|
| Purpose | Flexible I/O tester for Linux I/O subsystem — block devices and files | DB/system benchmark suite; `fileio` is one bundled sub-test | NetBench-style SMB client load generator for file servers |
| Direct/raw block-device support | Yes — first-class (`filename=/dev/...`, `filetype=block`, `direct=1`) | No direct block device mode; files only | No — SMB protocol only, targets shares |
| Block-size spectrum control | Full, per-job (`bs=4k…1M`, ranges, `bssplit`) | Coarser (one file-block-size per run) | Fixed NetBench traffic profile, not bs-configurable |
| Cache-defeat mechanisms | `direct=1`, `io_submit_mode=offline`, `invalidate=1`, `norandommap`, explicit `fsync`/`fdatasync` control | `--file-extra-flags=direct` only | N/A for device benchmarking |
| Output for parsing | Native `--output-format=json` (json/json+) with lat percentiles, clat buckets, target engines | Human text; no JSON | Human text |
| Queue-depth scaling | Async engines (`libaio`, `io_uring`) with `iodepth` | Thread-based sync I/O | N/A |
| Steady-state handling | `ramp_time`, `time_based`+`runtime`, per-job isolation (`stonewall`) | `--warmup-time` | N/A |
| Maintenance / provenance | Jens Axboe + Vincent Fu; versions to 3.42+; packaged in Fedora/EPEL; de-facto block benchmark standard | Slower cadence, DB-oriented roadmap; fileio secondary | Historic Samba tooling; niche |
| Container/kek carriers | Buildable statically-linked-ish on UBI (EPEL fio rpm or source); small image | Bigger dependency surface; fileio less exercised | Large runtime surface; requires share infra |
| Airgap suitability | Single binary pin, deterministic job file | Similar binary availability, but capability insufficient | Requires SMB server counterpart — new infra |

**Why this matters for the decision**: The feature measures **device/storage IO in confidential vs plain pods**, comparing runs with a stable, parseable, cache-bypassing methodology. fio is the industry reference tool for exactly this measurement; sysbench's `fileio` cannot address raw block devices at all and dbench models a protocol workload against a server — neither can satisfy FR-005..FR-008's requirements (device-level direct IO, bs ladder, machine-parseable output).

**Alternatives considered and rejected**:

- **sysbench (fileio)** — respected, but DB-centric; `fileio` supports only filesystem files (no block-device targets), coarser block-size control, no structured output. Using sysbench for *both* CPU and IO was attractive to the earlier vertical-scaling idea, but FR-014 clarifies vertical sweeps are out of scope, so this argument doesn't carry. Documented as a possible future cross-check for filesystem-path workloads.
- **dbench (as-is / wrapped / forked)** — dbench is a Samba/NetBench *protocol* load generator. As-is: requires an SMB share to target, which is server-side infrastructure, not pod storage. Wrapped/forked: wrapping adds an SMB server requirement inside the cluster (new dependency, new failure surface, and measures SMB caching and network on top of storage); forking to remove the protocol layer discards everything dbench is — what remains is a custom C benchmark reimplementing fio's core. Rejected on all three permutations.
- **Custom synthetic benchmark** — poorest credibility/reproducibility; unnecessary with fio available.

**What would change the decision**: (a) fio loses device-level/direct-IO capability or JSON output; (b) the measurement goal shifts from storage IO to protocol/DB behaviour (→ sysbench/dbench territory); (c) an enterprise requirement to measure under a *specific* application engine (e.g., RocksDB via db_bench) — in those cases a second, purpose-specific tool is adopted alongside fio under the same contract, not as a replacement.

## R2 — Execution model: in-pod `oc exec` repeats

**Decision**: The benchmark pod's main container idles (`sleep infinity`-style); the approved Python control tool (R3/FR-018) drives each fio repeat via bounded `oc exec` calls into the pod and collects fio JSON output. Repeats are separate exec invocations (default 3 per datapoint-job invocation).

**Rationale**: (1) separation of storage preparation from measurement — prep runs once at pod start, measurements are ephemeral; (2) per-repeat isolation makes each repeat independently timed and individually retrievable, matching FR-015 spread computation without cross-repeat contamination; (3) failure isolation — a hung/crashed fio exec marks the repeat failed while pod and remaining repeats survive; (4) it mirrors the iteration approach validated by the earlier staging runner without inheriting its Python.renders. `oc exec` timeout = per-job estimated time × safety factor (computed from job runtime + ramp, configurable).

**Alternatives considered**: fio as pod main-load with `--loops=N` (couples repeats to pod lifecycle; a single fio crash fails the case); copying fio JSON out with `oc cp` after a sleep main (same but awkward state handoff); in-pod sidecar exposing an HTTP API (violates no-server simplicity).

## R2b — In-pod tooling image

**Decision**: The benchmark pod (main container, and the LUKS init container for encrypted cases) runs the existing, externally-built `quay.io/rh-ee-chbutler/perf-utils` image — built outside this repository from `butler54/containers` `standard-quay/perf-utils` (UBI9-based; verified to contain fio 3.42+, sysbench, stress-ng; xfsprogs + cryptsetup present for the encrypted-case preparation path). This feature defines and builds **zero** container images (constitution v2.0.0 IV / FR-017); the reference is a documented default consumed as an override-capable operator input (FR-003/FR-009).

**Rationale**: the image already exists and covers the complete pod-side toolset; earlier drafts of this plan specified dedicated `fio` and `fio-summarizer` images, both removed — fio needs no new image, and summarization moved into the approved local Python tool (R3). Ownership and provenance of the image are recorded in the example README per constitution IV.

## R3 — Summarization and Iceberg authoring (approved local Python tool)

**Decision**: All control-side logic — serial case orchestration, per-repeat exec driving, log collection, fio JSON parsing/normalization, Markdown table emission, and Iceberg appends — lives in one **explicitly-approved Python tool** (`io-benchmark/tools/bench.py`; FR-018) running on the operator's control machine, with pinned dependencies (PyIceberg + PyArrow, `requirements.txt`). Markdown table and Iceberg appends are produced by the same parse pass, guaranteeing human/machine parity. The Iceberg store uses a **SQL (SQLite) catalog** backed by a local warehouse directory — fully file-local, no services.

**Rationale**: Iceberg authoring genuinely requires PyIceberg; scripting is permitted because it was **explicitly approved in advance** and recorded in the spec Clarifications (constitution v2.0.0 II). One approved tool owning the whole control flow replaces the earlier plan's two-part design (shell orchestrator + external `fio-summarizer` image), which was superseded when the constitution moved to v2.0.0 and FR-017/FR-018 were added.

**Alternatives considered**: external `fio-summarizer` container image (superseded — would need the repo to depend on a prescribable image pipeline, which constitution v2.0.0 IV now forbids, and adds a second runtime and an airgap mirroring burden); pure-shell parsing of fio JSON + hand-rolled Iceberg writes (unsafe and technically infeasible for Iceberg); a REST/JVM catalog service (disproportionate to a local-folder requirement).

## R4 — Iceberg layout and schemas

**Decision**: One warehouse dir `<results-root>/iceberg-warehouse/` shared across runs; one SQLite catalog file alongside it; three tables (see data-model.md §Iceberg): `runs`, `case_iterations`, `datapoints`, partitioned/acquired as appends keyed by `run_id`. Markdown table is regenerated from the appended state each invocation so the human view and store never diverge.

## R5 — Case catalog and pod topology

**Decision**: Exactly six cases with canonical slugs executed in fixed order — `plain`, `plain-luks`, `kata`, `kata-luks`, `coco`, `coco-luks`. Each case = one `helm template` render of the io-benchmark chart (PVC[Block] + Pod) applied with `oc apply`, then serial run-to-deletion.

Pod structure (single template, case-switched by values): main container (perf-utils image, idles, runs fio on `oc exec`), for encrypted cases a LUKS helper **init** container (same image) that formats/unlocks and exits, leaving an activated dm-crypt device visible to the main container via the shared device view, XFS formatted by the init as well — mirroring the block-storage examples' guest-side treatment in its insecure-static demonstration mode (per spec Assumption). Node placement via `nodeName`; TDX-runtime checks only for `kata*`/`coco*` cases.

**Alternatives considered**: sidecar-helper mount-namespace handoff + `/proc/PID/root` probe (used in storage examples) — heavier; serialising each case as separate charts — redundant.

## R6 — Guest-side LUKS pattern (encrypted cases)

**Decision**: Reuse the block-storage-encrypted example's guest-side LUKS+XFS preparation pattern in **insecure-static-key demonstration mode** (key held as in-run secret material passed via values/secret reference with clear DEMO labelling). No Trustee/attestation involvement: steady-state IO measurements are identical post-unlock, and attestation was explicitly deprioritised in spec clarifications.

**Rationale**: spec assumption explicitly authorised static-demo-key simplification; reusing the existing example's sequence keeps documentational coherence across the ensemble.

**Open questions parked as documented risks**: fio containers running root-level LUKS operations require pod `privileged`/`SYS_ADMIN` — mitigated by documenting minimum-capability need in README and allowing the operator to bind a dedicated SCC, matching how block-storage examples handle escalation (FR-010).

## R7 — Cache-defeat methodology

**Decision**: (a) fio `direct=1` on all jobs (bypasses host *and* guest page cache at the block layer); (b) `invalidate=1` (default) flushes inode cache before start; (c) write-preconditioning ramp (`ramp_time`) so sequential/rand numbers aren't influenced by allocation-on-write state of a fresh thin device; (d) FR-005 volume ≥ node RAM + margin captured as a **pre-flight warning path** (per clarification Q3: warn-proceed, stamp cache-suspect on all outputs) since host page-cache isn't the residual risk once direct IO is used — the sizing rule protects against SAN/controller and pod-level caching effects; (e) `norandommap=0`/`random_generator=tausworthe64` defaults for offset randomization.

**Rationale**: With direct IO, the "volume ≥ node RAM" rule's *enforcement* strength matters less than its *visibility*; the user explicitly chose warn-only. Job-level defenses do the measurement-honesty work.

## R8 — Isolation & preflight

**Decision**: preflight (implemented inside `bench.py`) performs: cluster reachability; node existence/schedulability; runtimeClass presence per selected cases (warn/fail per case type); runtime class ⇄ TDX cross-check for `coco` cases (`kata-cc` runtimeClass presence is the operational proxy — explicit TDX hardware detection via node debug is NOT auto-run, but is executed if `--coco-validate=strong` opt-in); raw-block capability probe (a bound-test tiny PVC with `volumeMode: Block` in the run namespace, deleted immediately); node memory read (for FR-005 sizing rule evaluation); tenant census (non-system pods on target node → loud warning per FR-016); tool-side prerequisites (`oc`, `helm`, python deps import check, results-root writability); image-override reminder.

All preflight outputs are fixed-format lines (`PREFLIGHT <OK|WARN|FAIL|CACHE-SUSPECT> <check> <detail>`) so runs can be logged/compared.

## R9 — Serial execution, naming, lifecycle

**Decision**: run ID = UTC timestamp + operator tag (`<utc-%Y%m%dT%H%M%SZ>-<case-tag>`); resource names `io-bench-<run-tag-truncs>-<case>`; strict sequential case loop with per-case `helm template → oc apply → wait → exec-loop → collect → oc delete -f → cleanup-verify` phases; Python `try/finally` + signal handlers run the per-case delete path on EXIT/INT/TERM; `bench.py --cleanup-only <run-tag>` re-executes remnant deletion deterministically (documented in README for control-machine-death recovery, per FR-013). Iceberg/Markdown summarization runs after each completed case (append mode) and once at end (full table regen).

## R10 — Timeouts and waits

**Decision**: all `oc` operations bounded: provision wait scales with volume size (`max(10m, volumeGiB×0.5m)` heuristic, documented), PVC bind ≤15m, pod Ready ≤15m, fio exec timeout = (ramp+runtime)×sections×1.5 rounded +10m floor, node-debug checks ≤2m each, delete waits ≤10m per resource with `--timeout` + final poll. Every timeout breach marks the case failed (recorded in summary) and moves to cleanup; never leaves pending orphans.

---

### Sources

- fio 3.42 documentation (fio.readthedocs.io) — job parameters (direct, bs, runtime, ramp_time, iodepth, invalidate), `--output-format=json`, engine model.
- sysbench README (github.com/akopytov/sysbench) — benchmark suite scope (oltp/fileio/cpu/memory/threads/mutex), fileio limitations (files only, prepare-stage files, no device mode).
- dbench (Samba project) — NetBench protocol load generator description; wrap/fork permutations assessed from source scope.
- `butler54/containers` `standard-quay/perf-utils/Containerfile` (verified 2026-10-13: UBI9 base + fio, sysbench, stress-ng, EPEL-gated install) — the single in-pod tooling image (R2b); published as `quay.io/rh-ee-chbutler/perf-utils`.
- Repo prior art: `staging/fio-script/` (fio case grid, timeouts, cleanup traps), block-storage-encrypted example (LUKS+XFS guest-side pattern, initdata handling), kbs-client/memory-security examples (image override patterns, initdata precedence).
