# Feature Specification: Confidential Storage Helm Examples

**Feature Branch**: `002-refine-storage-startup`

**Created**: 2026-10-08

**Status**: Draft

**Input**: User description: "Use ./staging/sample-containers as the baseline for three independently deployable root-level Helm examples: unencrypted block storage, encrypted block storage, and directly mounted NFS. Target Red Hat's confidential-container build and documented storage utilities; interoperate with coco-pattern metadata; allow initdata and image overrides; use default storage unless overridden; avoid resource collisions; offer sealed-secret, curl/KBS, and explicitly insecure standard-secret encryption-key delivery using one preconfigured Trustee resource; describe every example in the root README.md."

**Update**: Use debug initdata in coco-pattern deployments. On each main-container start, wait for the intended storage to become accessible in that container, create a prose file if absent, verify it if present, and explicitly log creation, existing expected content, or failure.

## Clarifications

### Session 2026-10-08

- Q: Should uninstalling either block-storage example preserve its volume and data by default? → A: Use Deployments for all examples. Deleting a pod must result in a replacement pod that can access existing data. Helm uninstall must delete all release-owned artifacts and block volumes.
- Q: How should planning proceed when stock debug initdata lacks the sealed-token verification prerequisite? → A: Track the fix upstream in validatedpatterns/coco-pattern issue #153 and build assuming corrected debug initdata is provided. Keep the single KBS resource requirement; charts must not silently disable signature verification or claim the current pattern already works.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Use Unencrypted Block Storage (Priority: P1)

A platform engineer deploys a standalone example that attaches a raw block volume, formats it when blank, and makes its filesystem available to the application without encryption. This provides a simple baseline for verifying confidential-container storage access.

**Why this priority**: Establishes the smallest useful storage demonstration and the shared deployment conventions before introducing key delivery.

**Independent Test**: Deploy only this example, write and read a test file through the application-visible storage path, delete its pod, and read the same file through the automatically created replacement pod. Uninstall the release and verify that its artifacts and block volume are deleted.

**Acceptance Scenarios**:

1. **Given** a prepared confidential-container cluster with a default storage class supporting raw block volumes, **When** the engineer deploys the example without specifying a storage class, **Then** a blank block volume is formatted without encryption and the application can write and read files on it.
2. **Given** an explicitly configured compatible storage class, **When** the engineer deploys the example, **Then** its storage request uses that class rather than the cluster default.
3. **Given** a previously initialized volume containing a test file, **When** the pod is deleted, **Then** its Deployment automatically creates a replacement pod that accesses the same volume, the file remains readable, and the volume is not reformatted.
4. **Given** a deployed release with block storage, **When** the engineer uninstalls it through Helm, **Then** all release-owned artifacts and its backing block volume are deleted without a separate storage-deletion step.

---

### User Story 2 - Use Encrypted Block Storage (Priority: P1)

A platform engineer deploys an example that initializes encryption on a blank raw block volume, obtains an encryption key through a selected delivery mode, unlocks the volume inside the confidential workload, and exposes the resulting filesystem to the application.

**Why this priority**: Demonstrates the principal confidential-storage use case and makes the difference between attested and insecure key delivery observable.

**Independent Test**: Deploy only this example, verify encryption is active, write and read a test file, delete its pod, and verify that the automatically created replacement pod unlocks the same volume with the original key and reads the file. Repeat independently for each key-delivery mode, then verify complete release-owned artifact and block-volume deletion on Helm uninstall.

**Acceptance Scenarios**:

