# Confidential storage examples

Three independent, readable Helm demonstrations for Red Hat confidential containers on bare-metal OpenShift:

| Example | Storage flow |
|---|---|
| [block-storage-plain](block-storage-plain/README.md) | Safely format blank raw-block media as unencrypted XFS and mount it in the application. |
| [block-storage-encrypted](block-storage-encrypted/README.md) | Prepare/unlock LUKS/XFS in the guest with attested curl, genuine CoCo sealed-token or explicitly insecure existing-Secret key delivery. |
| [nfs-direct](nfs-direct/README.md) | Mount an existing NFS export directly inside the application, without PV/PVC. |

Each main entrypoint waits for verified intended storage before creating/readback-verifying a public prose file or verifying matching existing prose. Deployments preserve storage access across pod replacement. Use distinct Helm release names to coexist; each directory includes its own chart, shell, values, guide and static checks. No runtime Python, custom image builds or shared chart framework.

Defaults select `kata-cc`, same-namespace coco-pattern `debug-initdata` and Red Hat images. Essential initdata/image/class/key/NFS overrides are documented locally; disconnected operation uses full image-reference overrides without startup package downloads. Guest policy must allow required mount/access and read-only exec probes; charts never silently relax it. Sealed mode additionally assumes externally corrected signing trust and uses the same single configured Trustee encryption resource.

**Testing only: delete and recreate releases for chart changes; upgrades are unsupported.** Pod replacement preserves the claim. Block release uninstall deletes owned claims/data through a compatible Delete provider; NFS export/data, external Secrets/initdata and Trustee infrastructure remain unowned and preserved.

CI runs static lint/render/source/package checks only—not workloads, images or clusters. Static results do not prove runtime persistence, attestation, encryption or provider reclamation. See the [static validation guide](specs/002-simplify-storage-charts/quickstart.md). Existing untracked staging samples remain untouched; previous live tooling/specification evidence remains available in Git history and prior feature records.
