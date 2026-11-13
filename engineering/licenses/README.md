# Licensing provenance

## Decision

The owner selected MIT for independent BrewPi Emulator Remix code and documentation on November 13, 2026. See the root [license](../../LICENSE.md), [contract](../../CONTRACT.md), and [third-party inventory](../../THIRD_PARTY_NOTICES.md).

No emulator implementation or third-party dependency has been incorporated. The [plan](../../IMPLEMENTATION_PLAN.md) records inspected BrewPi/Fuscus source revisions and behavioral facts. Existing source exposure is disclosed; the project does not claim a formally separated clean-room process. Scaffolding follows the owner's existing repository-layout/formatting conventions and uses standard MIT license text; these conventions are not incorporated BrewPi/Fuscus implementation code.

## Implementation boundary

Do not copy, vendor, link, translate, mechanically rewrite, or adapt reference code, test helpers, assets, headers, generated tables, or source structure. Write an independent behavior specification and original implementation. Wire names, schemas, enum values, timings, and original interoperability examples may appear in that specification. External host/panel execution does not incorporate their code into the emulator.

MIT labeling does not change the origin of copied material. License compliance alone does not override the owner's no-reuse requirement. Any proposal to incorporate reference material first requires an explicit user scope change and a separate provenance/license review.

Automated translation, AI-assisted paraphrasing, renaming, or restructuring of a reference routine remains prohibited reuse. Standard physical equations and conventional algorithms may be implemented independently. Record exact protocol names and numeric values as interoperability facts rather than copying source declarations or diagnostic text tables. Do not assert that similar behavior or a source citation alone establishes or defeats independent authorship.

## Material categories

| Material | Project requirement |
| --- | --- |
| Original implementation, helpers, tests, fixtures, configuration, and prose | Author independently; submit under MIT, with contributor notices and source-file SPDX identifiers where the format allows them. |
| Behavioral specifications and example messages | Write independently from recorded compatibility facts; cite source revisions; exclude copied implementation or expressive diagnostic tables. |
| Incorporated general-purpose library code | Select a permissive license as required by the plan; record exact material, terms, notices, and distribution obligations separately. Do not label it as original project code. |
| External compiler, test tool, system library, host, or panel | Record its role/version when selected or exercised; execution alone is not incorporation. Reassess separately if binaries, source, or runtime libraries will be bundled. |
| Generated code, tables, or assets | Record the generator/version, input origin, and generated output's applicable terms. Generation is not a way around the no-reuse rule. |
| Protocol captures, screenshots, and externally produced logs | Do not assume MIT ownership. Keep raw material in ignored local evidence by default; use independently authored minimal compatibility vectors. Review origin, private data, and applicable terms before including any external artifact. |

## Future dependency record

For each dependency or redistributed artifact, record its name and purpose, upstream location, exact version/revision or content hash, license identifier/text, copyright notices, modifications, build/runtime/test role, and whether its bytes are redistributed. Retain required notices and keep original project code under MIT. A dependency proposed in a plan is not an actual dependency inventory entry.

Use an individual record here when a real dependency/artifact is selected, with its disposition summarized in THIRD_PARTY_NOTICES.md. Do not create fictitious dependency entries while the inventory is empty. Each record must also identify the affected paths or binary package contents, original/third-party classification, reviewer/date, required notice locations, and unresolved restrictions. Record the actual version, not a floating branch or an unverified intended version.

## Review gate

- Confirm new emulator implementation and test helpers were independently authored from the behavior specification, with no imported or transformed reference code or assets.
- Confirm the contributor can license original work under MIT; preserve notices and add SPDX identifiers where appropriate.
- Inventory actual incorporated and bundled material, distinguish external tools/clients from shipped dependencies, and retain each component's own license text and notices.
- Review generated outputs and included evidence by their source and inputs; keep confidential or unreviewed captures local.
- Check the actual build/package contents for unexpected reference files, copied diagnostic tables, or bundled host/panel components before any future distribution.
- Record the checks actually performed and unresolved items; a completed documentation review does not qualify a future implementation or release.

Keep this record current when dependencies are introduced. Do not assert that a release is license-complete before inspecting its actual contents; no release exists at this stage.
