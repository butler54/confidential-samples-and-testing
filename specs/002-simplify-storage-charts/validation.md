# Simplification Validation

## Scope and initial state

2026-10-09, branch `003-simplify-storage-charts`. Initial changes: `.specify/feature.json` and this untracked feature directory; existing untracked `staging/fio-script/` and `staging/sample-containers/` are excluded. Prior `specs/001-add-storage-helm-examples/` records remain unchanged.

Static validation only: no runtime shell tests, images, registry pulls, cluster access, Trustee edits or storage deletion. Releases are delete/recreate only. Numeric reduction targets are assessed alongside readability; the mandatory outcome is substantive net simplification without weaker storage safety. Final `0.2.0` assertions are introduced with T032, not intermediate checkpoints.

## Baseline

| Chart | Values leaves | Template lines | Actions | Helpers |
|---|---:|---:|---:|---:|
| Plain | 34 | 367 | 304 | 11 |
| Encrypted | 41 | 383 | 313 | 11 |
| NFS | 37 | 347 | 294 | 11 |

All template files including NOTES/helpers counted; leaves count scalars/lists/empty maps as one. Baseline schemas contain 30 densely packed lines each, with cross-chart properties. Runtime main/storage-access scripts dispatch among all three flows and contain a separate timeout reporter.

## Tooling and inventory

Local Helm 3.22.0, Python 3.12.15, ShellCheck 0.11.0. CI retains Python 3.12.12. Development dependencies remain PyYAML 6.0.2 and shellcheck-py 0.11.0.1; no runtime Python.

Existing render/common-contract/override/isolation tests supplied static assertions to adapt. Startup/storage-access/format/encrypted-key/helper/NFS tests execute workload shell; collection/cleanup/live CLI tests execute auxiliary CLI logic. Image/prerequisite/live/uninstall tooling is operational, not static validation. Files were inspected through source/AST classification without invocation, then retired after replacement checks passed. No uninvestigated/untracked files or caches were removed.

### Exact retirement inventory

Within each chart's `tests/`, removed `conftest.py`, `live.py`, `live_support.py`, `check-images.sh`, `check-prerequisites.sh`, `verify-live.sh`, `verify-uninstall.sh`, `test_cleanup_support.py`, `test_collection.py`, `test_common_contract.py`, `test_isolation.py`, `test_live_cli.py`, `test_overrides.py`, `test_render.py`, `test_startup.py`, `test_storage_access.py`, and `fixtures/initdata-values.yaml`/`fixtures/mirror-values.yaml`.

Also removed plain `test_format.py`; encrypted `test_encrypted_storage.py`, `test_helper_identity.py`, `test_key_delivery.py`, `test_signature_normalization.py`; NFS `test_nfs_mount.py`. That is 60 investigated obsolete files, not a broad directory deletion. Their interfaces depended on retired framework options/synthetic runtime inputs; useful static assertions now live in each independent `tests/static.py`. Git history preserves the old code and prior feature records preserve its historical evidence.

Removed each `templates/_helpers.tpl` and encrypted `templates/sealed-secret.yaml`: concrete names/labels and chart-specific schemas replace the former, and sealed tokens now exclusively reference existing operator-owned Secrets. No runtime capability or unowned resource was deleted by these source changes.

## Results

All 37 implementation tasks complete. Revised default topology/source assertions first failed against all three legacy hashed names, then passed after specialization. Final local results:

| Chart | Primary positive/negative render cases | Strict Helm lint / ShellCheck / sh -n | Standalone package/render equality |
|---|---:|---|---|
| Plain | 20 | PASS | PASS |
| Encrypted | 27 | PASS | PASS |
| NFS | 24 | PASS | PASS |

71 primary render/rejection cases, plus package renders and source guards. This is not a runtime test count. Packages contain all needed scripts, no sibling dependencies, tests or Python; README documentation may be packaged but is never injected into the scripts ConfigMap. Metadata is chart 0.2.0/app 1.13.1 with the retained minimum platform and explicit Red Hat image defaults. No workload script or image was executed.

