# Benchmark catalog definitions

Declarative YAML definitions — the extensibility surface of this example
(FR-012, SC-004). Adding a benchmark = adding **one YAML file in this
directory plus its documentation**, with zero changes to existing
definitions, the Helm chart, the runner core, or the reporting flow.

The full contract (schema, harness guarantees, obligations) is specified in
[specs/005-gpu-confidential-benchmark/contracts/benchmark-catalog.md](../specs/005-gpu-confidential-benchmark/contracts/benchmark-catalog.md).

## Current catalog

| id | precision | binary | source |
|----|-----------|--------|--------|
| `hpl` | fp64 | NVIDIA HPL 26.02.01 | NVIDIA HPC-Benchmarks collection (pinned image) |
| `hpl-mxp` | mixed | NVIDIA HPL-MxP 26.02 | NVIDIA HPC-Benchmarks collection (pinned image) |

Selection rationale: [../docs/benchmark-selection.md](../docs/benchmark-selection.md).

## How to add a benchmark (maintainer guide)

1. **Ship it in the workload image.** The benchmark's binaries must already
   exist in the referenced image (default NVIDIA HPC-Benchmarks collection,
   or an externally owned override image — this repository never builds
   images, constitution IV).
2. **Copy the definition shape** from `hpl.yaml`:
   - `id`, `precision` (`fp64`|`mixed`), `version`, `docs_ref`
   - `parameter_inputs`: `memory_fill`, `default_nb`, `process_grid`
   - `command_template`: placeholders `{n}`, `{nb}`, `{p}`, `{q}`, `{nprocs}`
   - `parser`: a `metric` mapping (pattern + group capturing the performance
     number) and a `verification` mapping (pattern + group + `pass_value`)
     — **a benchmark without a verification verdict cannot produce
     performance results** (FR-007/SC-003).
3. **Document it**: selection rationale and parameters in
   `docs/benchmark-selection.md` (or a sibling doc referenced by
   `docs_ref`).
4. **Verify discovery**: `gpu-bench --dry-run --benchmarks <new-id> ...`
   must list it; `tests/run.sh` validates every definition in CI.

Mechanically proven by CI: `tests/run.sh` loads the real catalog through the
runner's own loader and additionally proves the discovery guarantee with a
placeholder definition in a temporary directory (quickstart Scenario 5 /
US3 acceptance).

## Future-work note (out of scope for feature 005)

NVIDIA's HPC-Benchmarks collection also ships **HPCG** (sparse
conjugate-gradient, PDE-flavored) — the natural candidate for the
anticipated physics-relevant (non-AI) benchmark. It would be added under
this contract with no harness change (research.md future-work note).
