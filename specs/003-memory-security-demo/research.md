# Research: Confidential Memory-Security Demonstrations

Phase 0 output. Every decision here resolves a Technical Context or design unknown from the plan. Sources: predecessor `butler54/coco-baremetal` (BAREMETAL-tests.md, `charts/coco-testing`, get-*.sh helpers), this repository's simplified sibling charts (`block-storage-plain`, `block-storage-encrypted`, `nfs-direct`), and the repo constitution.

## R1: How is the cluster-hosted magic-string endpoint built?

**Decision**: A single-container Deployment using the Red Hat `ubi9/httpd-24` image, serving a ConfigMap-mounted file (`static/index.txt`) whose content is the configurable magic string. Exposed through a ClusterIP Service (port 8080 target) and one OpenShift Route.

**Rationale**: Downstream-first (constitution III), unprivileged (httpd-24 runs as an arbitrary UID on 8080, no SCC needed), no custom image build (constitution IV), ConfigMap content keeps the string overridable without editing manifests (FR-004).

**Alternatives considered**: nginx S2I image (equivalent; httpd-24 chosen because it is the most commonly mirrored RHEL S2I web base); `ubi9/ubi` + python http.server (rejected — platform-python is not a documented serving path and weakens the "plain supported server" story); a custom static-file image (rejected — constitution IV forbids in-repo builds and none is needed).

## R2: How are HTTP and HTTPS both exposed, and how is plaintext exception documented?

**Decision**: One edge-terminated Route (`spec.tls.termination: edge`, default cluster wildcard certificate) with `spec.tls.insecureEdgeTerminationPolicy: Allow` **always rendered**. A single hostname serves HTTPS on 443 and plaintext HTTP on 80. There is no enable flag and no render variant: HTTPS is the default behaviour for every workload, and plaintext HTTP exists solely as the chart's explicitly documented, demonstration-only exception — marked in the route template comments, the `Allow`-policy template comments, the README walkthrough, and post-install NOTES.

**Rationale**: Revised per user direction (2026-10-13): the comparison is the chart's entire purpose, so HTTP is a first-class, documented feature rather than a toggle to forget or misconfigure. A single hostname serving both schemes gives the pair identical paths with only the scheme different; the delete/recreate lifecycle means the secure posture returns by deleting the release.

**Alternatives considered**: an opt-in `transport.plaintext.enabled` flag gating the HTTP pod and `Allow` policy (rejected by user — "Do not gate by a flag. Just explicitly document that it's intended in the chart"); two separate routes, one HTTP-only (rejected — second hostname adds DNS/host management and the pair would differ by hostname, weakening control variables); `Redirect` policy (rejected — the plaintext fetch would be upgraded, breaking the demonstration).

## R3: How do fetcher pods know the endpoint URL without GitHub or external discovery?

**Decision**: `route.host` is a **required** chart value (schema enforces non-empty FQDN), exactly as `nfs.server` is required in the sibling chart. The Route is rendered with that host, and every fetcher pod is rendered with the URL derived from the same value (`https://<host>/magic.txt`, or `http://` for the designated pod). The README documents the typical `oc get ingresses.config/cluster` one-liner to construct a default `<name>-<namespace>.<appsDomain>` host and requires distinct hosts for coexisting releases.

**Rationale**: Helm cannot read back assigned route hosts; required-value determinism keeps pods, route, and walkthrough output expectations identical, which FR-008/SC-002 depend on. Pods resolve and reach the wildcard apps domain through cluster DNS/egress — no external network beyond the cluster.

**Alternatives considered**: empty host with template-time unknown (rejected — URL would be unknowable for pods); in-cluster Service DNS for pod fetches (rejected for the demo because the transport test specifically needs traffic to traverse the router; Service DNS also stays as an internal note for future use).

## R4: How does the HTTPS fetcher trust the endpoint?

