# Implementation Validation

## Scope and environment

- Worktree branch: `002-refine-storage-startup`. Existing untracked staging samples are not implementation targets.
- Only local chart/render/shell fixtures are authorized by this run. No OpenShift context has been selected, deployed into, or modified; no backend volume deletion is attempted.
- Helm 3 and Podman are available; Podman host architecture is arm64. Python 3.12 test dependencies and ShellCheck 0.11.0 were installed in the ignored repository-local `.venv/` from pinned per-chart requirements.

## Image capability gate (T003)

- Source/package evidence for `osc-storage-helper:1.13.1` is recorded in `research.md`, source revision `617f70ce2225e036976c94783e1812a1dec4e41c`.
- Actual registry inspection with `skopeo inspect --no-tags` failed: Red Hat registry authentication is unavailable. No credentials were requested, printed, or copied.
- Therefore helper digest/architecture and actual executable inventory are **unverified**. Source findings are not substituted for execution. The chart-local image capability scripts allow an operator to verify the selected artifacts without building images here.
- This is an external runtime validation gate, not permission to install packages at startup. T003 remains unchecked until image capability evidence exists.

## Live acceptance gates

- Plain/encrypted persistence, source-verified mounts, NFS guest support, guest image execution, disconnected startup and actual CSI backing-volume deletion require an explicitly approved disposable cluster/export and provider-specific evidence; not executed in this run.
- Sealed mode additionally requires corrected upstream debug initdata and guest-local verification trust, tracked in https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162. No implicit signature bypass is implemented or accepted.
- T028, T040, T048, and T056 must remain unchecked where their required live evidence is missing.

## Local results

- T001: unique Helm v2 chart skeletons, version `0.1.0`/appVersion `1.13.1`, local templates/scripts/tests directories and chart-specific `.helmignore` created. Existing staging files untouched.
- T002: independent test runners and pinned pytest/PyYAML/ShellCheck requirements created; the local Python 3.12 dependency install completed successfully. Runners will require their later-phase workload scripts/tests; full chart/fixture suites are not yet runnable and are not reported as passing.
- T003: opt-in image capability scripts created for all three charts. They use operator-configured Podman registry authentication, no image builds, network-disabled test containers, and explicit target platform. They are not called by default offline validation. Actual helper inspection failed before any image container execution due to registry authorization.
- ShellCheck completed with zero findings on all six authored `tests/run.sh` and `tests/check-images.sh` scripts.
- `git diff --check` passed for tracked changes; this is not full workload validation.
- Implementation stopped at the failed sequential image-capability prerequisite, before Foundation. T001–T002 are checked; T003 and all subsequent tasks remain unchecked. These directories are scaffolding, not deployable completed examples.

## Resume requirements

Configure Red Hat registry authentication through the supported CLI login outside this conversation (do not paste credentials), or provide an authorized full image reference for a mirror of the exact helper artifact. Then run the chart-local `tests/check-images.sh` checks against that image and record the actual digest/platform/tool inventory. Confirm the intended verified image before continuing Phase 2. No alternative unsupported image, package install, or implied credential access is assumed.

## Authenticated retry — T003 completed

- The user configured authentication locally; no credentials were read into this conversation or altered by the agent.
- All four Podman checks passed using `--platform linux/amd64`: plain-block helper, encryption helper, NFS helper, and UBI retrieval utility. Containers were run with networking disabled and no host mounts; no storage formatting, mount, key retrieval, or cluster operation was performed.
- Helper tag `1.13.1`: Skopeo registry identity `sha256:c65fb8f12888705d4989d6b8f0e4e3f144224b43f72b609d5f496e77b3b73917`, Linux/amd64 selected; Podman local manifest digest `sha256:6194978f085331cf31da85ece1a2bdfab26d20b818932497cec95b5b7681c70f`, architecture amd64. Registry-list and locally stored manifest identities differ; they are not interchangeable claims about byte-identical manifests.
- UBI `9.6`: Podman local manifest digest `sha256:f3b9841ea7615b38fd271cf18ae235d8228d3369036eb175ded171c936808255`, architecture amd64; required curl/validation tools present.
- The first Skopeo retry selected OS darwin implicitly and failed platform selection; explicit `--override-os linux --override-arch amd64` succeeded. This was not an authentication failure.
- T003 is complete. Previous unauthorized observations remain as historical evidence, not the current gate status. No live acceptance result is inferred from the capability checks.

## Implemented artifacts and final offline validation

