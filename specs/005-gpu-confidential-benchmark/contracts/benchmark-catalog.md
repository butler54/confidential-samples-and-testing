# Contract: Benchmark Catalog (FR-012)

**Feature**: 005-gpu-confidential-benchmark | **Date**: 2026-10-14

The benchmark catalog is the extensibility surface of the `gpu-benchmark`
example. It exists so that adding a benchmark — including the anticipated
physics-relevant (non-AI) benchmark — requires **adding one declarative
definition and its documentation, and nothing else** (FR-012, SC-004).

## Location and format

Definitions are YAML files in `gpu-benchmark/benchmarks/`. First entries:
`hpl.yaml`, `hpl-mxp.yaml`. Definitions are data, not scripts: adding one
introduces no executable code and therefore needs no script approval
(constitution II).

## Definition schema

```yaml
id: hpl                      # unique catalog key
precision: fp64              # fp64 | mixed — metrics compared only within a benchmark
version: "26.02.01"          # binary version, from the pinned workload image
docs_ref: docs/benchmark-selection.md
parameter_inputs:            # declarative inputs the runner composes into HPL.dat
  memory_fill: 0.8           # fraction of aggregate GPU memory the problem fills
  default_nb: 384            # block size default (overridable identically per tier)
  process_grid: square-ish   # P x Q rule derived from GPU count (P <= Q)
command_template: >-         # in-pod command; placeholders filled by the runner
  hpl.sh --n {n} --nb {nb} --nprow {p} --npcol {q}
parser:                      # mapping from benchmark stdout to result fields
  metric: { pattern: "Gflops.*", field: gflops }
  verification: { pattern: "Verified.*", field: verdict, pass_value: PASSED }
```

## Guarantees (what the harness promises to a new definition)

1. **Discovery**: the runner enumerates `benchmarks/*.yaml` at startup; a new
   file is selectable via `--benchmarks <id>` with no runner change.
2. **Full pipeline**: a new definition automatically participates in tier
   comparison (plain vs coco), GPU configurations (single/full), preflight
   parameter computation, verification-gated reporting, and both result
   surfaces (Markdown + Iceberg).
3. **No regression**: adding a definition must not require modifying any
   existing definition, the Helm chart, the runner core, or the reporting
   flow (SC-004).

## Obligations on a new definition

1. Must declare `id`, `precision`, `version`, `parameter_inputs`,
   `command_template`, `parser` (metric + verification), `docs_ref`.
2. Must carry a correctness verification in its output (residual check or
   equivalent); benchmarks without a verification verdict cannot produce
   performance results (FR-007/SC-003).
3. Must be shipped by the already-referenced workload image (or a documented
   override image); the repository still defines/builds zero images
   (constitution IV).
4. Must document its selection rationale and parameters in the example docs
   (FR-003 pattern).

## Validation of the contract itself

The catalog contract is testable without a cluster: adding a placeholder
definition (e.g., a catalog-only stub) and running the tool's
`--dry-run`/catalog listing must surface it, while `helm lint` and the
existing chart remain untouched — the acceptance test for US3/SC-004.

## Future note

NVIDIA's HPC-Benchmarks collection also ships HPCG (sparse
iterative-PDE benchmark), a natural candidate for the physics-relevant
(non-AI) benchmark anticipated by the spec; it would be added under this
contract (research.md, future-work note). Out of scope for this feature.
