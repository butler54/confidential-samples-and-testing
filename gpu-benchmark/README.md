# gpu-benchmark

Serial GPU LINPACK benchmark harness comparing **standard (plain) pods** and
**confidential (`kata-cc-nvidia-gpu`) pods** on NVIDIA **H100-or-newer**
GPUs — single-GPU and full-system (all node GPUs over NVLink) — with
verification-gated results and an explicit confidential-vs-standard delta.
Mirrors the `io-benchmark` harness (spec
[005-gpu-confidential-benchmark](../specs/005-gpu-confidential-benchmark/spec.md)).

## Before you benchmark: what runs and why

**NVIDIA HPL** (fp64 LINPACK) and **NVIDIA HPL-MxP** (mixed-precision
LINPACK) own every number here. **[`docs/benchmark-selection.md`](docs/benchmark-selection.md)**
records why these two were selected, what was rejected, and what would
change the decision (FR-003). Read **[`docs/sizing-guidance.md`](docs/sizing-guidance.md)**
before quoting results — full-fill LINPACK runs take **hours by design**;
use `--hpl-n` for smoke runs.

## External image (ownership per constitution v2.0.0 IV)

The benchmark pod runs NVIDIA's already-published **HPC-Benchmarks
collection** — `nvcr.io/nvidia/hpc-benchmarks:26.02.01` (HPL 26.02.01,
HPL-MxP 26.02, NCCL 2.29.2, MPICH-ABI-compatible MPI), owned and published
by NVIDIA. This repository defines and builds **zero** container images.
Override with a mirror/pinned digest via `--workload-image` / `--set
images.workload=...` (FR-017); if NGC pull authentication is blocked in your
environment, mirror the image to an externally owned registry — the
repository takes no supply-chain ownership of it (perf-utils pattern,
research R1).

## Prerequisites

| Need | Why | Notes |
|---|---|---|
| `oc` cluster login, permission to create Pod/ConfigMap in the namespace | all case operations | No privileged SCC binding needed — GPU assignment flows through the device plugin, unlike io-benchmark's raw-block cases |
| `helm` v3 | chart rendering | |
| Python 3.12 on control machine | approved tool (spec FR-015) | `pip install ./gpu-benchmark/tools` (pyproject declares+pins: pyiceberg, pyarrow, typer, pyyaml; installs the `gpu-bench` console script) |
| Bare-metal node with **NVIDIA H100-or-newer** GPUs | FR-002 | Older GPUs — including other NVIDIA models — are rejected at preflight: only H100-and-newer support confidential GPUs |
| NFD + **NVIDIA GPU Operator** (with CC manager) | GPU serving + GFD labels + CC mode | Provides the node labels preflight gates on (`nvidia.com/gpu.product`, `gpu.count`, `gpu.memory.total`, `nvlink.present`) |
| **OpenShift sandboxed containers** operator | confidential tier | Creates the `kata-cc-nvidia-gpu` (confidential) and `kata-nvidia-gpu` (kata) runtime classes |
| Nominated **isolated** node | FR-009 | Harness census-warns only; never cordons/evicts — drain tenant workloads yourself |
| NVLink interconnect | full-system cases | `--gpu-config full` is rejected at preflight without it |
| Airgapped environments | FR-017 | Mirror the workload image; supply it via `--workload-image`. No startup downloads. |

## Running

Single command, serial cases, at most one benchmark pod ever exists:

```sh
gpu-bench --node worker-gpu1 --gpu-config single \
  --tiers plain,coco --benchmarks hpl,hpl-mxp \
  --run-tag qs-1 --yes
```

Common variants:

