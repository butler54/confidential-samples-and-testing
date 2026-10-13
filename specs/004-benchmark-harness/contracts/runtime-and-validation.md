# Contract: Runtime Boundary and Validation Scope

Mirrors previous features' contracts: honest declaration of what repository validation proves and what remains the operator's live execution.

## Runtime boundary

- **In-repo**: Helm chart templates; the single explicitly-approved Python tool (`tools/bench.py`),
  its pinned `tools/pyproject.toml`; docs (operator guide, sizing guidance, benchmark-selection
  analysis — the US1/FR-011 deliverable); `tests/` pipeline (`helm lint --strict`, `shellcheck`
  where shell remains, `sh -n`, `python3 -m py_compile`) wired into the existing CI matrix.
- **External images**: exactly one — the existing `quay.io/rh-ee-chbutler/perf-utils` image
  (built outside this repository from `butler54/containers` `standard-quay/perf-utils`; contains
  fio, xfsprogs, cryptsetup). The repo defines and builds zero container images (constitution
  v2.0.0 IV, FR-017). CI never pulls it.
- **Executed by operator, manually**: every cluster step — PVC/Pod lifecycle, `oc exec` fio
  repeats, sizing-rule decisions on cache-suspect runs, SCC bindings for the LUKS case.

## Validation scope

**Proven by repository validation (CI pipeline)**:

1. Chart renders cleanly under `helm lint --strict` + `helm template` for representative inputs
   (six case value shapes; encrypted/unencrypted; namespaced rendering); `values.schema.json`
   enforced.
2. Tool hygiene: `python3 -m py_compile tools/bench.py` clean; any residual shell clean under
   `shellcheck` + `sh -n`; `tools/pyproject.toml` parses and its pins resolve.
3. Zero container definitions in-repo (`find -iname '*Containerfile*' -o -iname 'Dockerfile'`
   is empty outside `staging/`); no runtime Python inside charts/pods; no forbidden registries.
4. Markdown links in docs resolve (light sanity scan).

**Explicitly not proven** (documented in README + summaries):

- Any benchmark number — the six-case comparison is the operator's live observation per
  FR-001..FR-008.
- Real cluster scheduling, TDX detection, storage-class raw-block support (probed live in
  preflight, never simulated).
- Availability of `quay.io/rh-ee-chbutler/perf-utils` at run time (operator override / mirror
  responsibility in airgap).
- Iceberg table growth correctness under real appends (validated live; the tool's append path
  is idempotent on run identity).
- Performance/repeatability conclusions (SC-003 surfaces measured spreads; thresholds stay
  operator judgment per FR-012).

Validation results must never be presented as performance evidence. The runbook (quickstart.md) is the acceptance path.
