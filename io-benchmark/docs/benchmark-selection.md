# Benchmark selection: why this harness runs fio end-to-end

This document is the feature's **US1 / FR-011 deliverable**: the recorded,
reviewable decision that binds every benchmark this harness runs. It evaluates
the credible options against the harness's stated measurement needs and
rejects the rest with reasons. The companion guidance on *interpreting* the
numbers lives in `sizing-guidance.md`.

## What the decision had to satisfy

The harness measures **storage IO** of plain pods, kata pods, and confidential
(coco) pods, with and without guest-side LUKS encryption, in a way that can be
quoted in credibility-sensitive comparisons. Concretely, the selected tool
MUST:

1. Address **raw block devices** directly (the benchmark target is a
   `volumeMode: Block` PVC, laid under XFS or LUKS+XFS inside the pod).
2. Offer **cache-defeating modes** (direct/unsynchronized IO, cache
   invalidation, sync control) so numbers measure media, not buffers.
3. Sweep a **block-size spectrum at least 4k→1M**, seq + rand, read/write/mixed.
4. Produce **machine-parseable output** without screen scraping.
5. Scale **queue depth** independently (async engine), since steady-state
   latency/bandwidth at depth is the honest block-device characterization.
6. Be **airgappable** as a single self-contained binary, and be suitably
   benchmark-mainstream that quoted results carry weight.

## Candidates and verdicts

### fio 3.x — SELECTED

The Flexible IO Tester was written (by Jens Axboe, now maintained with
Vincent Fu) precisely for characterizing Linux block/IO stacks. Against every
criterion above:

| Criterion | fio 3.x evidence |
|---|---|
| Direct block-device targets | `filename=/dev/xvda`, `filetype=block`, `direct=1` — first-class |
| Block-size spectrum | Per-job `bs=4k..1M`, `bssplit`, ranges |
| Cache-defeat | `direct=1`, `invalidate=1`, explicit fsync control |
| Machine-parseable output | Native `--output-format=json` (and `json+`) |
| Queue-depth scaling | `ioengine=libaio`/`io_uring` + `iodepth` |
| Steady state | `runtime`/`time_based` + `ramp_time`, `stonewall` section quiescing |
| Provenance/shape | Single binary, EPEL-built, de-facto block benchmark; no services needed |

The perf-utils workload image (`quay.io/rh-ee-chbutler/perf-utils`, built
externally from `butler54/containers` `standard-quay/perf-utils`) already ships
fio 3.42+ on UBI9, so no new container image is defined or built by this
feature (constitution v2.0.0 IV, FR-017).

### sysbench (`fileio`) — REJECTED

Respected DB/system benchmark, but wrong fit here:

- `fileio` benchmarks **filesystem files only** — it has *no* direct
  block-device target mode, so it cannot measure our `volumeMode: Block`
  PVC without an extra formatting/abstraction layer it does not control.
  (Upstream README confirms the prepare-stage file model.)
- Block-size control is **coarser** (single file-block-size per run).
- Output is **text only** — parsing needs screen scraping, which the
  self-describing, cross-run-comparable results contract (FR-008) forbids
  as a one-off liability. No JSON.
- Its main value (OLTQ-in-pod DB load, cpu/memory/threads tests) is out of
  scope for a storage-IO harness; the earlier staging iteration's
  vertical-scaling use case was clarified out of scope (FR-014).

sysbench remains in the perf-utils image, so it is documented as the natural
**cross-check** candidate if the harness's goal ever shifts to
filesystem-path or mixed system load.

### dbench — REJECTED (all three permutations)

- **As-is**: dbench is a Samba-project *protocol* load generator (NetBench
  traffic replay against SMB shares), not a block-tool; adopting it would
  pull an SMB server into the cluster as new infrastructure and would measure
  protocol+caching+network as well as media.
- **Wrapped**: cinnabar-style wrapping gains us implicit setup/teardown but
  still measures a share, not a device — the network and server-side caches
  contaminate exactly the numbers we must defend.
- **Forked**: stripping Samba/CIFS from dbench leaves a custom C benchmark
  re-implementing fio's core — highest effort, lowest credibility.

No permutation satisfies criteria 1/4/2/6.

### Custom synthetic benchmark — REJECTED

Poorest credibility and reproducibility; unnecessary given fio.

## Consequence for implementation

fio is the **single** tool end-to-end (FR-011): the job file baked into the
chart (`values.yaml#fioJobInline`), the exec contract in `tools/bench.py`,
and the parse/normalize/aggregate code are all fio-shaped. Nothing else runs.

## What would change this decision

- fio drops device-level/direct-IO capability or JSON output.
- The measurement goal shifts from **storage IO** to **protocol or DB
  behaviour** (that is sysbench/dbench territory — add a *second*
  purpose-specific tool alongside fio under the same contract, never a swap).
- An enterprise requirement demands measurement under a *specific* engine
  (e.g. RocksDB via `db_bench`); same treatment as above.
