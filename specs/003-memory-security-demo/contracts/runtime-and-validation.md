# Contract: Runtime Boundary and Validation Scope

What this feature's validation proves — and, explicitly, does not. Mirrors the previous feature's contract so reviewers and CI set honest expectations.

## Runtime boundary

- **In-repo (rendered or documented)**: two Helm charts; the memory-security walkthrough and kbs-client doc; in-chart shell helpers; static test harness; CI wiring.
- **Executed by the user, manually** (never by this repo's tooling or CI): every host/`oc debug` step; gcore dumps; packet captures; string greps; kbs-client invocations.
- **Built outside this repo** (dependency, FR-011): the coredump-helper and kbs-client container images in `butler54/containers`, consumed here by pinned reference. Until those builds are published with a resolvable reference, the walkthrough prerequisite section says so; chart renders do not depend on them (tooling images are documented, not chart values).

## Validation scope

Static pipeline (per chart `tests/run.sh` → `helm lint --strict`, `shellcheck`, `sh -n`, `tests/static.py`; CI matrix on pinned Helm 3.22.0/ubuntu-24.04):

**Proven statically**

1. Charts render or reject exactly per the values/render contract (route serving HTTPS + documented plaintext HTTP in every render, required `route.host`, initdata precedence).
2. String confinement (ConfigMap only), HTTP confinement (exactly one pod, one command), route policy invariants (edge + Allow always, demonstration markers present), name uniqueness across a multi-release cohort, image pinning format.
3. Shell syntax and static lint of every shipped script; README command blocks match the rendered resource names they reference (name-derived checks where feasible).

**Explicitly NOT proven** (documented in both chart READMEs; remains the user's live observation)

- That memory dumps contain or omit the magic string on any platform (the entire US1/US2 observation is manual by design).
- That the route serves both schemes on any given cluster; ingress availability; DNS.
- That `curl -k` succeeds against any given ingress CA configuration.
- That Trustee serves any demo resource; kbs-client behaviour at runtime.
- That tooling images exist at their pinned references until `butler54/containers` publishes them.
- Any cluster reachability, attestation, TDX capability, or provider behaviour.

Static results must never be reported as evidence of runtime security properties; the walkthrough documents expected live outputs for a human to compare.
