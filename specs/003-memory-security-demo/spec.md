# Feature Specification: Confidential Memory-Security Demonstrations

**Feature Branch**: `004-memory-security-demo`

**Created**: 2026-10-09

**Status**: Draft

**Input**: User description: "Fold the coco-baremetal confidential-container memory-security test workflows into this repository. Deploy the demonstration test pods with a Helm chart compatible with the coco-pattern like the other charts; provide a Markdown document with code blocks for copy-paste step-through testing; host the magic-string website on an OpenShift Route on the targeted cluster instead of GitHub so it works where GitHub is unreachable; add a test showing that HTTPS (as opposed to HTTP) is needed to keep data out of memory buffers; build no automated tests, only simple commands and documentation a user can step through."

## Clarifications

### Session 2026-10-09

- Q: How should the non-Red-Hat tooling images (memory-dump helper and key-broker client) be sourced? → A: Build both in `butler54/containers` and consume them here pinned; the personal-registry coredump image and any upstream client image are replaced by policy-compliant internal builds.
- Q: Where should the walkthrough inspect memory buffers for the plaintext-versus-TLS comparison? → A: Both observation points: the router process on the ingress node and the fetching pod's host node.
- Q: How should the transport comparison be structured so only the designated workload uses plaintext? → A: The cluster-hosted route MUST expose both HTTP and HTTPS endpoints; the chart deploys two confidential pods for the comparison — one fetching the magic string over HTTPS, the other over HTTP — and plaintext HTTP MUST be used only by that specific designated pod (the predecessor repository used HTTPS everywhere; this pair is new functionality).
- Q: What exactly should the attestation client scenario retrieve and where does the resource come from? → A: There is an existing independent container for deploying the kbs client; fold it in as a dirt-simple independent chart — the client utility ships as its own minimal self-contained example (deployable without the memory-demo chart), not as a component of the memory-demo chart.

### Session 2026-10-13

- Q: Should plaintext exposure be gated by a runtime flag? → A: No flag. HTTPS is the default behaviour for every fetcher; HTTP exists solely as the explicitly documented, demonstration-only exception — one route serves both schemes by design and exactly one designated pod uses HTTP. The intended HTTP exposure is documented in the chart itself (values comments, README walkthrough, post-install notes); there is no render variant without it. This supersedes the earlier plan-level opt-in-flag idea for plaintext exposure.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Observe graduated memory visibility across three workload tiers (Priority: P1)

A platform engineer installs a single chart that deploys three pods holding the same customer-facing magic string fetched at startup: an ordinary container, an ordinary (non-confidential) hypervisor-isolated container, and a confidential container whose memory is hardware-encrypted. The engineer then follows the packaged Markdown walkthrough to observe, from the host, how much of that data each tier exposes: the ordinary container's copy is directly readable on the host filesystem; the ordinary hypervisor tier's guest memory dump contains the magic string in plaintext; the confidential tier's guest memory dump contains zero occurrences of the magic string because its memory is encrypted.

**Why this priority**: This is the core demonstration — visually proving that confidential computing prevents host-level memory inspection. Every other objective (cluster-hosted endpoint, copy-paste document) exists to serve or strengthen this story.

**Independent Test**: Install the chart with defaults on a prepared confidential-computing cluster, follow only the packaged walkthrough, and confirm that the ordinary tiers reveal the string while the confidential tier yields zero occurrences. Delivers a complete, demonstrable security observation on its own.

**Acceptance Scenarios**:

1. **Given** a prepared cluster and the chart's default values, **When** the engineer installs the chart, **Then** a cluster-hosted magic-string endpoint and all three workload tiers become ready, and each demonstration pod holds the magic string fetched from the cluster-internal endpoint with no outbound internet or GitHub access required.
2. **Given** the running ordinary-tier pod, **When** the engineer performs the documented host-volume inspection steps, **Then** the magic string is readable on the host without entering the container.
3. **Given** the running ordinary hypervisor-tier pod, **When** the engineer performs the documented guest-memory dump steps, **Then** the dump contains at least one occurrence of the magic string.
4. **Given** the running confidential-tier pod, **When** the engineer performs the same documented guest-memory dump steps against it, **Then** the dump contains zero occurrences of the magic string, and the walkthrough documents the host-level evidence that the platform's memory-encryption capability (e.g., TDX) is active.
5. **Given** two or more installations, **When** the engineer uses distinct release identifiers, **Then** the demonstrations coexist without resource or endpoint collisions.

