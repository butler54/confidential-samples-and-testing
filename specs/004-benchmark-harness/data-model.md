# Data Model: IO Benchmark Harness

Entities from spec Key Entities, refined by research decisions. All are implementation artifacts of a benchmark run; none persist cluster-side after cleanup (except Iceberg appends, by design).

## Run Configuration (operator inputs, all configurable — FR-003)

| Field | Type / Default | Validation (preflight) | Source FR |
|---|---|---|---|
| run_tag | str, defaults to `<UTC:%Y%m%dT%H%M%SZ>` | `[a-z0-9.-]`, ≤40 chars | FR-003 |
| node | str, required | node exists & schedulable OR explicitly cordoned-by-operator intent flag | FR-003/FR-004 |
| storage_class | str, required | exists; raw-block capability probe warning | FR-003 |
| namespace | str, default `default` | exists or creatable | FR-003 |
| cases | list[str], default all six | ⊆ {plain, plain-luks, kata, kata-luks, coco, coco-luks} | FR-002 |
| pod_cpu / pod_mem | quantities, default `2` / `4096Mi` | within reasonable bound vs node allocatable | FR-014 |
| volume_size | str (Gi payload), default `512Gi` | FR-005 sizing rule vs node RAM (warn-only → cache-suspect stamp) | FR-005 |
| repeats | int ≥1, default `3` | FR-015 |
| fio_jobfile | path, default bundled `configmap-fio-job.yaml` template | exists, parseable by the Python tool's expectations | FR-006 override |
| images.workload | pinned ref, default `quay.io/rh-ee-chbutler/perf-utils` (externally built — FR-017); operator MUST override to internal mirror in airgap | non-empty; default documented | FR-009 |
| results_root | path, default `./results` | writable; Iceberg warehouse child `<results_root>/iceberg-warehouse/` | FR-008 |
| repo/checksum of image tags | recorded in run metadata for reproducibility | — | FR-012 |

Derived: `run_id = <run_tag>` (run_tag includes timestamp by default, unique per invocation); `results_dir = <results_root>/<run_id>`.

## Case (static catalog — FR-002)

| slug | runtimeClassName | storage treatment | notes |
|---|---|---|---|
| `plain` | none | XFS directly on raw block device | ordinary pod baseline |
| `plain-luks` | none | LUKS on device, XFS on dm mapping | "same encrypted storage as coco" applied to plain |
| `kata` | `kata` | XFS | sandboxed VM, no memory encryption |
| `kata-luks` | `kata` | LUKS + XFS | |
| `coco` | `kata-cc` | XFS | confidential VM (TDX) |
| `coco-luks` | `kata-cc` | LUKS + XFS | full comparison row |

Fixed execution order as listed. Failures mark the case `FAILED` and never abort later cases (FR-001).

## Datapoint (per repeat per fio job — FR-015)

From fio JSON output `#<results_dir>/<case>/rep<N>/<jobname>.json`:

| Field | Source | Notes |
|---|---|---|
| run_id, case, repeat_idx, job_name | derived | job_name = fio section (encodes pattern × block-size: `seqread-bs4k`, …) |
| pattern, block_size | job filename convention | `seqread\|seqwrite\|randread\|randwrite\|randrw`, `4k…1M` |
| bw_bytes / iops / lat_mean_us / lat_p95_us / lat_p99_us | fio JSON `bw`, `iops`, `latency` clat percentiles | client-facing fields |
| runtime_s, ramp_s, iodepth, ioengine, direct | job options echo | provenance for interpreting the number |
| status | OK / FAILED (+ error rc/stderr tail) | FR-008 failure marking |
| cache_suspect | bool stamped from FR-005 evaluation | warn-only path visibility |
| collected_at (UTC) | client clock | |

## Case Aggregate (computed by the Python tool — FR-015 spread)

Per (run_id, case, job_name): `n_repeats_completed`, `bw_bytes_{min,max,mean,stddev}`, `iops_{min,max,mean,stddev}`, `lat_mean_us_{min,max,mean,stddev}`, `lat_p95_us_mean`, `lat_p99_us_mean`, `spread_rel = (max-min)/max(ε, mean)` for bw/iops. Status of case = any-repeat-failure → partially-FAILED rows stay visible.

## Iceberg Store (self-describing machine format — FR-008/FR-011 contract)

Warehouse: `<results_root>/iceberg-warehouse/` · Catalog: local SQLite file `<results_root>/iceberg-warehouse/catalog.db` (PyIceberg `sql` catalog, in-image default).

**Table `runs.metadata`** — one row/invocation: run_id, run_tag, utc_start, utc_end, node, storage_class, namespace, pod_cpu, pod_mem, volume_size, repeats, fio_job_name_list, images (workload), cases_requested[], cases_completed[], cache_suspect, sizing_rule_threshold, sizing_rule_actual, tool_version (bench.py version), repo_git_sha (if available).

**Table `runs.case_iterations`** — one row/case run: run_id, case, runtime_class, encrypted, pvc_name, pod_name, utc_start, utc_end, status, failed_stage.

**Table `runs.datapoints`** — one row/(case, repeat, job): run_id + all Datapoint fields (partitioned by run_id). Aggregation column set appended by the tool (`case_aggregates` is derived, queried on demand into the Markdown table — Iceberg table `runs.case_aggregates` also written for query stability).

**Why this design**: per-run appends make Iceberg store the cross-run comparison medium (SC-003 cross-invocation defensible); SQLite catalog needs zero services; Parquet under warehouse keeps result self-describing.

## Run Log Layout (run folder — FR-008 raw-log retention)

```text
<results_root>/<run_id>/
├── run.env                    # operator inputs as resolved (sans secrets)
├── preflight.log              # fixed-format PREFLIGHT lines
├── manifest-<case>.yaml       # rendered per case
├── exec-<case>.log            # orchestration transcript
├── <case>/
│   ├── rep1/<job>.json, rep2/…, rep3/…  # fio JSON per repeat (FR-015)
│   └── case.log
├── LOGS/case-pod-<case>.log   # oc logs snapshot pre-delete
├── summary.md                 # Markdown comparison table (final)
├── summary-echo.txt           # stdout-side table copy
└── parse-args.json            # echo back of tool parse/summarize inputs (debug)
```

Cleanup guarantees (FR-013): per-case `oc delete -f manifest-<case>.yaml` + verified removal; identical path runs on INT/TERM via the tool's finally/signal handlers; `bench.py --cleanup-only <run-tag>` repeatable for control-machine-death recovery; cluster PVC lifecycle documented in case manifest delete path.

## Sizing Rule Rulebook (FR-005/FR-012)

`required_volume = node_total_ram × 1.1` (margin documented in sizing-guidance doc). If `volume_size < required_volume` → preflight `PREFLIGHT CACHE-SUSPECT volume sizing_rule node_ram=<X> required=<Y> configured=<Z>`; run proceeds; `cache_suspect=true` propagates into run metadata + every summary stamp; Markdown table carries `⚠ CACHE-SUSPECT` header row.
