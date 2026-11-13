# Changelog

No release has been made. Dates use the project owner's America/Chicago calendar.

## Unreleased

### Added

- Milestone 3 original controller/filter/peak/LCD behavior, independent thermal/probe/fermentation model, paced clock/pause, checkpoint resume, scenario examples, and six-suite local validation. All 48 source-defined reviewed cases now execute; nine characterization cases remain unresolved. Reviewed and authorized for commit and push to main.

- Original MIT milestone 2 C++17 transport, registry, persistence, local codec, and CMake build, with reviewed-fixture, regression, and actual PTY/process tests, plus review/provenance/build guidance.

- Milestone 1 firmware behavioral contract, full defaults/units, version-3 diagnostic metadata, 21 fidelity findings, original protocol fixtures, and provenance/review records.

- Source-backed implementation plan and compatibility review.
- MIT license for independently authored project code and documentation.
- Project contract, contributor and agent instructions, security guidance, and provenance records.
- Repository formatting metadata, contribution templates, and documented directories for future implementation and operator guidance.
- Public [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx) repository and initial `main` documentation/scaffolding baseline, with the local repository initialized and the HTTPS `origin` configured.

### Clarified

- Arduino firmware action/reaction now governs every behavioral question, including deterministic bugs; earlier corrective protocol/controller policies are superseded. Undefined/hardware-dependent outcomes remain explicit characterization requirements without invented exact replies.

- MIT contribution terms, contributor notices/SPDX requirements, and independent authorship rules for automated transformations.
- Provenance review categories for incorporated libraries, external tools/clients, generated outputs, and captured evidence.
- Reserved protocol-vector documentation, consistent full-state checkpointing, physical-load routing, and auxiliary thermal power in the proposed plan.

### Status

- Milestone 2 is published on main. Milestone 3 controller/thermal/clock work is reviewed and authorized for commit and push to main. Actual host/panel integration and Pi qualification remain outstanding.
- The published main baseline contains reviewed milestone 1 artifacts. No software release, CI, package, deployment, or device operation is included in milestone 2.