---

### User Story 2 - Compare plaintext versus encrypted transport visibility in memory buffers (Priority: P2)

The engineer runs the transport comparison using a dedicated pair of confidential pods deployed by the chart: both fetch the magic string from the same cluster-hosted route, but one fetches over TLS and the other over plaintext HTTP. The engineer then searches both documented memory-buffer locations — the ingress router process on its node and the hosting node of the fetching pods. The plaintext fetch leaves the magic string discoverable at both observation points; the TLS fetch leaves no occurrence, demonstrating that transport encryption is required to keep transferred data out of observable memory buffers even when the endpoint is inside the same cluster.

**Why this priority**: Extends the memory-observation story from at-rest/guest memory to in-transit buffers, answering the natural follow-up question "is the same-cluster network path also exposable?" It builds on the Story 1 deployment but is observable independently once the endpoint and the dedicated pod pair exist.

**Independent Test**: Install the chart, run only the transport-comparison section of the walkthrough against the dedicated pod pair, and confirm presence (plaintext pod) versus absence (TLS pod) of the string at both documented observation points.

**Acceptance Scenarios**:

1. **Given** the cluster-hosted route exposed over both HTTP and HTTPS and the dedicated pair of confidential pods running, **When** the engineer verifies the pods' startup fetches, **Then** the TLS-designated pod holds the string fetched over HTTPS and the plaintext-designated pod holds the string fetched over HTTP, and no other workload in the installation uses plaintext HTTP.
2. **Given** the plaintext pod's fetch has completed, **When** the engineer inspects the router process memory on the ingress node and the documented buffers on the pod's host node, **Then** the magic string is found at both observation points.
3. **Given** the TLS pod's fetch has completed, **When** the engineer inspects the same two locations, **Then** zero occurrences of the magic string are found.
4. **Given** a secured cluster configuration where the ingress controller is configured to reject or redirect plaintext traffic, **When** the engineer reads the walkthrough, **Then** the document names this platform prerequisite, describes the failure symptom, and states plainly that the route's plaintext HTTP is intentional, demonstration-only, and confined to the designated pod (secure posture returns upon deleting the release).

---

### User Story 3 - Deploy the key-broker client utility as an independent minimal chart (Priority: P3)

The engineer installs a separate, deliberately minimal chart — independent of the memory-demo example — that deploys the attestation key-broker client as a standalone confidential container on the cluster. The engineer then follows the packaged copy-paste commands to run the client inside that container and retrieve a demonstration resource from the cluster's Trustee key broker, proving attestation-gated secret release.

**Why this priority**: A valuable complementary utility (and existing standalone capability the engineer wants preserved), but it is intentionally "dirt simple", depends on the Trustee component already provided by the underlying pattern, and is not required to demonstrate the primary memory-encryption observation.

**Independent Test**: Install only the independent client chart, follow its short walkthrough to exec into the client container and run the retrieval commands, and observe the demonstration resource returned from the Trustee key broker.

**Acceptance Scenarios**:

1. **Given** only the independent client chart installed on a prepared cluster, **When** the engineer runs the documented commands inside the client container, **Then** a demonstration resource is retrieved successfully from the cluster's Trustee key broker, with the broker address and resource reference configurable through chart values.
2. **Given** the memory-demo example is absent or installed, **When** the engineer installs or removes the client chart, **Then** it deploys, runs, and cleans up independently of it.

---

### Edge Cases