1. **Given** Trustee exposes one configured encryption-key resource and authorizes this workload, **When** the engineer deploys the default curl-based retrieval mode, **Then** the key is retrieved through the supported attested access path, the blank volume is encrypted and unlocked, and the application can use its filesystem.
2. **Given** a valid CoCo sealed-secret reference to that same Trustee resource, **When** the engineer selects sealed-secret mode, **Then** attestation releases the key inside the confidential workload and the encrypted-storage demonstration succeeds without requiring a second Trustee resource.
3. **Given** an operator-supplied standard Kubernetes Secret containing the key, **When** the engineer explicitly enables insecure standard-secret mode, **Then** the same encrypted-storage flow succeeds and the documentation clearly states that key delivery is not attestation-protected.
4. **Given** an encrypted volume containing a test file and the original key, **When** the pod is deleted, **Then** its Deployment automatically creates a replacement pod that unlocks the same volume and retains the file without recreating encryption metadata or the filesystem.
5. **Given** missing, empty, denied, or incorrect key material, **When** storage initialization or unlocking is attempted, **Then** the application is not reported ready, no usable unencrypted fallback is provided, existing data is not reformatted, and diagnostics identify the failed stage without revealing the key.
6. **Given** a deployed encrypted-storage release, **When** the engineer uninstalls it through Helm, **Then** all release-owned artifacts and its backing block volume are deleted; pre-existing Trustee resources and operator-supplied Secrets remain untouched.

---

### User Story 3 - Mount an Existing NFS Export Directly (Priority: P2)

A platform engineer points an independent example at an existing NFS server and export. The workload mounts the export from inside its container environment, demonstrating network storage without a persistent-volume interface.

**Why this priority**: Adds a distinct storage path while keeping server provisioning outside the sample's scope.

**Independent Test**: Deploy only this example against a writable test export, write and read a file from the application-visible mount, and confirm the example creates no persistent volume or persistent volume claim.

**Acceptance Scenarios**:

1. **Given** a reachable NFS server and writable export, **When** the engineer supplies the server, export path, and container mount location, **Then** the application can write and read a test file through a mount performed inside the workload, without using a persistent volume or persistent volume claim.
2. **Given** specified mount options and an export permitting the requested access, **When** the engineer deploys the example, **Then** the mount honors those options and exposes storage at the configured location.
3. **Given** an unavailable server, invalid export, or rejected access, **When** mounting is attempted, **Then** the workload does not report storage readiness and supplies non-secret diagnostics identifying the mount failure.
4. **Given** an existing export containing a test file, **When** the pod is deleted, **Then** its Deployment automatically creates a replacement pod that remounts the same export and can read the file.
5. **Given** a deployed NFS release, **When** the engineer uninstalls it through Helm, **Then** all release-owned artifacts are deleted while the externally managed NFS server, export, and data remain untouched.

---

### User Story 4 - Configure and Run Examples Together (Priority: P2)

A platform engineer discovers the examples through the repository README, configures the common deployment options, and runs all three in one namespace on a coco-pattern-managed or equivalently prepared cluster, including a disconnected environment.

**Why this priority**: Makes the examples reusable demonstrations rather than isolated manifests tied to one environment.

**Independent Test**: Follow the documentation to deploy all three examples together, deploy a second release of one example, apply configuration overrides, and remove one release without affecting the others.

**Acceptance Scenarios**:

1. **Given** all three examples and distinct release identities, **When** they are deployed into one namespace, **Then** every example-owned resource has a distinct identity and each workload uses only its intended resources.
2. **Given** a running release of an example, **When** a second release of that example is deployed or one release is removed, **Then** names, resource ownership, and workload selection remain isolated and the other release continues working.
3. **Given** coco-pattern initdata injection and its same-namespace `debug-initdata` ConfigMap, **When** an example is deployed without an initdata override, **Then** its pod metadata selects `debug-initdata` without requiring edits to rendered deployment content; a configured alternate ConfigMap remains selectable.
4. **Given** operator-provided explicit initdata, **When** an example is deployed with that override, **Then** the supplied initdata is used rather than overwritten by automatic injection.
5. **Given** mirrored images for every container role and the documented disconnected prerequisites, **When** the engineer overrides all image references, **Then** none of the examples requires public-registry access or installing packages from public repositories during startup.
6. **Given** the root README and an individual example's documentation, **When** the engineer selects an example, **Then** they can identify its purpose, prerequisites, configuration, deployment steps, expected result, verification method, and cleanup/data-retention behavior without consulting a sibling example.

---

### User Story 5 - Observe Storage Persistence at Startup (Priority: P1)

A platform engineer deploys any example and uses the main container's logs to see whether it created a demonstration text file or found the same prose retained from an earlier pod. File operations happen only after the intended storage is available to the main container, so the demonstration cannot accidentally validate the container's temporary filesystem instead.

