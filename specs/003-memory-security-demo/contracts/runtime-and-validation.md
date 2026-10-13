# Contract: Runtime Boundary and Validation Scope

What this feature's validation proves — and, explicitly, does not. Mirrors the previous feature's contract so reviewers and CI set honest expectations.

## Runtime boundary

- **In-repo (rendered or documented)**: two Helm charts; the memory-security walkthrough and kbs-client doc; in-chart shell helpers; static test harness; CI wiring.
- **Executed by the user, manually** (never by this repo's tooling or CI): every host/`oc debug` step; gcore dumps; packet captures; string greps; kbs-client invocations.
- **Built outside this repo** (dependency, FR-011): the coredump-helper and kbs-client container images in `butler54/containers`, consumed here by pinned reference. Until those builds are published with a resolvable reference, the walkthrough prerequisite section says so; chart renders do not depend on them (tooling images are documented, not chart values).

## Validation scope

Lint/shell pipeline (per chart `tests/run.sh` → `helm lint --strict`, `shellcheck`, `sh -n`; CI matrix on pinned Helm 3.22.0/ubuntu-24.04). Render-assertion checkers (`tests/static.py`) were planned and implemented during this feature, then removed repo-wide per PR #5 review; structural contract items (route policy, HTTP/string confinement, naming) are documented review contracts verified by manual render spot-checks per quickstart, not automated tests.

**Proven by the pipeline**

1. Charts lint clean under `--strict` with representative demo values (schema-valid values, template resolution, required keys present).
2. Shell syntax and lint of every shipped script (`shellcheck` + `sh -n`).

**Explicitly NOT proven** (documented in both chart READMEs; remains the user's live observation)

- That memory dumps contain or omit the magic string on any platform (the entire US1/US2 observation is manual by design).
- That the route serves both schemes on any given cluster; ingress availability; DNS.
- That `curl -k` succeeds against any given ingress CA configuration.
- That Trustee serves any demo resource; kbs-client behaviour at runtime.
- That tooling images exist at their pinned references until `butler54/containers` publishes them.
- Any cluster reachability, attestation, TDX capability, or provider behaviour.

Static results must never be reported as evidence of runtime security properties; the walkthrough documents expected live outputs for a human to compare.