- The cluster lacks confidential-computing runtime classes, initdata propagation, or the Trustee key broker: the walkthrough MUST document prerequisite verification commands that fail loudly before any deployment is attempted.
- The cluster has no outbound internet or GitHub access: every fetch step in every scenario MUST resolve to the cluster-hosted endpoint and succeed.
- Cluster ingress policy blocks or redirects plaintext traffic: the walkthrough MUST document the failure symptom and that the demo requires an ingress configuration where plaintext routes are permitted; the secure posture returns by deleting the release (delete-and-recreate lifecycle).
- The magic-string content or the endpoint credentials/TLS trust need to change per environment: these MUST be overridable through chart and documented inputs without editing manifests.
- Multiple demonstrations run in different namespaces at once: resource names, endpoint hostnames, and any dump-output naming MUST remain unambiguous per installation.
- Freshness of observations: the walkthrough MUST instruct the user to trigger the fetch-and-dump sequence in documented order so stale or zeroed buffers cannot create false negatives, and MUST state expected outputs so users can distinguish "protected" from "test performed incorrectly."
- Node-debug and privileged memory-dump operations are destructive-adjacent host operations: all host-level steps MUST carry explicit caution notes and target only the documented node and process.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The example MUST deploy, via a single Helm chart in its own self-contained directory, three demonstration workloads of graduated trust: an ordinary container, an ordinary hypervisor-isolated (non-confidential) container, and a confidential container with hardware memory encryption; each must fetch and continuously hold the same magic string.
- **FR-002**: The chart MUST deploy a cluster-hosted magic-string web service exposed through OpenShift cluster ingress, so that the magic string can be retrieved entirely within the target cluster with no dependency on GitHub or any external network.
- **FR-003**: The cluster-hosted endpoint MUST be exposed through a route serving both HTTPS (TLS) and plaintext HTTP by design. HTTPS is the default transport for every workload; HTTP exists solely as the explicitly documented, demonstration-only exception. The chart MUST deploy a dedicated pair of confidential-tier pods for the transport comparison — one configured to fetch the magic string over TLS, the other over plaintext HTTP — and plaintext HTTP MUST be confined to that single designated pod; every other workload in the installation MUST fetch over TLS. The intended HTTP exposure MUST be explicit and visible in the chart itself (values comments, README walkthrough, post-install notes); no feature flag or render variant removes it.
- **FR-004**: Magic-string content, workload images, runtime/initdata selection, and endpoint overrides MUST be configurable via chart values; defaults MUST align with this repository's established confidential-container conventions (confidential runtime class, repo-standard initdata integration, Red Hat-supported images, full disconnected-mirror overrides).
- **FR-005**: The chart MUST support coexistence of multiple installations via distinct release identities and MUST follow the chart conventions of the sibling examples in this repository.
- **FR-006**: The example MUST include a Markdown walkthrough document composed primarily of copy-paste command blocks covering, in order: prerequisite verification, installation, the three-tier memory observation, the plaintext-versus-TLS buffer observation, verification of expected outputs, and cleanup/uninstall. The independent client utility chart MUST likewise include its own brief copy-paste usage document covering installation, resource retrieval from the key broker, and cleanup.
- **FR-007**: Every host-level or privileged observation step MUST have a documented, copy-paste command path (small helper scripts are permitted as debugging tooling per repository policy) and MUST be reproducible with the cluster-admin access already documented as a prerequisite.
- **FR-008**: The walkthrough MUST document expected observations for every comparison (what proves protection, what proves exposure, and what indicates the test was performed incorrectly).
- **FR-009**: The feature MUST NOT introduce an automated behavioural test harness; validation is limited to the repository's standard static chart linting/rendering checks plus the manual step-through document.
- **FR-010**: The example MUST document all cluster-side prerequisites (memory-encryption-capable bare-metal nodes, the confidential-containers pattern with its key broker and initdata machinery, and cluster-admin node-debug access).
- **FR-011**: The memory-dump helper and the attestation key-broker client MUST be delivered as images built in the designated external image repository (`butler54/containers`) and consumed here by pinned, immutable references; the personal-registry coredump image used by the predecessor workflows MUST NOT be carried over. No image may be built in this repository.
- **FR-012**: The example documentation MUST identify it as the successor to the external source repository's test workflows, so that repository can be retired once parity is confirmed.
- **FR-013**: The attestation key-broker client utility MUST ship as its own independent, minimal Helm chart in its own self-contained directory, modelled on the existing standalone client container: deployable, usable, and removable without installing the memory-demo chart, with the broker address, resource reference, image, runtime, and initdata selection exposed as values aligned with this repository's conventions. No additional platform components may be introduced to support it.