**Why this priority**: Provides an automatic, explicit persistence demonstration and prevents misleading success before a helper's mount is available to the application.

**Independent Test**: For each example, deploy against writable storage without its demonstration file and inspect the creation log; delete the pod and inspect the replacement pod's existing-file log. Repeat with incorrect file content, denied write access, and delayed or unavailable mounts to verify distinct failures.

**Acceptance Scenarios**:

1. **Given** the intended storage is accessible from the main container and its demonstration file is absent, **When** the main entry point runs, **Then** it creates a text file containing the documented expected prose, verifies the saved content, and explicitly logs the path, that the file did not previously exist, and that creation and verification succeeded.
2. **Given** the file already exists on the intended storage with the expected prose, **When** a new or replacement pod starts, **Then** its main entry point verifies the content, logs that the file already existed with the expected prose and was not recreated, and preserves the file.
3. **Given** the existing file contains different prose, is unreadable, or cannot be created or verified, **When** the main entry point runs, **Then** it reports the specific outcome and that neither successful creation nor an existing expected-prose file was confirmed, does not overwrite existing content, and does not start the main application or report readiness.
4. **Given** a storage helper has prepared its mount but it is not yet accessible from the main container, **When** the main entry point begins, **Then** it waits for confirmed access to the intended storage before attempting file operations or starting the main application; directory existence or a helper-only readiness signal is insufficient.
5. **Given** the intended mount never becomes accessible, **When** the configured storage-startup deadline expires, **Then** the main entry point logs the storage path and timeout, reports that the prose-file check could not run, and fails without creating a file on the container's temporary filesystem.
6. **Given** two releases mount the same external NFS export, **When** both start, **Then** their default demonstration file paths are distinct and neither treats the other release's file as evidence of its own persistence.

### Edge Cases

