# Contract: Values, Naming, and Render Rules

Consumer-facing surface of both charts. This contract is what the walkthroughs may assume; it is a documented review contract (no automated enforcement — render-assertion checkers were removed repo-wide per PR review). Tooling images used only in walkthrough node-debug steps (coredump helper, network-tools) are documented inputs, not chart values.

## memory-security values contract

| Path | Type | Default | Constraint (schema-enforced unless noted) |
|---|---|---|---|
| `runtimeClassNames.coco` | string | `kata-cc` | non-empty |
| `runtimeClassNames.kata` | string | `kata` | non-empty |
| `initdata.configMapName` | string | `debug-initdata` | empty ⇒ no kyverno annotation |
| `initdata.encoded` | string | `""` | non-empty ⇒ wins over `configMapName` (hypervisor annotation) |
| `images.demo` | string | `registry.access.redhat.com/ubi9/ubi:9.6` | non-empty, tag-pinned (no `:latest`) |
| `images.magicServer` | string | `registry.access.redhat.com/ubi9/httpd-24:<tag>` | non-empty, tag-pinned |
| `imagePullPolicy` | string | `IfNotPresent` | enum |
| `imagePullSecrets` | list | `[]` | names only (existing Secrets) |
| `magic.string` | string | `MyMagicKeyIsABanana` | non-empty |
| `route.host` | string | `""` | **required** non-empty FQDN at render (install-time value) |
| `resources.*` | object | sibling-style defaults | CPU/memory quantities, VM tiers include guest RAM |

There is intentionally **no** `transport.plaintext.enabled`-style toggle: the plaintext HTTP endpoint and pod pair are inherent to the chart design (see FR-003 and research.md R2).

Install mode (single): `helm install <rel> ./memory-security --set route.host=<host-on-apps-domain>` → endpoint + 3 tier pods + the fetch pair (`<rel>-fetch-https`, `<rel>-fetch-http`); the route serves 443 (TLS) and 80 (plaintext, documented exception). HTTP usage is confined to `<rel>-fetch-http`; secure posture returns on `helm uninstall`.

## Naming contract

All resources `<release>-<suffix>`: endpoint `magic` (Deployment/Service/Route), tiers `standard|kata|coco`, pair `fetch-https|fetch-http`, ConfigMap `magic-string`, scripts ConfigMap n/a (scripts live on the client side, run by the user locally). Releases coexist when each has a distinct `route.host` (walkthrough requires this and shows construction: `<rel>-<ns>.<appsDomain>`).

## Render rules (staticly asserted)

1. `magic.string` content appears **only** in the `magic-string` ConfigMap; never in pod command arguments.
2. Exactly one rendered container command contains an `http://` scheme (the designated fetch pod), and it appears in exactly one pod.
3. Route has `tls.termination: edge` **and** `insecureEdgeTerminationPolicy: Allow` in every render — plaintext HTTP is inherent to the chart; the route and fetch-http pod templates carry the demonstration-intent warning comment, and `README.md`/`NOTES.txt` contain the demonstration-only notice.
4. Initdata annotation precedence: `encoded` (hypervisor `init_data`, quoted) > `configMapName` (kyverno annotation) > none. Tiers/pair follow the per-pod rules in data-model.md; the kata and standard tiers carry **no** initdata annotation.
5. Every rendered image is non-empty and tag-pinned; default render contains only `registry.access.redhat.com` references.
6. Pods reference no SCC bindings, Secrets, or cluster-scoped resources; restricted securityContext defaults; no `securityContext.privileged` anywhere in rendered output.
7. `route.host` absence ⇒ helm lint/render rejection (schema), so CI covers failure mode.

## kbs-client values contract

| Path | Type | Default | Constraint |
|---|---|---|---|
| `images.client` | string | pinned `butler54/containers` build reference | non-empty, tag-pinned |
| `runtimeClassName` | string | `kata-cc` | non-empty |
| `initdata.*` | same as memory-security | same | same precedence rules |
| `kbs.address` | string | `""` | optional; README default-construction one-liner for cluster Trustee route |
| `resources` | object | modest single-pod defaults | quantities |
| `imagePullSecrets`, `imagePullPolicy` | as memory-security | same |

Render rules: single Deployment `<release>-client`, `kata-cc` + initdata annotation per precedence rules, no Services/Routes/Secrets, `sleep infinity` entrypoint, pinned image.
