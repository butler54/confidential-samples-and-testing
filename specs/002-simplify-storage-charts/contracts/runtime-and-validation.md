# Runtime Intent and Static Validation Contract

This feature preserves intended runtime behavior but validates it **statically only**. No cluster, container/image, mount, formatting, key retrieval, pod replacement or uninstall execution is authorized. Deployment/install snippets in final example READMEs are for developers' future testing, not commands for this workflow to execute.

## Concrete topology

| Chart | Containers | Data access |
|---|---|---|
| Plain | Formatter init; application | Main mounts the inspected/formatted claim directly as XFS. |
| Encrypted | Curl init only in curl mode; native restartable helper init-sidecar; application | Helper owns LUKS/XFS mount; shared process namespace exposes its verified current proc-root filesystem to main. |
| NFS | Application only | Main mounts expected NFS source directly; no Kubernetes NFS volume. |

One replica and Recreate strategy. No guessed helper PID, postStart ordering gate, bidirectional mount propagation or ready-marker-only storage validation. Application-visible access must precede prose writes and readiness. Memory control volume is not demonstration storage.

## Safety/readability boundary

- Shell commands operate on explicit validated inputs with quoted arguments, no `eval`, tracing or package installation.
- Inspect raw media without treating tool errors as empty media. Missing signatures alone are insufficient: confirm whole-device zero content before initialization. Preserve compatible XFS/LUKS, deduplicate identical LUKS signatures, reject conflicting/unknown signatures. Never force-format or use the stock helper's unsafe fallback.
- Encrypted mapper must match its backing device; validate the selected key even when a mapper exists. Install scoped cleanup before acquiring resources/publishing active helper state, and remove readiness/state on termination. Keep curl key state private for native helper restarts; clear exported PASS before child processes, and reject unprocessed sealed tokens.
- Verify mounted source/type and current encrypted helper identity. Keep one pinned storage view for file operations so a path substitution/unmount does not redirect writes to the container root. Required permissions remain external lab prerequisites.
- Create only absent prose, verify readback, accept existing matching prose without rewriting, and log only public expected content/status. Preserve symlink/content safeguards and bounded NFS/storage operations.
- Surface created, existing/verified and failed outcomes explicitly. A failed mount/key/helper/prose check cannot leave the workload falsely ready. No new health service to bypass exec-denying policy.

Keep these checks explainable and local; do not rebuild a generalized process supervisor, storage abstraction or configuration framework. Consolidating files is acceptable only if flow becomes easier to follow and the whole safety logic remains reviewable.

## Static acceptance matrix

| Area | Required checks | Evidence limits |
|---|---|---|
| Base charts | Helm strict lint, valid YAML, one Deployment/account/config, block PVC only where needed | No scheduling/CSI guarantee. |
| Essential inputs | Class/capacity, complete mirrors/pull references, resources, SCC opt-in, initdata default/inline/cluster-default | No registry pulls or guest policy execution. |
| Encrypted modes | Curl init only in curl; secret reference only in sealed/insecure; shared PID/native sidecar; conflicting/missing/invalid source rejection | No live attestation, unsealing or cryptsetup claim. |
| Negative configuration | Invalid mode, malformed resource path, missing Secret, missing NFS server/export, invalid timeout, unknown/cross-chart keys | Reject through schema/small required expressions, not a generic validator. |
| Isolation/ownership | Four releases, namespace-varied filename identity, stable replacement references, external resources never emitted/adopted | No concurrent workloads or provider-deletion evidence. |
| Shell/content | `sh -n`, ShellCheck; statically trace preparation → mount gate → prose → ready and failure cleanup | Never invoke workload scripts or runtime-mocking test suites. |
| Packaging/version | Chart 0.2.0, app baseline retained, nonfloating images, only runtime scripts in ConfigMap, tests/docs excluded from packaged runtime content | No image execution or builds. |
| Readability | Same-method before/after counts and ≤10-minute reviewer walkthrough of each flow | Explicit human review, not fabricated user studies. |

## Runner and CI

Chart-local `tests/run.sh` becomes an explicitly static entrypoint: lint, render/parse assertions, shell syntax/lint, package-content and metadata checks. A small local static checker may use Python/Helm on developer machines; it must not call workload scripts, import legacy runtime test suites, connect to a cluster or pull/run workload images. No runtime Python is packaged.

Update existing read-only CI matrix to run only this entrypoint with pinned tools/parser dependencies. Useful old static assertions may be retained/adapted; obsolete framework assertions and dynamic tests must be deliberately classified before retirement, not silently ignored. No live/image/backend tooling is required by the new guides or CI.

Successful static validation is completion evidence for this feature, not proof of runtime security or persistence. GitHub CI must actually pass before merge; writing a plan or running local lint is not proof that CI ran.