### Key Entities

- **Magic string**: A distinctive, overridable demonstration secret served by the cluster-hosted endpoint and held by every tier; its presence or absence in dumps/buffers is the observable signal.
- **Demonstration tiers**: The three workload placements (ordinary, ordinary hypervisor, confidential) sharing identical contents but with different host visibility guarantees.
- **Cluster-hosted endpoint**: The in-cluster web service and its ingress route that serves the magic string over TLS and plaintext HTTP (plaintext confined to the designated comparison pod), removing external dependencies.
- **Transport comparison pair**: The two dedicated confidential pods — one fetching over TLS, one over plaintext HTTP — used to demonstrate buffer leakage; plaintext HTTP is confined to the designated pod.
- **Observation walkthrough**: The step-through document that couples each command block to its expected security observation.
- **Attestation key broker**: The cluster-provided Trustee service whose client utility demonstrates attestation-gated secret release; an external prerequisite, not something this feature deploys.
- **Client utility chart**: The independent, minimal chart that deploys the key-broker client as a standalone confidential container for manual, command-driven use; separate from, and not dependent on, the memory-demo chart.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An engineer with a prepared cluster can complete the entire walkthrough (install through cleanup) in under 60 minutes using only the packaged document and commands.
- **SC-002**: 100% of command blocks in the walkthrough execute by copy-paste with only the explicitly documented placeholder substitutions (such as a node name), on first attempt.
- **SC-003**: Across runs on a memory-encryption-capable platform, the ordinary hypervisor tier's memory dump contains the magic string and the confidential tier's dump contains exactly zero occurrences, in 100% of correctly executed runs.
- **SC-004**: The plaintext-designated pod's fetch leaves the magic string discoverable at both documented observation points (ingress router node and the pod's host node), and the TLS-designated pod's fetch leaves zero occurrences at the same points, in 100% of correctly executed comparisons.
- **SC-005**: Every fetch operation succeeds in an environment with no outbound access to github.com or the public internet.
- **SC-006**: The chart passes the repository's standard static validation (lint and render checks) and installs and uninstalls cleanly with default values.
- **SC-007**: All three user stories are reproducible using only this repository plus the documented cluster prerequisites, with zero references to content hosted in the external source repository.

## Assumptions

- Users are platform engineers with cluster-admin access to a prepared bare-metal OpenShift cluster with memory-encryption-capable processors (e.g., Intel TDX) and the confidential-containers pattern (runtime classes, initdata propagation, Trustee key broker) already installed.
- Host-level inspection (node debug shells, privileged diagnostic containers, kernel core dumps) is an intentional and documented part of the demonstration, performed only by the authorized user on the documented target node.
- The cluster's default ingress wildcard certificate terminates TLS at the router edge; the walkthrough may document fetching the cluster CA or explicit trust-flag usage for the TLS scenario.
- The memory-dump helper and attestation client tooling images will be built in the designated external image repository (`butler54/containers`) and pinned here; this feature documents those dependencies but does not perform the image builds.
- Administrative retirement (archival) of the external source repository is out of scope for this feature; the deliverable is content parity plus the successor notice so the retirement can proceed independently.
- Consistent with this repository's testing-only stance, chart lifecycle is delete-and-recreate; no upgrade flow is required.
- Validation is the repository's standard static linting plus manual step-through; no live-cluster runs or automated verification are performed by this feature.