- No default storage class, an unsupported raw-block class, or an unbound storage request: storage remains unavailable and the documented diagnosis identifies the prerequisite rather than silently switching storage behavior.
- Existing recognizable but incompatible filesystem or encryption metadata: initialization refuses destructive conversion rather than treating it as a blank volume.
- Wrong or changed encryption key: unlocking fails without overwriting the existing volume; key rotation and recovery are outside this feature.
- Multiple selected key-delivery flags, no valid selection, or missing mode-specific configuration: configuration is rejected with an actionable error before deployment.
- Missing initdata ConfigMap, invalid explicit initdata, or denied attestation: the workload must not present protected storage as ready; documentation distinguishes configuration failure from key denial.
- Conflicting automatic-injection and explicit-initdata settings: the explicit override takes precedence; reserved ownership and workload-selector metadata cannot be overridden into collisions.
- Two releases use long or similar names: resource naming remains valid and distinct, including after any required name shortening.
- NFS export permissions, read-only options, or root squashing prohibit writes: documentation explains the expected access failure and does not advise disabling server protections globally.
- A mounting or storage helper stops after initial success: the application no longer reports storage readiness until the storage is usable again.
- Cluster policy disallows required workload privileges: deployment failure and narrowly scoped permission prerequisites are explained without automatically granting privileges to unrelated workloads.
- Restrictive initdata disallows interactive execution: verification remains possible without weakening the default policy or exposing encryption keys through application output.
- The selected storage class retains backing volumes on claim deletion: it does not satisfy the uninstall-cleanup requirement. Documentation must identify a compatible class with automatic backing-volume deletion; examples must not change a shared storage class's policy globally.
- Backing-volume deletion is delayed or fails in the storage provider: cleanup verification waits for actual deletion and reports a failure rather than treating claim removal alone as complete cleanup.
- Pod deletion occurs while storage is attached: the Deployment replaces the pod and permits normal detach/reattach recovery without allocating a new data volume or reinitializing existing data.
- The helper reports readiness before its mount is accessible from the main container: file operations and the main application remain gated on main-container access to the intended storage, not a marker on an unrelated filesystem.
- The demonstration file exists with unexpected or partial content: startup logs a content mismatch, preserves the existing file, and fails rather than replacing it or reporting persistence success.
- A read-only export contains the expected demonstration file: verification can succeed without rewriting it; if the file is absent, startup reports creation failure instead of claiming success.
- The requested debug initdata ConfigMap is absent: startup must not silently fall back to an unrelated policy; documentation identifies the missing same-namespace prerequisite and supported explicit overrides.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST provide exactly three new independently deployable Helm examples, each wholly contained in a distinct root-level example directory: unencrypted block storage, encrypted block storage, and direct NFS mounting. Existing staged samples MUST serve as the baseline, not as runtime dependencies.
- **FR-002**: Each example MUST include its own chart, comprehensive configuration defaults, and documentation sufficient for independent deployment and verification, with no dependency on a sibling example's files or setup.
- **FR-003**: All examples MUST target Red Hat OpenShift confidential containers on bare metal, identify supported platform prerequisites and versions, and use the appropriate confidential runtime by default while allowing the runtime selection to be configured.
- **FR-004**: Each example MUST interoperate with coco-pattern workload metadata, including `coco.io/initdata-configmap`, `coco.io/skip-initdata`, and `io.katacontainers.config.hypervisor.cc_init_data`. Any example-owned initdata ConfigMap MUST follow the pattern's `coco.io/type: initdata` and `INITDATA` content contract.
- **FR-005**: In coco-pattern deployments, each example MUST select the same-namespace `debug-initdata` ConfigMap by default through `coco.io/initdata-configmap`. Each example MUST still allow selection of another existing same-namespace initdata ConfigMap, explicit encoded initdata, and an explicitly selected cluster-managed default-initdata mode. Explicit initdata MUST take precedence over automatic injection. Debug initdata is an intentional demonstration default, MUST be documented as a relaxed testing policy rather than production hardening, and MUST NOT silently bypass attestation or key-release authorization.
- **FR-006**: Examples MUST expose consistent configuration behavior for namespace/release identity, workload labels and annotations, runtime, initdata, image references, and application storage location. Optional metadata customization MUST preserve resource ownership and release-isolated workload selection.
- **FR-007**: Block-storage examples MUST request raw block storage using the cluster's default storage class when no class is specified, allow an explicit class and storage capacity, and document the raw-block provisioning prerequisite. The NFS example MUST NOT create or use persistent volumes or persistent volume claims.
- **FR-008**: All example-owned resources, references, and workload selectors MUST be unique per example and release in a shared namespace. Independently named releases of the same example MUST coexist, and removal of one release MUST NOT alter another release's resources. Shared pre-existing infrastructure MUST be referenced without assuming ownership.
- **FR-009**: The unencrypted example MUST format only a blank volume, mount the resulting supported filesystem for application use, and preserve existing compatible filesystems and data across workload restarts. It MUST NOT require an encryption-key resource.
- **FR-010**: The encrypted example MUST initialize encryption only on a blank volume, obtain the selected key, unlock and mount the encrypted filesystem inside the confidential workload, and make it available to the application only after successful preparation. Subsequent starts MUST reopen existing encryption and preserve data.
- **FR-011**: Encryption-key delivery MUST have three mutually exclusive feature-flag modes: CoCo attestation-unsealed secrets, curl-based retrieval of a Trustee KBS resource through the supported attested access path, and an explicitly insecure standard Kubernetes Secret. Curl-based retrieval MUST be the default; insecure mode MUST require explicit selection.
- **FR-012**: Both attested key-delivery modes MUST use the same single preconfigured Trustee encryption-key resource, with its identifier configurable. The example MUST NOT provision Trustee resources or require additional key, status, or demonstration-secret resources. Standard-secret mode MUST accept operator-supplied equivalent key material without requiring a KBS fetch.
- **FR-013**: Protected key-delivery failures MUST stop storage preparation without fallback to an insecure mode. Empty or invalid keys and unsuccessful retrieval responses MUST NOT be accepted as usable key material. Encryption keys MUST NOT appear in repository defaults, diagnostics, logs, rendered example plaintext values, or application-served content; insecure testing MUST use an operator-supplied Secret.
- **FR-014**: The NFS example MUST mount an operator-specified existing server and export inside the container workload, expose configurable mount location and options, and document connectivity and export-permission prerequisites. Provisioning an NFS server is outside scope.
- **FR-015**: Every application, initialization, storage-helper, retrieval, and supporting container MUST have an explicit maintained default image reference and allow full image-reference overrides for disconnected use. Red Hat-supported images MUST be preferred, and non-Red Hat dependencies MUST have a documented justification.
- **FR-016**: The examples MUST use Red Hat-provided storage utilities where applicable to the demonstrated behavior, following the documented OpenShift Sandboxed Containers 1.13 baseline. This repository MUST NOT build container images; any additional image requirements MUST be owned externally in `butler54/containers`.
- **FR-017**: Startup MUST NOT require installation of utilities from public package repositories. Documentation MUST enumerate all consumed images and any disconnected prerequisites beyond image mirroring, including attestation, trust configuration, and storage/network access.
- **FR-018**: Storage preparation, mount-access, or startup-file verification failure MUST prevent main-application startup and application storage readiness, with identifiable failure stages and no exposure of key material. Readiness MUST reflect continued access to the intended storage, not merely application process startup.
- **FR-019**: Example documentation MUST explain required permissions and their scope, provide deployment/configuration/verification instructions, distinguish attested and insecure key delivery, and explain automatic recovery after pod deletion and destructive Helm-uninstall consequences. Helm uninstall MUST delete all release-owned artifacts, claims, and backing block volumes without a separate deletion step; block-storage classes MUST support automatic backing-volume deletion on claim removal. Pre-existing shared infrastructure, operator-supplied resources, and externally managed NFS data MUST remain untouched. Permissions MUST be limited to the workloads that need them rather than broadly changing namespace or cluster privileges.
- **FR-020**: The root `README.md` MUST provide a short description and link for each of the three examples, distinguish their storage and security behavior, and direct users to prerequisites and example-specific documentation.
- **FR-021**: Delivery MUST include automated checks for chart validity, explicit image/version defaults, the three key-mode selections and invalid combinations, metadata/override behavior, and resource isolation across examples and releases. Each documented storage flow MUST have reproducible acceptance verification, including automatic data-access recovery after pod deletion for all three examples, complete release-owned artifact and backing-block-volume deletion on Helm uninstall, and denied-key behavior for encrypted storage.
- **FR-022**: All three examples MUST use Deployments. Deleting a workload pod MUST automatically produce a replacement pod that regains access to the same existing data, including reacquiring the original encryption key where required, without manual redeployment or destructive initialization.
- **FR-023**: On every main-container start, its entry point MUST first confirm that the intended storage is accessible at the application-visible path in the main container. It MUST wait up to a documented, configurable finite deadline for mount availability or propagation before any demonstration-file operation or main-application startup. An existing directory, fixed sleep, or helper-only readiness signal MUST NOT alone establish main-container storage access. On timeout or mount failure, startup MUST explicitly log the failure and skip file operations without writing to temporary container storage.
- **FR-024**: After successful storage-access verification, the main entry point of every example MUST create its demonstration text file only when absent and verify that the saved content matches the documented expected prose. When the file already exists, it MUST read and compare its content against the same expected prose without overwriting or recreating it. The default file path MUST reside on the demonstrated storage, remain stable across replacement pods, and be distinct per example and release, including on a shared NFS export.
- **FR-025**: Main-container startup logs MUST explicitly distinguish successful creation of a previously absent file, discovery of an existing file with the expected prose without recreation, and failure to confirm either successful condition. Logs MUST identify the demonstration file path, whether creation occurred, and any content-mismatch, read, write, verification, or mount-access failure. Success logs MUST identify the expected non-secret prose; error logs MUST NOT print arbitrary existing file content or encryption keys. Failure to create or verify the file MUST preserve existing content, stop main-application startup, and prevent readiness.
- **FR-026**: Documentation and reproducible acceptance checks MUST cover the default debug-initdata selection and explicit overrides, initial file creation, existing expected prose after pod replacement, content mismatch, file-access failure, delayed mount propagation, and unavailable-mount timeout for all three examples. Verification MUST inspect the main container's logs and the file on the intended storage, not only a helper's logs or readiness markers.
- **FR-027**: The sealed-mode design MUST presume externally corrected coco-pattern debug initdata supplies the supported sealed-token trust prerequisites while retaining one KBS encryption-key resource. Documentation MUST link upstream issue #153, identify the corrected initdata as an external prerequisite, and require fail-closed live verification before claiming that mode works. Charts MUST NOT modify shared initdata or silently disable sealed-token signature verification to compensate for the current upstream gap.

