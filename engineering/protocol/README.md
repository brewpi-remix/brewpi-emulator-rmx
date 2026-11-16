# Protocol reference

The emulator follows the normal Uno/RevC BrewPi Remix controller personality over a PTY. Serial commands preserve firmware types, byte framing, mutation order, diagnostics, timing, and deterministic quirks. Native scenario/store/checkpoint JSON is a separate interface.

- [Behavioral contract](behavioral-contract.md)
- [Command details](commands.md)
- [Controller, filters, clock, and thermal model](controller.md)
- [Defaults and units](defaults.md)
- [Diagnostic signatures](diagnostics.md)
- [Firmware quirks and compatibility limits](firmware-findings.md)
- [Original fixture data](test-vectors/README.md)

Required wire identifiers and source-backed facts establish interoperability; no reference implementation is incorporated. See the [authorship contract](../../CONTRACT.md). Undefined-memory, overflow, and physical-bus outcomes remain unqualified where no exact reference result exists.
