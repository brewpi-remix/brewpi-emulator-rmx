# Development guide

Read the [contract](../../CONTRACT.md), [plan](../../IMPLEMENTATION_PLAN.md), and [architecture](../architecture.md) before changes. Milestone 1 is the published firmware specification; milestone 2 is an original C++17 transport/registry/persistence implementation reviewed and authorized for commit and push to main. Milestone 3 work, CI, releases, deployment, reference edits, and hardware operations remain outside this publication task.

Use the tested commands in the [build/run guide](../../docs/milestone-2.md). The [milestone 2 review](milestone-2-review.md) records fixture accounting, Linux/macOS/sanitizer evidence, and limits. [Milestone 1 review](milestone-1-review.md) is the historical specification/static-check handoff. Firmware action/reaction, including bugs, governs all behavior; four reviewed controller cases are deferred to milestone 3, and nine characterization cases remain unresolved.

## Tools and layout

The foundation is C++17, CMake, a system compiler, the C++ standard library, and POSIX APIs. Python's standard library drives tests; no Python package or third-party JSON/controller library is needed. Actual exercised tool/image versions are recorded in [milestone 2 provenance](../licenses/milestone-2.md). Source belongs in src, independent tests in tests, future build helpers in cmake, future configuration/scenarios in config, and optional service templates in systemd. Generated binaries/reports/state belong in ignored directories. Follow root formatting files.

## Validation and provenance

Build and run CTest after relevant source/test changes. Use the sanitizer configuration for native memory/arithmetic checks; passing sanitizers are not AVR-equivalence or hardware evidence. Check changed documentation links, SPDX markers, whitespace, fixture preservation, and generated-output exclusions. Isolate ordinary validation from working BrewPi state/services/serial devices. Actual host/panel and Pi checks remain separate milestones.

The public repository is [brewpi-remix/brewpi-emulator-rmx](https://github.com/brewpi-remix/brewpi-emulator-rmx); local main tracks its HTTPS origin. The owner authorized committing and pushing the reviewed milestone 2 artifacts to main; no milestone 3 work is authorized. Keep original work under MIT, record additional behavioral facts before implementation, and never copy or translate reference routines/helpers. The [provenance gate](../licenses/README.md#review-gate) and [third-party inventory](../../THIRD_PARTY_NOTICES.md) remain mandatory for new dependencies/material.