- All three root-level charts contain independent values/schema/templates, runtime scripts, documentation, chart-local tests and opt-in explicit-context verification tools. Root README provides the requested short linked descriptions. No sibling runtime dependency or image build is introduced.
- Final local suites: `block-storage-plain/tests/run.sh` **49 passed**; `block-storage-encrypted/tests/run.sh` **74 passed**; `nfs-direct/tests/run.sh` **47 passed** — **170 tests total**. Every runner also completes strict Helm lint at Kubernetes 1.33 and ShellCheck successfully.
- Tested properties include initdata precedence/default debug selection, protected labels/ownership, invalid key modes and source conflicts, the single-resource sealed metadata contract, HTTP error/redirect/empty/invalid key handling, probe-error/nonblank-media safety, file creation/existing/mismatch/readback/read/permission/race behavior, source gating and delayed availability, dynamic helper generation/source rejection, deployment/PVC/NFS topology, disconnected render references, explicit live/destructive authorization, long-name/namespace isolation and standalone chart packaging.
- Measured red checks before foundational/startup implementation: common workload contract failed on missing Deployment, and prose startup failed on missing script. Subsequent regression/error suites were added during implementation/review; this record does not claim every individual test was measured red before its corresponding code.
- Collection render check: **11 distinct resource identities** across three releases/charts in one synthetic namespace; no overlapping identities. This is render evidence, not live coexistence.
- All four expanded Linux/amd64 image capability checks pass, including blockdev/sort/awk/sed/date/mktemp and curl's validation tools. No key retrieval, actual block-device formatting, guest mount or cluster operation was performed by those checks.
- Additional review exercised `wipefs` against a **new synthetic 32MiB regular file inside a disposable, network-disabled container**, with a fake unit-test passphrase. This does not touch host disks or cluster volumes, and does not validate device-mapper mounting. It confirmed two `crypto_LUKS` signatures for LUKS2; runtime signature normalization and regression tests now deduplicate identical types without hiding conflicts.
- Existing-key checks precede mapper reuse; read/probe errors never imply blank storage; a full zero-byte check is required before initial raw-device formatting. PBKDF memory is bounded to 64MiB to fit helper resources. Actual guest/CSI behavior remains unverified.
- Code review fixed readback/read-error distinctions, truthful unknown creation state on supervisory timeout, one startup window covering mount and access, public-file checks in readiness, stale proc-root handling, reserved Helm-hook annotations, sealed-envelope metadata mismatches, and non-200 HTTP responses incorrectly resembling passphrases. Privileged/debug guest exposure is explicitly documented rather than represented as production isolation.
- High-confidence credential/private-key pattern scan of new chart sources found no matches; synthetic test values and public KBS identifiers are not production credentials. One initial failing pytest fixture inherited unrelated environment values into diagnostic output; all subsequent fixtures whitelist PATH plus explicit synthetic inputs. No such credentials were written into repository source or validation evidence. Rotate any credential from that diagnostic if the logs are shared outside the trusted session.
- CI workflow parses, pins action commits/Helm/Python/test dependencies, uses read-only repository permissions and disables persisted checkout credentials. Its matrix runs each chart independently; it contains no kubeconfig, registry credential, live hardware job, or PR-secret access. Action commit tags, Helm v3.22.0 and Python 3.12.12 Linux 24.04 availability were checked; CI itself has not run on GitHub.
- A non-fatal parallel-pytest garbage-directory cleanup warning was observed when suites shared pytest's default temporary root. Runners now allocate unique private scratch roots per invocation to avoid that shared cleanup race; no broad temporary-directory deletion is performed.

## Requirements and acceptance evidence

| Requirement / outcome | Evidence | Remaining gate |
|---|---|---|
| FR-001–FR-006, SC-007–SC-008 | Three independent packages, common values/schema tests, initdata/metadata contract tests, root/individual READMEs | Actual admitted pod behavior in prepared namespace |
| FR-007–FR-010, SC-001/SC-005 | PVC/topology render and safe format/encryption fixtures; image tools verified | Source-verified guest mounts, retained data across two real pod replacements |
| FR-011–FR-013/FR-027, SC-003–SC-004 | Mode/source/token metadata validation, fail-closed curl/key fixtures, no implicit signature bypass | Three live modes, actual corrected signed-token trust and denied/tampered tests |
| FR-014–FR-017, SC-006 | Direct-NFS topology/source argument tests; no PV/PVC/NFS volume; full mirror render override tests | Guest NFS support/export access and disconnected image/attestation operation |
| FR-018–FR-022, SC-002/SC-005 | Main readiness/startup/ownership/authorization fixtures, explicit provider-check interface, isolation/package checks and CI | Live coexistence, scoped SCC admission and actual backend deletion |
| FR-023–FR-026, SC-009–SC-012 | Creation/existing/error/race/mount-delay/helper-identity fixtures and explicit log contract | Observed guest propagation/readback and matching replacement logs in all three examples |

