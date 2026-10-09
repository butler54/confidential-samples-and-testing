### Additional finding: OSC 1.13 sealed secrets need an initdata/trust prerequisite

While designing block-storage examples using this pattern's `debug-initdata`, source review found a separate obstacle beyond replacing the plaintext placeholder in `kbs-access-sealed`.

This is a source-based compatibility finding, **not a claim of a reproduced live-cluster failure**. Reviewed pattern revision: `aa04a093268be8ac92174313848a4c44298fbc41`; OSC 1.13 source branches and guest-components v0.20.0.

### Source-level reproduction

1. Inspect `ansible/initdata-debug.toml.tpl`: its CDH configuration does not configure a sealed-token verification-key provisioning path or an explicit signature-verification override.
2. Replace the sample's plaintext Secret with a genuine CoCo vault token for a single KBS encryption-key resource. Transport the `sealed.<header>.<payload>.<signature>` token through a Secret-backed environment variable; Kata's agent sends it to CDH for unsealing.
3. Inspect CDH's token verification: it requires the public signing JWK from KBS or a guest-local `/run/confidential-containers/cdh/sealed-secret/<kid>` file. There is no documented pattern path to provision that guest-local file through the current debug initdata.
4. Inspect the initdata loader: adding an arbitrary public-key field does not establish that the file is written at the required guest location. A plain `kbs:///...` string is also not a sealed token.

With exactly one KBS encryption-key resource and no additional KBS signing-key resource, stock debug initdata therefore does not document/provide the prerequisite for signature-verified vault unsealing.

### Expected behavior / requested fix

Please update the pattern's initdata generation and sealed example documentation together so a genuine sealed vault token can be unsealed using a documented, supported trust setup. In particular:

- Provide a supported way to provision the public verification key into the guest when the example is intended to need only one KBS encryption-key resource, or explicitly document any additional resource requirement.
- Do not silently disable sealed-token signature verification. If a debug-only `skip_sealed_secret_verification = true` option is offered, make it explicit and clearly distinguish skipping token-integrity verification from bypassing attestation or KBS authorization. Restrictive/default non-debug policies should not inherit that relaxation.
- Replace plaintext/bare-pointer demonstration data with a real externally generated CoCo sealed token; do not commit signing private keys or encryption passphrases.
- Document regeneration/propagation of `debug-initdata`, changed initdata measurements/reference values, and pod recreation where required by admission and attestation policy.

### Acceptance criteria

- A Secret-backed `sealed.` environment value is actually unsealed by Kata/CDH inside a confidential guest, and the released value is the configured KBS resource.
- The documented one-encryption-resource path works with corrected initdata and any explicitly stated trust prerequisites; unsupported prerequisites fail closed rather than falling back to plaintext.
- Signed-token verification behavior is tested, including invalid/tampered tokens when verification is enabled.
- Denied attestation or KBS policy never releases the encryption key, including in any explicitly enabled debug-only signature-verification relaxation.
- No plaintext keys, private JWKs, or decrypted secret values are emitted in logs or served by the example.

### References

- [Pattern debug initdata](https://github.com/validatedpatterns/coco-pattern/blob/aa04a093268be8ac92174313848a4c44298fbc41/ansible/initdata-debug.toml.tpl)
- [OSC Kata environment unsealing](https://github.com/openshift/kata-containers/blob/osc-release-v1.13/src/agent/src/confidential_data_hub/mod.rs)
- [Red Hat CDH sealed-token verification](https://github.com/openshift/confidential-containers-guest-components/blob/osc-release-v1.13/confidential-data-hub/hub/src/secret/mod.rs)
- [CDH v0.20.0 configuration](https://github.com/confidential-containers/guest-components/blob/v0.20.0/confidential-data-hub/hub/src/config.rs)
- [OSC initdata loading](https://github.com/openshift/kata-containers/blob/osc-release-v1.13/src/agent/src/initdata.rs)

The downstream storage-example design will proceed assuming corrected upstream debug initdata is supplied as an external prerequisite. This does not assert that the current pattern already fixes the issue or approve an implicit signature bypass.
