<!--
Sync Impact Report
Version change: 1.1.0 -> 2.0.0
Modified principles:
  II. Helm-First Delivery -> II. Helm-First Delivery (scripts gated on explicit approval)
  IV. External Image Builds -> IV. No Container Definitions (repo must not define containers;
      external-image build mandate removed)
Added sections: none
Removed sections: none
Follow-up TODOs: none
-->
# Confidential Samples and Testing Constitution

## Core Principles

### I. Self-Contained Examples
Every example MUST reside entirely in its own directory and include the manifests, Helm chart,
values, scripts, documentation, and configuration required to understand and deploy it. Examples
MUST NOT depend on files or implicit setup from a sibling example. This permits independent use,
review, and removal of workloads.

### II. Helm-First Delivery
Examples MUST use Helm when the workload can be expressed as a chart. Charts MUST expose
environment-specific and operational configuration through comprehensive `values.yaml` files.
When Helm is not suitable, examples MAY use raw Kubernetes manifests with a documented
rationale. Kustomize MUST NOT be used. Executable scripts of any kind — Python, shell, or any
other language — MUST NOT be created unless explicitly approved in advance for the change in
which they appear ("explicit approval" means a recorded decision in the feature specification,
implementation plan, or maintainer review, not merely the absence of objection). Approved
scripts MUST use the simplest practical language, MUST be lint-validated in CI where a linter
exists, and MUST carry a documented rationale for why the behavior cannot live in a Helm chart
or manifests.

### III. Downstream-First Dependencies
Examples MUST prefer Red Hat-supported container images, operators, charts, and OpenShift
resources. Any non-Red Hat dependency MUST be explicitly justified in the example
documentation, including why an equivalent downstream resource cannot satisfy the requirement.
This keeps workloads aligned with supported OpenShift platforms.

### IV. No Container Definitions
This repository MUST NOT define containers: no Dockerfiles, Containerfiles, image build
configuration, or build pipelines for images belong in this repository, and the repository MUST
NOT prescribe where any required external image is defined or built. When a workload needs an
image that Red Hat does not ship downstream, the example MUST reference an already-published
image by immutable reference where practical and document its ownership and approval in the
example README. The repository takes no supply-chain ownership of external images.

### V. CI/CD and Version Discipline
Every change MUST pass repository linting and applicable validation in CI before merge. Examples,
charts, and supporting artifacts MUST use explicit, maintained versions; changes to versions MUST
be reviewed and recorded in the relevant artifact metadata. CI configuration MUST detect linting
or versioning regressions rather than relying on manual checks.

### VI. Simplicity and Explainability
Examples MUST use the smallest design that demonstrates the intended confidential container or
confidential virtual machine workload. Added components, permissions, abstractions, and
configuration MUST have a documented operational purpose. Documentation MUST explain deployment,
configuration, and verification steps so a platform engineer can reproduce the example.

## Delivery Constraints

This repository is an ensemble of workload examples and debugging tooling for confidential
container and confidential virtual machine workloads on OpenShift. Each workload MUST identify
its target OpenShift prerequisites, required confidential-computing capabilities, and expected
verification outcome. Debugging tooling MUST state its supported target and expected diagnostic
result. Deployment content MUST remain within the workload directory except for shared,
repository-level CI/CD configuration and documentation.

## Development Workflow

Contributors MUST validate Helm charts with `helm lint` when charts are present and run all
repository-provided linting and validation commands relevant to changed files. Pull requests MUST
identify the affected example, note any external image the change depends on (with its owning
project), identify every executable script added and record its explicit approval reference, and
explain any exception to Helm-first or downstream-first requirements. Reviews MUST reject
changes that cannot be deployed or understood independently, and MUST reject unapproved scripts.

## Governance

This constitution supersedes conflicting repository practices for example structure, delivery,
dependencies, image builds, CI/CD, and documentation. Amendments MUST be proposed as a change to
this document, describe the affected principles and migration impact, and receive maintainer
approval before adoption. Compliance MUST be reviewed for every pull request and during release
or version-management changes.

Constitution versions use semantic versioning: MAJOR for backward-incompatible principle removal
or redefinition, MINOR for a new principle or materially expanded governance, and PATCH for
clarifications that do not change governance. The ratification date records initial adoption; the
last-amended date changes whenever this document changes.

**Version**: 2.0.0 | **Ratified**: 2026-08-28 | **Last Amended**: 2026-10-13
