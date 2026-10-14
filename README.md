# Confidential samples and testing

Independent, readable Helm demonstrations for Red Hat confidential containers on bare-metal OpenShift.

## Storage examples

| Example | Storage flow |
|---|---|
| [block-storage-plain](block-storage-plain/README.md) | Safely format blank raw-block media as unencrypted XFS and mount it in the application. |
| [block-storage-encrypted](block-storage-encrypted/README.md) | Prepare/unlock LUKS/XFS in the guest with attested curl, genuine CoCo sealed-token or explicitly insecure existing-Secret key delivery. |
| [nfs-direct](nfs-direct/README.md) | Mount an existing NFS export directly inside the application, without PV/PVC. |

Each main entrypoint waits for verified intended storage before creating/readback-verifying a public prose file or verifying matching existing prose. Deployments preserve storage access across pod replacement. Defaults select `kata-cc`, same-namespace coco-pattern `debug-initdata` and Red Hat images. Essential initdata/image/class/key/NFS overrides are documented locally; disconnected operation uses full image-reference overrides without startup package downloads. Guest policy must allow required mount/access and read-only exec probes; charts never silently relax it. Sealed mode additionally assumes externally corrected signing trust and uses the same single configured Trustee encryption resource.

## Observability and utility examples

| Example | Demonstration |
|---|---|
| [memory-security](memory-security/README.md) | Graduate host memory visibility across ordinary, sandboxed and confidential tiers, and show that HTTP (unlike HTTPS) leaves data in host memory buffers. Serves its magic string from a cluster-hosted endpoint over an HTTPS+HTTP route — no GitHub reach required. **DEMONSTRATION ONLY: the endpoint intentionally exposes plaintext HTTP, confined to one designated fetch pod.** |
| [kbs-client](kbs-client/README.md) | Minimal confidential key-broker client pod for manual, attestation-gated retrievals from the cluster Trustee; independent of the other examples. |
| [io-benchmark](io-benchmark/README.md) | Serial, cache-defeating IO benchmark (fio) across plain/kata/coco pods with ±guest-side LUKS; results land in a Markdown table plus self-describing local Apache Iceberg tables. Tooling image `perf-utils` is built externally and consumed overridable; the control-side runner is the only approved runtime-Python tool in the repository (spec 004). |
| [gpu-benchmark](gpu-benchmark/README.md) | Serial GPU LINPACK benchmark (NVIDIA HPL fp64 + HPL-MxP mixed) on H100-or-newer GPUs, single-GPU or full-system (NVLink), confidential (`kata-cc-nvidia-gpu`) vs standard pods with verification-gated results and an explicit delta. Benchmarks are a declarative YAML catalog; the workload image is NVIDIA's published HPC-Benchmarks collection; the control-side runner is an approved tool (spec 005). |

These examples supersede the retired `butler54/coco-baremetal` test workflows (their contents, plus an offline-capable endpoint and the HTTP/TLS comparison). Tooling images they reference (coredump helper, key-broker client, perf-utils) are built in `butler54/containers` and consumed pinned/overridable; nothing is built in this repository.

Shared conventions: use distinct Helm release names to coexist; each directory includes its own chart, shell/values, guide and lint/shell checks. No runtime Python except where explicitly approved (io-benchmark, gpu-benchmark), no custom image builds, no shared chart framework.

**Testing only: delete and recreate releases for chart changes; upgrades are unsupported.** Pod replacement preserves the claim. Block release uninstall deletes owned claims/data through a compatible Delete provider; NFS export/data, external Secrets/initdata and Trustee infrastructure remain unowned and preserved.

CI runs Helm lint and shell checks only—not workloads, images or clusters. Validation results do not prove runtime persistence, attestation, encryption or provider reclamation. See the [static validation guide](specs/002-simplify-storage-charts/quickstart.md). Existing untracked staging samples remain untouched; previous live tooling/specification evidence remains available in Git history and prior feature records.
