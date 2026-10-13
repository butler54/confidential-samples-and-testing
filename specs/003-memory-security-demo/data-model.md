# Data Model: Confidential Memory-Security Demonstrations

Manifest- and values-level entities. There is no persistent application state; all data lives in chart values, rendered manifests, and `emptyDir` memory volumes. Relationships are K8s-native (labels reference, service selector, route→service).

## memory-security chart

### MagicString (content entity)

| Field | Type | Default | Rules |
|---|---|---|---|
| `magic.string` | string | `MyMagicKeyIsABanana` | Non-empty; ≤ 1 MiB served file; grep-safe single-line recommended; distinctive (walkthrough greps for it case-insensitively) |

Rendered **only** into `configmap-magic-string` (data key `magic.txt`); static checks assert the string never appears in pod command args or annotations.

### Endpoint (cluster-hosted website)

| Object | Key fields | Notes |
|---|---|---|
| Deployment `<release>-magic` | image `images.magicServer`, port 8080, ConfigMap volume mount, restricted securityContext | runc tier; 1 replica |
| Service `<release>-magic` | ClusterIP, port 80→8080 | selector by release labels |
| Route `<release>-magic` | `spec.host: route.host` (required value); `tls.termination: edge`; `insecureEdgeTerminationPolicy: Allow` — plaintext HTTP served **by design** as the documented, demonstration-only exception | single hostname serves HTTPS and HTTP always |

### Demo tier pods (graduate trust, R5)

| Pod | runtimeClass | initdata | Extra rendering rules |
|---|---|---|---|
| `<release>-standard` | default runc (absent) | none | none |
| `<release>-kata` | `kataRuntimeClassName` (default `kata`) | none | none |
| `<release>-coco` | `ccRuntimeClassName` (default `kata-cc`) | `coco.io/initdata-configmap: <initdata.configMapName>` when set (non-empty); `io.katacontainers.config.hypervisor.init_data: <initdata.encoded>` when `encoded` set (wins) | vCPU/memory hypervisor annotations inherited per values |

All three: `fetch-key` initContainer (image `images.demo`) running `curl -ks https://<route.host>/magic.txt -o /keys/magickey.txt`; main container `sleep infinity`; `emptyDir{medium: Memory}` at `/keys`; restricted-compatible securityContext; resource defaults 2 vCPU/4Gi for VM tiers per predecessor demo.

### Transport comparison pair (chart-inherent)

| Pod | Scheme | Rendering condition |
|---|---|---|
| `<release>-fetch-https` | `https://<route.host>/magic.txt` (`curl -k`) | always rendered |
| `<release>-fetch-http` | `http://<route.host>/magic.txt` | always rendered — the chart's documented, demonstration-only HTTP exception |

Both are `kata-cc` + initdata (per coco rules above), same shape as tier pods. HTTP must appear in exactly one rendered container command; enforced by static checks (FR-003 confinement). No feature flag exists: the pair and the `Allow` route are inherent to the chart.

### initdata selection (entity shared chart-wide)

| Value | Default | Rule |
|---|---|---|
| `initdata.configMapName` | `debug-initdata` | empty string → no kyverno annotation (cluster default) |
| `initdata.encoded` | `""` | when non-empty, wins over configMapName (hypervisor annotation, quoted) |

### Values entity (memory-security)

```text
runtimeClassNames: {coco: kata-cc, kata: kata}
initdata: {configMapName: debug-initdata, encoded: ""}
images: {demo: registry.access.redhat.com/ubi9/ubi:9.6, magicServer: registry.access.redhat.com/ubi9/httpd-24:<tag>}
imagePullPolicy: IfNotPresent
imagePullSecrets: []
magic: {string: MyMagicKeyIsABanana}
route: {host: ""}                    # REQUIRED FQDN at install
resources: {demo: {...}, endpoint: {...}}   # defaults per sibling style
```

All image values also accept a disconnected-mirror registry substitution (string replace against `registry.access.redhat.com/` prefix documented; consistent with sibling override style).

### Helper scripts (debugging tooling)

| Script | Inputs → Output |
|---|---|
| `scripts/get-pod-uid.sh <pod> <namespace>` | pod UID on stdout (for host fs path) |
| `scripts/get-pod-mac.sh <pod> <namespace>` | OVN MAC on stdout (for QEMU PID match) |

### Tooling images (documented, not chart-rendered)

| Tool | Image source | Used in |
|---|---|---|
| coredump helper (`gcore`) | built in `butler54/containers`, pinned reference | walkthrough node-debug steps |
| network-tools (`tcpdump`) | Red Hat `network-tools-rhel9` image | host-node capture steps |

## kbs-client chart

### Client workload

| Object | Key fields |
|---|---|
| Deployment `<release>-client` | single container, image `images.client` (pinned `butler54/containers` build), `sleep infinity`, `kata-cc` + initdata selection identical to memory-security entity |
| Values | `images.client`, `runtimeClassName`, `initdata.*` (same table), `kbs.address: ""` (documented Trustee base URL override; README supplies default-construction one-liner), `resources`, `imagePullSecrets` |

## Lifecycle & invariants

- Everything is release-scoped; deleting a release removes all rendered objects (delete/recreate only — no upgrade flow, per repo testing-only stance).
- Invariants enforced statically: (1) string content confined to the ConfigMap; (2) exactly one pod and container command uses HTTP; (3) route always has `tls.termination: edge` + `Allow` and the route/pod templates carry the demonstration-intent marker comments; (4) `route.host` non-empty at render; (5) every image field non-empty and tag-pinned (`:<tag>`, no `:latest`).
