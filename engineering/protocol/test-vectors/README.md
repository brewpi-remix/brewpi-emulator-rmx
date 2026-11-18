# Protocol fixtures

These independently authored MIT JSON files specify the controller personality, defaults, diagnostics, and byte/semantic expectations. They contain interoperability values and synthetic examples, not copied firmware tests or generated source tables.

- [defaults-v1.json](defaults-v1.json): native identity, settings/constants, synthetic hardware inventory, and initial presets.
- [diagnostics-v1.json](diagnostics-v1.json): 43 type/ID signatures and argument expectations.
- [protocol-v1.json](protocol-v1.json): 48 deterministic source-defined cases and nine nonpassing reference-characterization placeholders; the [qualification reconciliation](../firmware-findings.md#characterization-reconciliation) identifies their covered subclaims and genuinely unqualified remainders.

Fixture metadata describes specification artifacts, not execution receipts. Run the native suites to obtain current execution results. Unresolved cases have no invented exact output and do not count as passing. Their count is not a count of wholly untested behaviors: separately named regressions cover bounded observed or source-defined outcomes without promoting the whole characterization placeholder. Byte expectations preserve `CRLF` framing, CP437 LCD values, malformed/partial input, diagnostic placement, and firmware quirks.

The original [fixture matcher](../../../tests/fixtures.py) validates ordered replies/diagnostics and native engine state through a test-only driver. Public PTY tests exercise the shipped process separately. See the [wire contract](../behavioral-contract.md) and [development guide](../../../docs/development.md).
