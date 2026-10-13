# io-benchmark

Serial, cache-defeating IO benchmark harness comparing plain pods, kata
sandbox pods, and confidential (coco) pods — each with and without the same
guest-side LUKS+XFS storage treatment used by the repository's
encrypted-storage example. One nominated node, one storage class, one
container size per run; results land in a Markdown table **and** self-
describing Apache Iceberg tables on the control machine.

## Before you benchmark: why fio owns every number here

Tool selection was a deliberate decision, not inertia from the earlier
iteration. **[`docs/benchmark-selection.md`](docs/benchmark-selection.md)**
analyzes fio vs sysbench (`fileio`) vs dbench (as-is / wrapped / forked)
against the harness's stated needs, selects **fio** as the only tool, and
states exactly what would change the decision (US1 / FR-011).

## External image (ownership per constitution v2.0.0 IV)

The benchmark pod runs **`quay.io/rh-ee-chbutler/perf-utils`** — built and
published **outside this repository** from the `butler54/containers` repo
(`standard-quay/perf-utils` Containerfile; UBI9-based, ships fio 3.42+,
sysbench, stress-ng). This repository defines and builds **zero** container
images. Override with a mirror/pinned digest via `--workload-image` /
`--set images.workload=...`.

## Prerequisites

| Need | Why | Notes |
|---|---|---|
| `oc` cluster login, permission to create Pod/PVC/ConfigMap in the namespace | all case operations | For LUKS/`privileged` pods the namespace's SA needs a `privileged`-capable SCC binding (cluster-admin action, FR-010 escalation documentation) |
| `helm` v3 | chart rendering | |
| Python 3.12 on control machine | approved tool | `pip install -r io-benchmark/requirements.txt` (pins: pyiceberg, pyarrow) |
| Nominated **isolated** node | FR-016 prerequisite — harness never cordons/evicts | Drain tenant workloads and system daemons aside; harness census-warns only |
| Storage class supporting `volumeMode: Block` | raw-block benchmark device | Hostpath-csi and similar filesystem-only classes do not work (preflight probe catches this) |
| `kata` / `kata-cc` runtime classes | for kata/coco cases | Only checked when those cases are selected |
| Airgapped environments | FR-009 | Mirror the one workload image; supply it via `--workload-image`. Vendor the pinned Python deps per your environment. |

## Running

Single command, serial cases, at most one benchmark pod ever exists:

```sh
python3 io-benchmark/tools/bench.py \
  --node worker-1 --storage-class my-sc \
  --volume-size 512Gi --pod-cpu 4 --pod-mem 8192Mi \
  --run-tag gauntlet-1 --yes
```

Common variants:

```sh
# Preflight only (nothing provisioned):
python3 io-benchmark/tools/bench.py --dry-run --node worker-1 --storage-class my-sc

# Single case / subset (canonical order kept):
python3 io-benchmark/tools/bench.py --node worker-1 --storage-class my-sc --cases plain
python3 io-benchmark/tools/bench.py --node worker-1 --storage-class my-sc --cases kata,coco-luks

# Custom fio job file (sections override; [global] with direct=1 stays baked):
python3 io-benchmark/tools/bench.py --node ... --fio-jobfile myjobs.fio

# Airgap mirror:
python3 io-benchmark/tools/bench.py --node ... \
  --workload-image registry.internal/perf-utils@sha256:<pinned>

# Left-by-control-machine-or-crash recovery (deterministic):
python3 io-benchmark/tools/bench.py --cleanup-only gauntlet-1
```

Every flag maps one-to-one to run inputs — see
`specs/004-benchmark-harness/contracts/operator-surface.md` for the full
surface and exit codes (`0` ok, `1` preflight, `2` case failure, `4` leftover
cleanup failed).

## What you get

```text
results/<run-tag>/
├── run.env                        # resolved operator inputs (sans secrets)
├── preflight.log                  # fixed-format PREFLIGHT lines
├── manifest-<case>.yaml           # exactly what was applied, per case
├── exec-<case>.log                # orchestration transcript per case
├── <case>/rep<N>/fio.json         # raw fio JSON per repeat
├── LOGS/case-pod-<case>.log       # pod logs collected before delete
├── summary.md                     # human table (BW/IOPS + spread per job)
└── summary-echo.txt

results/iceberg-warehouse/         # shared across runs (FR-008)
├── runs.metadata                 # one row per invocation (incl. cache_suspect)
├── runs.case_iterations          # one row per case run
├── runs.datapoints               # per (case, repeat, job)
└── runs.case_aggregates          # per (case, job): min/max/mean/stddev + spread
```

The same datapoints feed both surfaces, so quoted numbers from `summary.md`
always trace to the store. Query cross-run comparisons with any Iceberg
reader (duckdb, pyiceberg, Spark). Two concurrent runs against the same
`results/` root are safe: writes are run-scoped appends identified by
`run_id`, and the tool absorbs concurrent-writer lock contention (SQLite
`busy_timeout=5000` + bounded retry with jitter, FR-008 concurrent edge case).
Expected evidence for a successful run:
`PREFLIGHT OK sizing-rule`, `CASE <slug> DONE` for all six cases, exit 0,
six (or `--cases`-count) rows in the summary, no leftover pods/PVCs on the
cluster.

## Interpreting numbers (must-read before quoting)

Read [`docs/sizing-guidance.md`](docs/sizing-guidance.md) **before** quoting
results. The sizing rule (volume ≥ node RAM × 1.1) is enforced warn-only —
violations stamp every artifact `CACHE-SUSPECT`, never abort the run.

## Cleanup

Normal runs delete each case's Pod/PVC/ConfigMap and verify deletion
(FR-013). Interruption (Ctrl-C) runs the same delete path from the tool's
signal handler. If the control machine dies mid-run:

```sh
python3 io-benchmark/tools/bench.py --cleanup-only "<run-tag-you-used>"
```

`--cleanup-only` returns exit 0 (clean) or 4 (resources remain — re-run it or
delete by label `io-benchmark/run-tag=<tag>`). **No upgrade/migration story**
— delete and recreate is the lifecycle.

## Non-goals (per spec)

Not a multi-node/distributed benchmark, not CPU/memory/net benchmarking, not
attestation/key-delivery ceremony (demo static LUKS key is deliberate and
labelled), no CI regression gating on numbers.
