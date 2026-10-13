# Quickstart: IO Benchmark Harness

Validation & run guide. Follow in order; the first two sections are CI-verifiable, the rest are the operator's live acceptance path.

## 1. Repository validation (lint/shell — CI-equivalent)

```sh
sh io-benchmark/tests/run.sh
```

Expected: `helm lint --strict` (with demo values) 0 failures; shellcheck/`sh -n`/`py_compile` clean. CI matrix row: `io-benchmark`.

## 2. Render spot-check (no cluster)

```sh
helm template io ./io-benchmark \
  --set case.slug=plain --set node.name=worker-1 \
  --set pvc.storageClass=my-sc --set pvc.size=512Gi \
  --set images.workload=quay.io/rh-ee-chbutler/perf-utils:latest
```

Expected: Pod name `io-benchmark-plain`, PVC `volumeMode: Block`, `nodeName: worker-1`, no runtimeClassName for `plain`; set `case.slug=coco-luks` and expect `runtimeClassName: kata-cc` + LUKS init container present; `configmap-fio-job` data overridable via `--set-file fioJobInline=…`.

## 3. Preflight-only dry run (cluster, no provisioning)

```sh
python3 io-benchmark/tools/bench.py --dry-run --node worker-1 --storage-class my-sc --pod-cpu 2 --pod-mem 4096Mi
```

Expected `PREFLIGHT` lines: cluster reachable, node found/cordon state reported, runtimeClasses present (needed cases only), SC raw-block probe, tenant census, FR-005 sizing evaluation (expect `CACHE-SUSPECT` if volume < node RAM ×1.1), image-override reminder. Exit 0 or 1 with explicit failing check.

## 4. Single-case minimal run (live acceptance — US2)

```sh
python3 io-benchmark/tools/bench.py --node worker-1 --storage-class my-sc \
  --cases plain --volume-size 64Gi --run-tag smoke-1
```

Expected (FR-001 lifecycle observable via `CASE plain …` markers): rendered manifest applied → PVC bound (Block) → pod Ready on worker-1 → XFS prepared → repeats ×3 fio execs (see `exec-plain.log`) → JSON collected (`results/smoke-1/plain/rep{1..3}/*.json`) → pod/PVC deleted + verified → exit 0 in ≤(provision+bench) time. `summary.md` contains one row; `results/iceberg-warehouse/` populated; re-summarization only needed from a debugger's perspective if a parse hiccup occurs.

## 5. Full six-case comparison (live acceptance — US3)

```sh
python3 io-benchmark/tools/bench.py --node worker-1 --storage-class my-sc \
  --volume-size 512Gi --pod-cpu 4 --pod-mem 8192Mi \
  --workload-image <mirror>/perf-utils:<pinned> \
  --run-tag gauntlet-1 --yes
```

Expected: strictly one benchmark pod at a time (`oc get pods -A | grep io-benchmark` during run shows ≤1 — observed by operator); six table rows (or explicit FAILED rows); `summary.md` header carries `⚠ CACHE-SUSPECT` only when sizing rule tripped; Iceberg `runs.datapoints` shows ~jobs × repeats × cases rows; variance columns (stddev/rel-spread) readable per FR-015; encrypted cases show LUKS+XFS preparation in `exec-<case>.log`.

## 6. Trust checks (US4 interpretation)

- Re-run data from two runs: query Iceberg `runs.case_aggregates` joined on case/job to compare cross-run spread — the sizing-guidance doc explains interpretation.
- If `CACHE-SUSPECT` stamped, treat read-heavy small-block results as unreliable; re-run with compliant volume before citing numbers.

## 7. Failure & recovery drills

- Ctrl-C mid-case → the tool's signal/finally path drives `oc delete -f manifest-<case>.yaml` + cleanup verify; leftover hunt after control-machine death: `python3 io-benchmark/tools/bench.py --cleanup-only <run-tag>`.
- Cluster unreachable at start → preflight FAIL, exit 1, nothing created.
- Simulate case failure (tainted fio image): case marks FAILED, later cases still run, summary shows FAILED row, exit 2.

## 8. Mirroring (airgap) reminder

Point `--workload-image` (or your namespace's `--image-pull-secret`) at your internal mirror of `quay.io/rh-ee-chbutler/perf-utils`; that one image is the only container image requirement. The tool-side Python deps are pinned in `io-benchmark/requirements.txt` — vendored/mirrored per your environment's Python packaging approach. No other network dependencies at run time. See README §Airgap.