### Key Entities

- **Example**: A self-contained storage demonstration with a unique name, chart, supported environment, defaults, and operator documentation.
- **Release**: An independently owned deployment of one example in a namespace; determines resource identity and workload selection.
- **Storage Target**: Either a raw block volume with capacity, provisioning choice, and initialization state, or an existing NFS export with server, path, mount options, and access permissions.
- **Initdata Configuration**: Workload initialization and policy settings selected through cluster defaults, a same-namespace configuration reference, or an explicit override.
- **Key-Delivery Selection**: Exactly one delivery mode and its required configuration, identifying either the shared Trustee encryption-key resource or an operator-supplied insecure Secret.
- **Image Configuration**: Versioned default and operator-overridden image references for every container role, including disconnected mirrors.
- **Demonstration File**: A release-isolated text file on the intended persistent storage with a stable path and documented, non-secret expected prose; its creation or verified prior existence makes persistence observable in main-container logs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All three examples can be deployed and verified independently on a prepared supported environment, and each completes a write/read test at its documented application-visible storage location.
- **SC-002**: All three examples plus a second release of one example operate concurrently in one namespace with zero resource-identity collisions, cross-selected workloads, or unintended shared example-owned resources. Removing any one release leaves every remaining release's verification test passing.
- **SC-003**: The encrypted-storage demonstration completes the same write/read and retained-volume restart tests in all three key-delivery modes using one Trustee encryption-key resource for the two attested modes.
- **SC-004**: Across missing-resource, denied-attestation, empty-key, and wrong-key tests, zero runs report usable storage readiness, expose key material, silently downgrade protection, or destroy pre-existing data.
- **SC-005**: Each example preserves access to a written test file across at least two consecutive pod deletions and automatic replacements, without manual redeployment or storage reinitialization; the encrypted example remains encrypted throughout. Helm uninstall leaves zero release-owned artifacts or backing block volumes after provider cleanup completes, while pre-existing shared resources and external NFS data remain intact.
- **SC-006**: All three examples pass their storage-use verification with every image redirected to a disconnected mirror and with no public-registry or public-package-repository access required during startup.
- **SC-007**: For every example, verification confirms the selected initialization configuration is used in each of the three supported cases: cluster-managed default, named configuration, and explicit override.
- **SC-008**: A platform engineer can locate all three examples from the root README and complete each documented deployment and verification flow without editing packaged deployment content or consulting a sibling example. Every flow includes an expected outcome, pod-replacement verification, and a warning that Helm uninstall destroys release-owned block storage.
- **SC-009**: In all three examples, one initial start against storage without the demonstration file logs verified creation, and at least two subsequent pod replacements log that the same file existed with the expected prose and was not recreated.
- **SC-010**: Across delayed-mount and unavailable-mount tests for all three examples, zero runs perform demonstration-file operations before the intended storage is accessible to the main container, and zero files are created on temporary container storage as a fallback. Unavailable-storage runs report timeout by the configured deadline without starting the main application.
- **SC-011**: Content-mismatch, unreadable-file, and failed-creation tests produce distinct, explicit failure logs in every example, with zero overwritten existing files, false persistence-success reports, or ready applications. Every successful creation or existing-file check names the path and expected non-secret prose.
- **SC-012**: Default deployments of all three examples in a prepared coco-pattern namespace select debug initdata; alternate named, explicit, and cluster-default selections remain verifiable through configuration overrides.

