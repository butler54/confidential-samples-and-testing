# Sizing guidance: problem size, run duration, and quoting rules

**Feature**: 005-gpu-confidential-benchmark | **Read this before quoting any
Gflops number.**

## How N is computed (research R6)

The runner sizes the LINPACK problem once per run (per benchmark and GPU
configuration) and reuses the identical parameters for every runtime class
(FR-004 — comparability):

```text
N   = floor( sqrt( memory_fill × per_gpu_memory_bytes × gpu_count / 8 ) )
N  -= N mod (8 × NB)                      # HPL-friendly multiple of the block size
NB  = definition default (HPL: 384, HPL-MxP: 2048) or --hpl-nb
P,Q = factor pair of gpu_count with P ≤ Q, closest to square
      (1→1×1, 4→2×2, 8→2×4)
```

Defaults: `--memory-fill 0.8` (80% of aggregate GPU memory), per-GPU memory
from the GFD label `nvidia.com/gpu.memory.total`. Example, one H100 80GB,
single-GPU HPL: `N ≈ 92,000` with `NB=384`. Full-system on 8×H100:
`N ≈ 261,000` with a 2×4 process grid.

Overrides (`--hpl-n`, `--hpl-nb`, `--hpl-p`, `--hpl-q`, `--memory-fill`)
apply to **all tiers alike** — the runner refuses per-tier parameter
divergence because it would invalidate the comparison.

## Run-duration expectations (must read)

HPL's cost is `(2/3)·N³` flops. At the default memory fill:

| Configuration | Rough sustained fp64 rate | Approx. wall time per repeat |
|---|---|---|
| 1 × H100 (HPL) | ~50 TF/s | **~3 hours** |
| 8 × H100 NVLink (HPL) | ~400 TF/s | ~3 hours |
| HPL-MxP (mixed) | ~10–20× fp64 | minutes |

Full-fill LINPACK runs are **hours long by design** — that is what
"sustained peak" means. For smoke tests and harness validation, override the
problem size (e.g. `--hpl-n 20000`) and treat the resulting numbers as
non-representative. Set `--exec-timeout` above the expected duration
(default 14400s = 4h per repeat).

## Quoting rules

1. Only **verified** numbers may be quoted: the residual-check verdict must
   be `PASSED` (FR-007). Unverified/failed runs appear as status gaps, never
   as performance numbers (SC-003).
2. Quote the **delta within one benchmark only** — HPL (fp64) and HPL-MxP
   (mixed) numbers are never compared to each other (research R8).
3. Quote the pair, not one side: `plain` and `coco` results from the **same
   run** (same node, same parameters). Cross-run quoting requires identical
   `N/NB/P/Q` and GPU model, checked against `run.env`.
4. State the node isolation status: the harness census-warns about tenant
   pods on the node but never enforces isolation (FR-009). A warned run is
   quotable only with the caveat.
5. For multi-repeat runs (`--repeats`), quote the mean **and** the relative
   spread from the summary table; a spread above a few percent invalidates
   fine-grained delta claims.
6. Confidential-vs-standard deltas are **measured outcomes**, not promises
   (spec assumption) — report what the run showed, including "no measurable
   difference" when that is the result.