```sh
# Preflight + parameter preview only (nothing provisioned):
gpu-bench --dry-run --node worker-gpu1

# Full-system on a 4/8-GPU NVLink node:
gpu-bench --node worker-gpu8 --gpu-config full --expect-gpu-count 8 \
  --benchmarks hpl --run-tag full-1 --yes

# Smoke run (small problem, non-representative numbers — see sizing guidance):
gpu-bench --node worker-gpu1 --hpl-n 20000 --run-tag smoke-1 --yes

# Airgap mirror:
gpu-bench --node worker-gpu1 --workload-image registry.internal/hpc-benchmarks@sha256:<pinned>

# Left-by-control-machine-or-crash recovery (deterministic):
gpu-bench --cleanup-only qs-1
```

Every flag maps one-to-one to run inputs — see
[`specs/005-gpu-confidential-benchmark/contracts/operator-surface.md`](../specs/005-gpu-confidential-benchmark/contracts/operator-surface.md)
for the full surface and exit codes (`0` ok, `1` preflight, `2` case
failure, `3` usage error/operator abort, `4` leftover cleanup failed).

## What you get

```text
results/<run-tag>/
├── run.env                        # resolved operator inputs (sans secrets)
├── preflight.log                  # fixed-format PREFLIGHT lines
├── values-<case>.yaml             # exact Helm values per case
├── manifest-<case>.yaml           # exactly what was applied, per case
├── exec-<case>.log                # orchestration transcript per case
├── <case>/rep<N>/bench-output.txt # raw HPL / HPL-MxP output per repeat
├── <case>/devices.txt             # assigned-GPU evidence (nvidia-smi)
├── LOGS/case-pod-<case>.log       # pod logs collected before delete
├── summary.md                     # per-case table + confidential-vs-standard delta
└── summary-echo.txt

results/iceberg-warehouse/         # shared across runs (FR-008)
├── runs.metadata                  # one row per invocation (incl. census warns)
├── runs.case_iterations           # one row per case run
├── runs.datapoints                # per (case, repeat): Gflops + verified status
└── runs.case_aggregates           # per case: min/max/mean/stddev + spread
```

**Verified-only rule (FR-007/SC-003)**: a performance number exists only
together with its LINPACK residual-check verdict; unverified or failed runs
appear as status gaps, never as numbers. The delta table pairs `plain` and
`coco` results of the **same run** per benchmark — fp64 and mixed numbers
are never compared to each other. Expected evidence for a successful run:
`PREFLIGHT OK` lines, `CASE <slug> DONE status=verified` for all cases,
exit 0, rows in the summary, no leftover pods/configmaps on the cluster.

## Interpreting numbers (must-read before quoting)

Read [`docs/sizing-guidance.md`](docs/sizing-guidance.md) **before quoting
results**: run-duration expectations, quoting rules (verified pairs only,
same-run comparisons, isolation caveats, spread reporting). Deltas are
measured outcomes, not promises.

## Cleanup

Normal runs delete each case's Pod/ConfigMap and verify deletion.
Interruption (Ctrl-C) runs the same delete path from the tool's signal
handler. If the control machine dies mid-run:

```sh
gpu-bench --cleanup-only "<run-tag-you-used>"
```

`--cleanup-only` returns exit 0 (clean) or 4 (resources remain — re-run it
or delete by label `gpu-benchmark/run-tag=<tag>`). **No upgrade/migration
story** — delete and recreate is the lifecycle.

## Adding benchmarks (FR-012)

Benchmarks are declarative YAML definitions in
[`benchmarks/`](benchmarks/README.md); adding one (e.g., the anticipated
physics-relevant, non-AI benchmark) requires **only** a new definition file
plus its docs — zero changes to existing definitions, the chart, the runner
core, or the reporting flow (SC-004). CI validates the contract with a
placeholder-discovery check.

## Non-goals (per spec)

No attestation/Trustee secret integration (confidential tier is
runtime-class only — see `kbs-client`/`block-storage-encrypted` for
attested secret delivery), no AI/ML benchmarks, no multi-node benchmarks,
no CI regression gating on numbers. Testing only: delete and recreate
releases for chart changes; upgrades are unsupported.