**Decision**: `curl -k` in the HTTPS fetch pod, loudly commented: TLS still encrypts traffic (the entire point of the buffer observation); `-k` only skips server-certificate verification. The README documents the optional stricter variant — mounting `service-ca` or fetching the ingress CA — as an extension, not a default.

**Rationale**: Keeps the demo's control variable (transport encryption) independent of PKI state on arbitrary lab clusters; avoids silently injecting the cluster CA into initdata trust boundaries; FR-008 requires honest expected-output documentation rather than hidden trust magic.

**Alternatives considered**: default `--cacert` from the ingress operator CA (rejected as default — extra objects and per-cluster CA plumbing, and a wrong CA would make US2 fail before the memory observation starts); plaintext for all pods (rejected by FR-003 explicitly).

## R5: What are the three graduated-trust tiers, concretely?

**Decision**: Pods named `<release>-standard` (no runtimeClassName — runc), `<release>-kata` (`runtimeClassName: kata` — OSC default, non-confidential local Kata), `<release>-coco` (`kata-cc` plus the repo-standard initdata annotation selecting `debug-initdata` by default; `coco.io/initdata-configmap: <name>` when `initdata.configMapName` is set, else hypervisor `init_data` when `initdata.encoded` is set). All three fetch with TLS at startup into an `emptyDir{medium: Memory}` `keys/` volume and sleep; each has a `fetch-key` initContainer using the demo image, mirroring the predecessor chart semantics.