## Assumptions

- Target users are platform engineers with access to a prepared Red Hat OpenShift bare-metal confidential-container environment. Installing the operators, confidential runtime, Trustee, admission policies, storage driver, or cluster-wide infrastructure is outside scope.
- OpenShift Sandboxed Containers 1.13 and its Red Hat storage-helper documentation are the baseline. Exact compatible OpenShift and Trustee versions and coco-pattern revision will be recorded during planning; compatibility with every historical pattern version is not implied.
- “One in each directory” means one new root-level directory per required example, not converting every existing root-level or staged directory into a chart. Suggested distinct identities are `block-storage-plain`, `block-storage-encrypted`, and `nfs-direct`.
- “Sealed secrets” means CoCo secrets unsealed within the confidential guest after attestation, not Bitnami Sealed Secrets decrypted by a cluster controller. The latter would not demonstrate the requested attested key release. Placeholder plaintext Secrets or bare resource pointers MUST NOT be presented as functioning sealed secrets.
- “Pulling a resource from KBS via curl” includes the supported local Confidential Data Hub path used by the baseline samples, where Trustee communication and attestation are performed for the guest; it does not imply an unauthenticated public key endpoint.
- Trustee contains exactly one relevant encryption-key resource. Its reference defaults may follow the staged sample identifier `default/kbsres1/key3`, but operators must supply valid policy, key material, and trust configuration. Examples do not generate, rotate, or recover keys.
- The operator supplies an existing NFS server/export. NFS authentication requiring additional attested credentials, NFS transport encryption, server lifecycle management, and automated export provisioning are not included.
- Examples use a single workload instance per release to keep raw-block ownership simple. Scaling shared writers, performance benchmarking, high availability, and backup/recovery automation are outside scope.
- Pod replacement and workload restarts reuse the same block volume and, for encrypted storage, the original key. Helm uninstall deliberately destroys release-owned block storage; no uninstall-retention mode is required. Externally managed NFS storage and pre-existing shared resources are not release-owned and must not be deleted.
- A compatible default storage class is present for the default block-storage path and uses a deletion reclaim policy with a provider that deletes backing volumes on claim removal. Explicit storage-class overrides must satisfy the same cleanup behavior. Lack of that prerequisite is a documented deployment failure, not a requirement to create or globally modify a storage class.
- Existing sample concepts may be reused, but experimental shortcuts such as hard-coded helper process IDs, undocumented policy relaxation, plaintext demonstration passwords, and unversioned images are not required behaviors.
- coco-pattern provides `debug-initdata` in the workload namespace. This feature deliberately uses that relaxed policy for demonstration and troubleshooting by default, while preserving overrides for restrictive policies. These examples are not production policy-hardening demonstrations; verification must respect whichever policy the operator selects.
- For sealed mode, operators provide corrected upstream debug initdata and any supported guest-local public verification-key provisioning it requires; the current reviewed pattern revision does not yet satisfy that prerequisite. Work proceeds under this external dependency rather than adding another KBS resource or silently skipping signature verification. Findings are recorded at <https://github.com/validatedpatterns/coco-pattern/issues/153#issuecomment-6052160162>.
- The expected prose is fixed, public demonstration text documented consistently in each example: “This file demonstrates persistent storage for this confidential container example.” The file is a demonstration artifact, not an encryption key or attestation resource, and does not require an additional Trustee resource.
- “Neither condition” means that neither verified creation of an absent file nor verification of an existing expected-prose file succeeded; content mismatch, read/write failure, or unavailable storage must be reported as failure rather than treated as another success state.
- “Before starting” means before demonstration-file operations and the main application begin. A startup entry point may run only to wait for and verify main-container storage access until that gate succeeds.

### Source Context

- Local baseline: `staging/sample-containers/baseline-custom/`, `staging/sample-containers/storage-encrypted/`, `staging/sample-containers/storage-encrypted-kbs/`, and `staging/sample-containers/kbs-access-curl/`.
- Red Hat storage and initdata behavior: <https://docs.redhat.com/en/documentation/openshift_sandboxed_containers/1.13/html/deploying_confidential_containers_on_bare-metal_servers/configure-cc-overview_metal-cc#encrypt-the-block-volumes_metal-cc>.
- Pattern metadata and injection behavior: <https://github.com/validatedpatterns/coco-pattern>, including the workload initdata injection and namespace propagation policies reviewed on 2026-10-08. The pattern's sealed-access example contains a documented plaintext placeholder and is not evidence of working attestation-unsealed delivery.
