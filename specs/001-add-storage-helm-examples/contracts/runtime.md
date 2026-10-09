# Runtime, Logging, and Lifecycle Contract

**Status**: Phase 1 contract under the externally corrected-initdata prerequisite in [research](../research.md#r7--genuine-sealed-secret-mode-upstream-prerequisite). Current stock initdata is not represented as satisfying verified sealed-mode trust.

## Main-container startup gate

1. Emit `storage_wait` identifying the configured path and timeout.
2. Confirm the intended filesystem/source from the main container, using the resolved dynamic helper identity when a helper owns the mount. A directory, symlink, fixed PID, or helper marker alone is insufficient.
3. Bound mount discovery and accessibility checks by `startup.timeoutSeconds`; individual network/filesystem operations also need bounded supervision. On failure, log `startup_failed stage=storage reason=mount_timeout created=false file_check=not_run`, exit nonzero, and never touch the demonstration file.
4. Emit `storage_accessible` only after the access gate succeeds. Derive the stable release-specific filename on that storage.
5. If absent, create without clobbering an existing file, write the fixed sentence plus one newline, close it, and read back for exact verification. If already present, verify without writing. Refuse symlinks, nonregular files, traversal, unreadable files, and mismatched content.
6. Emit exactly one successful file-result event for this start, then `exec` the foreground application. On file failure, emit an explicit failure and exit nonzero without launching the application.

The allowed public prose is: `This file demonstrates persistent storage for this confidential container example.`

## Result events

Stable event names and key-value fields are a test interface, not just free-form log messages. Escape field values so input cannot inject additional log records.

| Event | Required fields | Meaning |
|---|---|---|
| `storage_wait` | `path`, `timeout_seconds` | Waiting for storage available to the main container. |
| `storage_accessible` | `path`, `source`, `filesystem` | Correct mounted storage is accessible in the application's view. |
| `file_created` | `path`, `previously_existed=false`, `created=true`, `verified=true`, `expected_prose` | File was absent, created, and read back successfully. |
| `file_existing_verified` | `path`, `previously_existed=true`, `created=false`, `verified=true`, `expected_prose` | Existing content matched; no recreation. |
| `startup_failed` | `stage`, `reason`, `path`, `created`, `verified=false`, `successful_condition=none` | Neither verified creation nor existing expected prose was confirmed. |

Failure reasons include `mount_timeout`, `mount_source_mismatch`, `helper_unavailable`, `key_denied`, `key_empty`, `unlock_failed`, `file_type_invalid`, `content_mismatch`, `read_failed`, `create_failed`, and `readback_failed`. A readback failure after creation truthfully reports `created=true` but `verified=false`; it is never a success. No response bodies, arbitrary existing file contents, passphrases, sealed payloads, or shell tracing appear in logs.

Implementation uses `key_empty_or_invalid` for the byte-contract failure. If external I/O supervision kills a file operation before its result can be known, `file_check_timeout` reports `created=unknown`, not a false assertion that nothing was written. Readiness also compares the public prose and cannot remain Ready after its loss/mismatch.

## Continued operation

- Readiness runs in the main container and requires the intended storage to remain accessible and initial demonstration verification to have succeeded. Do not rely only on an HTTP process or a marker in a nonpersistent volume.
- A bounded startup probe permits the mount gate to run; no early liveness probe restarts healthy initialization. Deployment progress deadlines exceed the configured startup window and allow guest image-pull time.
- Pod deletion causes automatic replacement against the same claim/export. Native helper sidecars must cleanly handle reopen/remount and filesystem ownership; no fixed process ID, `eval`, or forced reformatting.
- A new mount wait must identify the current helper process/generation, not reuse stale PID files or readiness from a previous helper instance.
- Encrypted initialization uses a chart-local fail-closed state machine with the Red Hat image's cryptsetup/XFS utilities, not the stock binary's destructive probe-error fallback. A current validated PID/generation and correct mount source are required before the main container uses proc-root access.
- Sealed mode requires Kata/CDH signature-verified unsealing using corrected operator-supplied initdata and guest-local trust material. Missing/invalid signatures, unavailable trust, denied attestation, or an unprocessed `sealed.` value fail startup; the chart does not silently relax verification or mutate pattern resources.
- Startup/readiness probes require the selected agent policy to permit their exec requests. Restrictive overrides that deny them cannot satisfy Ready acceptance; logs-only diagnosis does not weaken the policy and is not independent mount/encryption verification.
- Shared storage is not a backup guarantee. A forced pod deletion or node failure may require CSI detach/reattach; do not delete the claim to fix attach errors.

## Uninstall

- Helm-owned resources have no retain annotation or resource-preserving uninstall hook. Uninstall removes the Deployment, account, scripts/configuration, optional scoped bindings, chart-owned sealed-envelope Secret, and block PVC.
- CSI `Delete` reclamation removes the PV and backing volume asynchronously. Verification records PV/backend identity before uninstall and checks actual deletion afterward. `helm uninstall --wait` by itself is not proof of backend deletion.
- Existing Trustee key, initdata/pull Secrets and ConfigMaps, storage class, SCC, namespace, NFS server/export/data, and externally supplied key Secrets are unowned and remain.
- NFS demonstration files remain on the external export; documentation distinguishes them from chart-owned artifacts rather than deleting external data during uninstall.
