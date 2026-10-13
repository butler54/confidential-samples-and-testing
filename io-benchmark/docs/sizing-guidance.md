# Sizing and variance guidance (FR-005 / FR-012)

How to read this harness's numbers on large-memory nodes and enterprise
storage. Selection rationale lives in `benchmark-selection.md`; the
per-run stamp itself is emitted by `bench.py` preflight.

## The sizing rule

```
required_volume = node_total_RAM × 1.1   (documented margin)
```

Preflight evaluates `volume_size >= required_volume` every run
(`PREFLIGHT OK|CACHE-SUSPECT sizing-rule …`). On violation the run proceeds —
this is deliberately **warn-only** (spec Clarifications, session 2026-10-13)
— and every downstream artifact is stamped `cache_suspect`:

- `summary.md` carries a `⚠ CACHE-SUSPECT` header.
- `run.env`, Iceberg `runs.metadata.cache_suspect` and
  `runs.datapoints.cache_suspect` are `true`.
- `--assume-cache-suspect` forces the stamp even on compliant volume sizes.

Why warn-only rather than hard-fail: with fio `direct=1` on every job, host
and guest **page caches are bypassed at the block layer**, so node RAM stops
being the dominant cache risk. What remains is **below** the hypervisor —
storage controller and SAN caches, which node RAM does not describe at all.
Forcing run abort would buy false precision: a 2×RAM volume on a cached SAN
can still be cache-dominated. The rule's job is *visibility*, not veto.

Residual guidance by topology:

| Backend | Effective rule |
|---|---|
| Local disk / direct-attached | `≥ RAM × 1.1` is likely sufficient — page cache bypassed, device cache small |
| SAN with read cache | Treat the SAN's published cache as the reference, not node RAM; `1.1 × max(RAM, SAN read cache)` |
| Thin-provisioned/virtual disk | Add the platform's metadata cache to both ends of the rule |
| `randread`-heavy small-block | Cache-suspect is *most* meaningful here; treat with skepticism even when the rule passes |

## Interpreting the spread columns

Each job is run `repeats` times (default 3, FR-015) and `summary.md`
+ `runs.case_aggregates` quote min/max/mean/stddev plus `spread_rel` =
`(max-min)/mean`.

Rough reading (no thresholds are enforced — FR-012 leaves judgment to the
operator):

- **`spread_rel < 5%`** — stable; numbers can be quoted with confidence.
- **5–15%** — typical SAN/SAN-cache volatility; quote the mean with the
  spread, not the mean alone.
- **> 15%** — noisy run. Check the tenant-census warning first (co-resident
  pods are the usual cause, FR-016); then re-run with `repeats=5`.
- **Asymmetric spread between cases** (e.g. plain quiet, coco volatile) is
  itself a result — it indicates per-class interference sensitivity, not
  harness error. Report it as such.

## Practical levers when variance is high

1. Increase `--repeats` (more samples, same sweep).
2. Provide a custom `--fio-jobfile` with longer `runtime` and `ramp_time` —
   60s+ per section on SAN backends.
3. Verify volume complies with the sizing rule for your *worst* cache tier.
4. Re-run with an **emptier node** (the harness never cordons/evicts; that is
   the operator's isolation prerequisite).

## What the pipeline does about cache by construction

- fio `direct=1` + `invalidate=1` on every job (chart-baked global).
- Job sections stonewall-separated (steady-state per job, no bleed).
- Working set = 90% of the requested volume (never RAM-shaped, FR-007).
- Write jobs precede read jobs in the default job file (device
  pre-condition) and each job has `ramp_time=10`.
- All datapoints recorded regardless of outcome — FAILED rows are first-class
  in `summary.md` and Iceberg, so variance is attributable.