**Rationale**: Matches the predecessor demo tiers preserved by US1 with FR-004/FR-005 repo conventions applied; `kata` requires no CC plumbing (and no initdata annotation — dropped from the predecessor's kata pod); OSC on the target clusters provides the `kata` runtime class.

**Alternatives considered**: fold the kata tier into the coco chart via a values boolean (rejected — concrete per-workload pods match the sibling simplification and make the walkthrough's per-tier sections map 1:1 to files); kata-remote (rejected — not the bare-metal TDX story).

## R6: How are host observations performed (US1 memory dumps)?

**Decision**: Small in-chart helper scripts replace the predecessor's four repo-root one-offs:

- `scripts/get-pod-uid.sh <pod> <namespace>` — prints UID for locating the standard pod's `emptyDir` file on the host.
- `scripts/get-pod-mac.sh <pod> <namespace>` — prints the pod's OVN primary-interface MAC (parses the `k8s.ovn.org/pod-networks` annotation, as the predecessor did).

The walkthrough then runs, per tier's node: `oc debug node/<node>` → privileged debug container using the **coredump-helper tooling image** (built in `butler54/containers`, consumed pinned per FR-011) with `--pid=host` privileges, resolve the QEMU PID by pod MAC, `gcore <pid>`, `strings core.<pid> | grep -ic '<string>'`. Expected outputs are printed in the README: kata ⇒ ≥1 occurrence; coco ⇒ 0 occurrences; TDX flag check documented as platform evidence.

**Rationale**: Preserves the predecessor's proven mechanics; in-chart scripts satisfy constitution II's documented debugging-tooling exception; pinned tooling image satisfies constitution III/IV and FR-011.

**Alternatives considered**: `oc debug` with the UBI demo image + runtime `dnf install gdb` (rejected — needs package mirror reachability during a live demo and hides steps); host systemd/coredumpctl (rejected — qemu cores are not routed to abrt); keeping the predecessor's personal-registry coredump image (forbidden by clarification Q1).

## R7: How is the transport comparison observed at BOTH points deterministically?

**Decision**:

- **Router (ingress node)**: debug the node hosting an ingress router pod; run the coredump-helper privileged debug container; `gcore` the haproxy process; string-search for the magic string. Trigger a fresh fetch in the designated HTTP pod (`kubectl exec` curl loop documented) immediately before the dump so buffers are current. Expected: string present for the HTTP fetch, absent after the TLS-fetch control (with documented caveat that only the string's absence is meaningful — other noise hits are expected).
- **Fetching pods' host node**: `oc debug node/<pod-node>` with the Red Hat `network-tools` debug image starts a packet capture on the pod's egress path (`tcpdump -i any -A 'tcp port 80'` / `port 443`) while the walkthrough re-issues the fetch; HTTP shows the string on the wire in plaintext, HTTPS shows no readable string. Timing and interface selection steps are spelled out so this is copy-paste deterministic.

**Rationale**: The router-side `gcore` is a true *memory-buffer* observation (matches the user's "memory buffers" wording literally); the host-node packet-path capture is the only deterministic kernel-buffer-adjacent observation for traffic crossing a node — raw skbuff searching is not copy-paste reliable, and both capture locations together tell the complete in-transit story the user asked for ("both router and host node").

**Alternatives considered**: host-node `gcore` of the fetch pod's QEMU (rejected — the transport pair is kata-cc, so guest memory is encrypted by design and would show nothing regardless of transport); conntrack/OVS flow tables (no payload); eBPF string tracers (too much tooling for a doc-only demo).

## R8: What does the kbs-client chart deploy?

**Decision**: A single confidential (`kata-cc` + same initdata selection) Deployment with the `kbs-client` tooling image (built in `butler54/containers`, pinned; FR-011) idling (`sleep infinity`), minimal values: `images.client`, `runtimeClassName`, `initdata.*`, `resources`, `imagePullSecrets`. The README documents `oc exec` one-liners to run `kbs-client` with a configurable KBS/resource against the cluster Trustee (address overridable via values `kbs.address`), plus a sample resource path note and cleanup. It is completely independent of `memory-security`.

**Rationale**: Exactly the user's clarification: "independent container… dirt simple independent chart"; constitution I/II friendly; nothing new provisioned into Trustee.

**Alternatives considered**: a fetcher init-container that pulls a KBS secret at start (rejected — that is provisioning logic, not a "dirt simple client pod"); embedding the client as a sidecar in the memory chart (rejected by clarification Q3).

## R9: Static validation design (no live tests)

**Decision**: Each chart ships `tests/run.sh` + `tests/static.py` + `requirements.txt` with the same pinned parser deps as siblings. Assertions (memory-security): every render produces endpoint (Deployment/Service/Route) + three tier pods + the fetch pair (TLS and HTTP fetchers); route always has `tls.termination: edge` + `Allow` and the demonstration-intent marker comments; exactly one rendered command contains an `http://` URL (never zero, never two) and it lives in `<rel>-fetch-http`; `route.host` rejects empty via schema; all images match the pinned-reference policy (registry allow-list incl. `registry.access.redhat.com`, `registry.redhat.io`, and the documented tooling image reference); initdata annotation logic renders per R5; the magic string appears only in the ConfigMap (not in pod args); README/NOTES carry the demonstration-only HTTP notice. kbs-client: default render = Deployment with `kata-cc` + initdata annotation; image pinned; kbs.address required-or-defaulted per contract. CI: extend the existing matrix and path filters to both directories; workflow renamed `Validate examples`.

**Rationale**: Mirrors the contract from the previous storage feature (static-only assurance, honest about unverified runtime behavior); satisfies FR-009/SC-006 without any cluster.

**Alternatives considered**: shared static test library across charts (rejected — repeats the pre-002 framework mistake; small duplication is intentional); OPA/rego policies (rejected — Python asserts match sibling charts).

## R10: What is deliberately NOT carried over from coco-baremetal?

- GitHub Gist URL as the string source (objective 3 — replaced by cluster-hosted endpoint).
- Repo-root helper scripts and their per-tier hardcoded names (R6 generalizes them; release-scoped).
- The chart-owned `namespace.yaml` (release namespace wins; distinct hosts/names per release per R3).
- The kata pod's initdata annotation (no CC machinery needed for the non-CC tier).
- The personal-registry `quay.io/rh-ee-chbutler/coredumps` image (Q1 decision; built in `butler54/containers` instead).

Repo retirement is handled socially per FR-012 (successor notes in both chart READMEs and root README); nothing here modifies the external repo.
