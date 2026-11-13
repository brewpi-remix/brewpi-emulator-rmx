# Protocol documentation

Milestone 1 is complete as a source-backed specification and original fixture deliverable for owner review. No emulator, executable conformance suite, or reference-hardware execution exists. The owner's firmware-first instruction supersedes earlier proposed behavioral improvements: preserve Arduino action/reaction, including deterministic bugs, while writing original MIT implementation later.

- [Behavioral contract v1](behavioral-contract.md): selected build personality, serial semantics, commands, schemas, timing, and persistence.
- [Defaults and units](defaults.md): full S/C/V data, fixed-point C/F behavior, identities, and external plant inputs.
- [Diagnostic metadata](diagnostics.md): version-3 IDs, typed arguments, reachability, and output ordering without copied expansion text.
- [Firmware findings](firmware-findings.md): required bugs/quirks and explicit characterization obligations.
- [Original protocol fixtures](test-vectors/README.md): machine-readable defaults, 43 diagnostic signatures, 48 source-defined cases, and nine characterization cases.
- [Milestone review](../development/milestone-1-review.md) and [provenance record](../licenses/milestone-1.md).

The [implementation plan](../../IMPLEMENTATION_PLAN.md) owns later milestones. This document set is normative for milestone 1 topics and supersedes inconsistent provisional protocol choices in earlier history. Undefined/hardware-dependent findings are not assigned invented exact outputs or counted as passing tests. Stop for review before implementation.
