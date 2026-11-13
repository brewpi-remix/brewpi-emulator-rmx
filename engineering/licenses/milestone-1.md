# Milestone 1 provenance record

Date: November 13, 2026. Owner instruction: complete the behavioral contract/defaults/diagnostics/original fixtures, preserve independent MIT licensing, follow the Arduino firmware even where buggy, and stop before implementation. Original project documentation/data are copyright 2026 Lee Bussy and licensed under [MIT](../../LICENSE.md).

## Material and origin

The [protocol contract](../protocol/behavioral-contract.md), [defaults prose](../protocol/defaults.md), [diagnostic metadata](../protocol/diagnostics.md), [findings](../protocol/firmware-findings.md), [fixture-format guide](../protocol/test-vectors/README.md), and [three JSON datasets](../protocol/test-vectors/defaults-v1.json) are independently authored specification material. Companion JSON files are linked from the fixture guide. No firmware/Fuscus source routine, declaration, macro, test helper, diagnostic text table, image, captured stream, or binary is incorporated or mechanically translated.

Source inspection supplied required interoperability facts: command bytes, field names/types, numeric IDs/signatures, fixed-point values, annotations, and action/reaction ordering. The small required annotation phrases and LCD wire layout are recorded as protocol facts, not a copied expressive diagnostic table. The source citations identify exact reviewed revisions; the referenced code retains its own license. Existing source exposure is disclosed, so this is not a formally separated clean-room assertion.

Original fixture identities and scenario inputs were selected locally. One-off arithmetic calculated synthetic ROM CRC bytes, thermal capacities, and fixed-point-derived default data; standard-library serialization wrote the authored literal expectations. No reference implementation, emulator implementation, copied parser, or model was executed to generate expected replies. Semantic fixtures are declarations, not shipped controller code or a new runtime API.

## Dependency disposition

The selected initial emulator foundation uses original C++17 code plus the standard library and POSIX/Linux facilities, without an incorporated third-party JSON or controller library. This is a design decision only; no code/build/dependency was added. External build tools/system libraries and future Python/pyserial/host/panel test clients retain their own terms and must be inventoried at actual selection/execution/bundling. No source or binary from them is included here. The [third-party incorporation inventory](../../THIRD_PARTY_NOTICES.md) therefore remains empty.

## Review performed and limits

The local source/profile/default/converter/logger/device/persistence paths were inspected and their deterministic findings recorded. JSON structure, IDs/references, hex encodings, diagnostic signatures, fixture/default cross-references, CRC bytes, source links, Markdown links, and whitespace were checked locally. No executable fixture runner, emulator test, native build, host/panel process, Arduino operation, Pi installation, or reference change was performed. The exact checks and limitations are summarized in the [milestone review](../development/milestone-1-review.md).

The follow-up review added independently described saved-record validation, parser stale-value behavior, narrowed integral telemetry, explicit restart barriers, and state-construction requirements. Added vectors remain original specification data; no reference code or generated upstream table was incorporated.

The nine characterization cases have no fabricated exact reply and cannot count as passing. Future implementation/release review must inspect actual source/dependency/build/package contents under the [licensing review gate](README.md#review-gate). This documentation record neither proves future code provenance nor authorizes implementation, new commits/pushes, releases, or deployment.
