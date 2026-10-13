# Contract: Operator Surface

The end-user interface of the io-benchmark harness. Walkthroughs and tests may assume exactly this.

## Entrypoint

```text
python3 io-benchmark/tools/bench.py [flags]
```

Explicitly-approved Python tool (spec FR-018, constitution v2.0.0 II) + `oc` + `helm` on the control
machine. Single command per spec FR-001; resumable only by starting a new run
(`--cleanup-only <run-tag>` for leftovers).

## Inputs (all via flags; flags map to run-configuration fields 1:1 — see data-model.md)

| Flag | Values | Default | Notes |
|---|---|---|---|
| `--run-tag S` | alnum+`-.` | UTC timestamp | becomes run_id |
| `--node NAME` | existing node | (required) | schedulability evaluated in preflight |
| `--storage-class NAME` | existing SC | (required) | raw-block support probed |
| `--namespace NS` | | `default` | |
| `--cases a,b,c` | subset of six canonical slugs, canonical order applied | all six | |
| `--pod-cpu Q` / `--pod-mem Q` | qty; qty | `2`; `4096Mi` | single size per run (FR-014) |
| `--volume-size S` | Gi-size string | `512Gi` | FR-005 rule evaluation |
| `--repeats N` | int≥1 | `3` | |
| `--fio-jobfile PATH` | readable file | chart-bundled default | FR-006 |
| `--workload-image REF` | image ref | `quay.io/rh-ee-chbutler/perf-utils` (documented default) | airgap override (FR-009/FR-017) |
| `--results-root PATH` | writable path | `./results` | iceberg warehouse lives under it |
| `--assume-cache-suspect` | bool | off | forces cache-suspect stamping |
| `--initdata {debug,cluster-default}` | per repo conventions | `debug` on coco cases | coco-pattern alignment |
| `--image-pull-secret NAME` | | none | airgap mirror auth |
| `--cleanup-only RUN_TAG` | | not set | remediate leftovers and exit |
| `--coco-validate {proxy,strong}` | | `proxy` | strong adds opt-in node-debug TDX check |
| `--dry-run` | bool | off | full preflight incl. raw-block probe, then stop before provisioning (probe PVC is transient — created+deleted) |
| `--yes` | auto-confirm | off | without `--yes`, an interactive "Type 'yes'" confirmation precedes the first provisioning (EOF-safe decline exits 3); `--yes` skips the prompt |

Exit codes: `0` all cases OK · `1` preflight FAIL · `2` ≥1 case failed · `3` usage/config error ·
`4` cleanup verification failed (remnants left — `--cleanup-only` hint printed). Nonzero still
emits whatever summary/iceberg appends were possible (FR-001 continuation).

## Outputs

1. **stdout** — fixed-structured progress: `PREFLIGHT …` lines (R8), `CASE <slug> <phase>` markers, final row table copy (same as `summary-echo.txt`). Machine-greppable, designed for log capture on operator machines.
2. **run folder** — layout per data-model.md §Run Log Layout, including `summary.md` (Markdown comparison table — FR-008 human surface).
3. **Iceberg store** — `<results_root>/iceberg-warehouse/` with appends to `runs.metadata`, `runs.case_iterations`, `runs.datapoints`, `runs.case_aggregates` (data-model.md §Iceberg). Appends happen after each completed case and at finalize; queryable with any Iceberg reader (duckdb/pyiceberg/spark) for cross-run comparison.
4. **cache-suspect stamp** — when FR-005 sizing violated: preflight WARN line, `run.env`, `summary.md` header row, Iceberg `runs.metadata.cache_suspect=true`.

## Chart values (io-benchmark Helm chart, one render per case)

`case.slug`, `case.runtimeClassName|""`, `case.encrypted(bool)`, `node.name`, `pvc.storageClass`,
`pvc.size`, `pod.cpu/mem`, `images.workload`, `fioJobInline` (jobfile text, templated into
ConfigMap), `initdata.mode`, `imagePullSecrets[]`, `namespace`. values.schema.json enforces
required fields, enum case slugs, and tagged (non-`latest`) image refs.

## Summarization step (in-tool — R3)

Summarization runs **inside** `bench.py` (the approved Python tool), invoked after each completed
case and once at end-of-run; there is no external summarizer process or image. Contract: reads
datapoint JSONs + `run.env` from the run dir; appends Iceberg; emits markdown; idempotent for the
same run (dedupe by run_id+case+repeat+job).

## Delete/recreate guarantee

No upgrades/upgrade contracts. Operator uninstall story = delete manifests + local results intact (FR-013).
