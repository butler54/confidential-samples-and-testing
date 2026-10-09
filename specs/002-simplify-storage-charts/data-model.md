# Data Model: Teaching Examples

No service database or API model is introduced. These are workload resource and file lifecycles.

## Example

**Fields**: chart name, documented storage kind, applicable values, owned templates/scripts, explicit image versions, static validation entrypoint.

**Rules**: One storage kind per chart; encrypted key mode is the only storage-specific runtime alternative. Each directory is independently usable. Relevant configuration follows [values contract](contracts/values.md).

## Release

**Fields**: namespace, Helm release name, chart identity, account, Deployment, scripts ConfigMap, optional scoped SCC binding, block claim when applicable.

**Identity**: Full release name with short literal suffixes; chart/release selectors. No legacy hash wrapper or truncation. Ownership is Helm release ownership only, never adoption of external references.

**Transitions**: not installed → installed → pods replaced while original claim remains → explicitly uninstalled. Chart revision changes require uninstall → install; no upgrade transition. Block data is disposable on uninstall, subject to external Delete reclamation. Pod replacement is not release deletion.

## Storage View

**Fields**: fixed application mount path, intended source, filesystem type, stable open directory view for file operations, encrypted helper identity/backing mapper when applicable.

**Relationships**: Plain release owns one raw-block claim; encrypted release owns one raw-block claim and its in-guest mapper lifecycle; NFS references external server/export. Plain/NFS mount in the main container. Encrypted main accesses the verified native sidecar's guest filesystem through current process identity, not assumed shared mount namespaces.

**Transitions**: waiting → compatible media inspected → prepared/unlocked → mounted/source verified → pinned/application accessible → prose verified → ready. Any failure invalidates success/readiness; never proceed on temporary storage. Only confirmed blank media may be initialized. Helper replacement cannot silently reuse stale state.

## Demonstration File

**Fields**: chart/release/namespace-isolated basename, public expected prose, created/existing outcome.

**Transitions**: absent → safe create/readback → verified; existing expected prose → verified without rewrite; unexpected/unreadable content → failure without overwrite. File operations use the verified storage view, not unchecked path re-resolution.

## Key Reference (encrypted only)

**Fields**: mode, one KBS resource path, existing Secret name/key for sealed or insecure mode, transient private in-guest key transport.

**Rules**: Curl uses guest CDH-mediated attestation; sealed mode uses agent/CDH unsealing and external signing trust; insecure mode is explicitly labeled insecure. Keys are not resources managed by this chart. No plaintext values, tracing, command-line keys or secret-bearing diagnostic output. No source fallback. Any temporary key state is private and cleaned up.

## Static Evidence

**Fields**: tool versions, lint/render outcomes, positive/negative contract checks, before/after complexity counts, human flow review, limitations.

**Rules**: Evidence refers only to static properties. No assertion of executed attestation, mounted storage, persistence, runtime readiness or backing-volume deletion. Prior feature results remain historical, not new acceptance evidence.