## Final task status

- **57/61** implementation/local-validation tasks completed.
- **T028, T040, T048, T056 remain unchecked**: require explicitly approved disposable context/namespace/export, actual upstream sealed trust and provider-specific deletion evidence. Registry login does not authorize these operations.
- No commits, pushes, OpenShift deployments, pod deletions, namespace changes, Trustee edits, CSI finalizer removals or backend volume deletions were performed. Existing staged samples remain untouched.

## Convergence implementation — 2026-10-09

- Runtime remains independent Helm charts plus embedded POSIX shell scripts. No runtime Python file, health service, added image, Service or Route was introduced. Chart-local Python remains excluded development/verification tooling only.
- Pinned-view prose operations and deterministic path-replacement tests are now present in all three charts. Operations use the validated CWD, compare filesystem/inode identity before and after file work, never re-resolve the absolute data path for the write, and refuse success/Ready state after a view change. New tests were observed failing before the corresponding fix.
- Helper success/reopen/mapper-reuse tests exposed a real termination race: readiness state could be published before cleanup traps were installed. Cleanup now installs before opening anything or publication, only cleans verified-owned mappings/mounts, handles post-open errors, and invalidates its own published state. Tests cover fresh LUKS/XFS, existing reuse, wrong backing/mount identity, post-open filesystem failure and readiness invalidation after helper state/generation changes.
- All chart-local cleanup verifiers share an end-to-end configured deadline across Helm teardown, owned/controller-owned objects, PV removal and backend evidence. Backend adapter exit codes are 0=proven absent, 3=pending, other nonzero=error; pending is retried within the remaining budget. Complete mocked API/Helm flows cover matching-label external objects, unchanged/replaced data, successful eventual cleanup, fatal backend errors and deadline exhaustion. These mocks do not prove real CSI reclamation.
- Collection verification now accepts explicit chart/release cohorts and mirror/initdata expectations, requires all three examples plus a second release, checks owned resource/claim/selector/file isolation and Ready admitted pods, and re-verifies each remaining member's actual storage/prose through the independently packaged tool. An already removed member is checked but never removed automatically. Cross-chart uninstall is explicitly refused; destructive actions still require their own flags. Mocked cohort cases cover wrong mirror, duplicate file identity, selector mismatch, unready members, bad injected data and surviving members after removal.
- NFS fixtures now execute the actual NFS-kind checker for source/type mismatch, delayed/unreachable mount observations, read-only retained files and write-denial behavior. They do not contact a server or perform actual mounts. The real GNU-timeout case runs on Linux CI; it is explicitly skipped on this macOS environment rather than represented as executed.
- Safe override validation now rejects system mount targets, incomplete CPU/memory maps, incoherent budgets below the fixed guest/overhead requirement, and known floating aliases including nightly. Optional SCC Roles/RoleBindings propagate supported resource annotations consistently. Negative render tests were measured failing before the fixes.
- Failure diagnostics now distinguish complete file/mount paths, configured timeout and skipped/failed file checks, retaining truthful creation/unknown outcomes. A separate bounded shell deadline reporter announces mount expiry independently of child cleanup grace. No arbitrary existing file content, token or key is logged.
- Final chart-local test results: **plain 75 passed; encrypted 107 passed; NFS 80 passed, 1 skipped — 262 passed total**. All runners also pass strict Helm lint and ShellCheck; `git diff --check` passes. Existing staging samples are not implementation targets and were not changed.
- The exec-denying compatibility choice remains **unanswered**. The existing debug-initdata path is retained and works with its expected exec permission, but fully exec-denying policy acceptance is not claimed and logs-only remains diagnostics. No policy or specification was silently weakened to close that gate.
- No live environment, export, corrected sealed signing trust, provider adapter/evidence or explicit destructive-target authorization was provided. All linked live tasks remain open. No cluster operations, Trustee edits, backend deletion, commits or pushes occurred.

## Current completion tracking

- All nine buildable convergence fix groups are now implemented and validated once across the independent charts; their 27 linked task entries in Phases 9–11 are checked. Current total: **84/94** checked.
- Remaining policy tasks: **T063, T074, T085**. Their required decision is whether initdata overrides must allow the supplied read-only exec probes, or whether full all-exec-denied support remains mandatory despite the no-new-runtime-service boundary. No answer or scope change has been assumed.
- Remaining live tasks: **T028, T040, T048, T056, T069, T080, T091**. These are linked evidence gates, not seven separate authorizations/runs; reuse the approved evidence set when available.
- Re-running convergence before resolving those gates cannot turn them into implemented functionality. Do not add runtime Python, weaken policy, fabricate acceptance results or infer a target from the current kubeconfig.