Essential coverage: default/named/inline/cluster-default initdata and precedence, full helper/utility mirrors, pull references, resources, class/capacity, SCC opt-in, three key paths, missing/conflicting sources, invalid resource/mode/input rejection, IPv6/root NFS export, 53-character/dotted/default release names. Synthetic inline bytes test annotation selection only, not validity of real guest initdata or signing trust.

Four-release static comparison (`plain`, `encrypted`, `nfs`, `plain-two`) found 15 distinct resource identities, four distinct selectors and four prose names. Per-chart tests also vary namespace/file identity. A fixed `-sa` suffix prevents use/adoption of the namespace default account even for a release named `default`; all optional SCC subjects match their release account. External Secrets, initdata, NFS/Trustee infrastructure are referenced, not rendered/adopted.

## Measured simplification

| Chart | Values leaves before → after | Template lines before → after | Actions before → after | Helpers before → after | Runtime shell lines before → after | Schema bytes before → after |
|---|---|---|---|---|---|---|
| Plain | 34 → 19 | 367 → 147 | 304 → 54 | 11 → 0 | 277 → 205 | 5300 → 2897 |
| Encrypted | 41 → 28 | 383 → 171 | 313 → 67 | 11 → 0 | 395 → 343 | 5300 → 3952 |
| NFS | 37 → 16 | 347 → 121 | 294 → 50 | 11 → 0 | 246 → 179 | 5329 → 3032 |

Every chart meets the numeric targets as well as the mandatory net reduction. Template lines decreased 60%/55%/65%; actions decreased 82%/79%/83%. Zero chart-name storage branches, runtime `SAMPLE_KIND` dispatch, unused default roles or custom CPU/memory/token template parsers remain. Schemas were expanded into readable groups but also decreased in bytes and unrelated properties, so complexity was not relocated into them. Shell shrank while retaining meaningful safety functions.

## Static source review

Assistant source walkthrough ran 04:43:00–04:43:50 UTC (50 seconds combined for the familiar three flows), followed by account/mapper edge-case review. This is an assistant review within the planned time budget, **not** an independent human comprehension study or runtime measurement.

| Example | Source/preparation | Main access and key source | Observable outcome/cleanup intent |
|---|---|---|---|
| Plain | Owned raw Block claim; inspect and prove blank bytes before XFS formatting, otherwise reuse compatible XFS | Main mounts/verifies the raw device; no key | Create/readback or existing exact prose; claim persists across pod replacement, disposable on uninstall through Delete provider |
| Encrypted | Owned raw Block claim; key-tested LUKS/mapper/XFS preparation by native helper | Selected CDH curl or existing Secret PASS; unset PASS before any child; current PID/start generation/mount verified through proc-root | Pinned prose and current readiness; cleanup installed before acquisition; external key/trust resources preserved |
| NFS | External configured export; direct mount in main, bounded preparation/file operations | Exact source/type/access verified; no key or Kubernetes NFS volume | Pinned prose/current readiness; bounded best-effort unmount, no export/file deletion |

Five failure classes reviewed in source: missing/wrong keys fail without fallback; unavailable/wrong storage blocks prose/ready publication; incompatible media is never converted; prose mismatch/read errors fail without rewrite or arbitrary-content logging; inspection errors cannot establish blank media. File creation uses noclobber and a pinned working directory; readiness rechecks current source/helper and pinned view. Timeouts report failure after finite grace rather than maintaining a separate background reporter. These are intended safeguards, not dynamically exercised guarantees.

## Final gates and limitations

Static CI configuration and Markdown/local-link checks passed; `git diff --check` passed. Git ignore coverage was verified for environments/caches, secret inputs and archives; no unrelated technology ignore file was needed. Protected staging and prior-spec paths have no tracked changes. No tracing/eval, new service/image build, cluster-wide grant, policy relaxation, signature bypass, Trustee change or destructive live action was added.

Constitution review passes: self-contained Helm examples, downstream defaults, no image builds, explicit 0.2.0 version change, static read-only CI and documented operational purpose for retained safety/permissions. **GitHub CI has not been observed for these uncommitted changes and must pass before merge.** Static results do not certify guest execution, attestation/unsealing/encryption, NFS behavior, pod persistence, backend reclamation or cold-reader timing. No live test is required or authorized by this feature.
