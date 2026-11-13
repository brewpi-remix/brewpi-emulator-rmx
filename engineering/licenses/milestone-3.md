# Milestone 3 provenance record

Date: November 13, 2026. Original source, tests, scenario examples, build changes, and documentation are copyright 2026 Lee Bussy, licensed under the root [MIT License](../../LICENSE.md). New source/helper files carry SPDX-License-Identifier: MIT; JSON examples have their adjacent [configuration notice](../../config/README.md). The owner subsequently authorized committing and pushing the reviewed milestone 3 implementation, tests, and supporting documentation to main.

## Original work and behavioral inputs

The controller evaluator, independent filter delay-state realization, conservative midpoint thermal model, paced clock, checkpoint representation/validation, LCD shadow, and new tests/scenarios were authored for this project. No BrewPi/Fuscus routine, header, macro, source file, generated table, test/helper, binary, or asset was copied, linked, vendored, translated, or mechanically rewritten. Runtime code does not read source references or expected fixture output. Data structures are original native maps, delay matrices, external energy state, and JSON snapshots, without importing reference class/EEPROM layouts.

The reviewed MIT contract/defaults/diagnostics/fixtures and independently written [milestone 3 behavioral/mathematical notes](../protocol/milestone-3-details.md) supplied interoperability facts. Additional pinned source inspection established observable filter arithmetic, sensor countdowns, PID/state/peak/output order, clock widths, and LCD/camera timing before implementing those facts. Source exposure is disclosed; no formally separated clean-room assertion is made. Reference code retains its own license, and behavioral citations do not relicense it.

The thermal equations, fixed-step midpoint integration, deterministic noise arithmetic, and scenario inputs are independently chosen conventional mathematics and original external hardware modeling. No firmware simulator/Fuscus physics routine was imported or executed. The binomial filter impulse oracle was calculated independently from the documented transfer function, not captured from reference or emulator output. Other tests check original controlled inputs and conservation/analytic expectations. The three reviewed JSON datasets are unchanged; new evidence consists of ignored local reports rather than copied upstream captures/tests.

The follow-up review independently authored physical-component validation, exact native checkpoint-count restoration, and additional negative-input/checkpoint/drift regressions from these existing specifications and conventional arithmetic. No additional dependency, reference implementation, raw capture, or generated upstream material was introduced; the reviewed JSON datasets remain unchanged.

## Dependencies and tools

There is no newly incorporated library, asset, package, or generated upstream code. Original C++17 uses the standard library and system POSIX/libc facilities, and tests use Python's standard library. CMake, compilers, clang-format, sanitizer runtimes, container images, and system libraries are external tools/environment components, not redistributed project source. Future packaging must inspect its actual binary/library closure separately; this is not a release-license guarantee.

| Exercised external environment | Disposition |
| --- | --- |
| macOS ARM64: AppleClang 21.0.0, CMake 4.5.0, Python 3.15.2, clang-format 23.1.5 | Native compile/configure/test/format and sanitizers, not incorporated or bundled. |
| Linux ARM64: GCC 13.3.0, CMake 3.28.3, Python 3.12.3 | Existing local wsprry-gray-line-tools:local image sha256:4df3c8dd73723be39fd3a16be972ffe023f6c4adad812c17c85be218f3f0f9bc, network disabled, repository read-only, ephemeral outputs. |
| Emulated Linux x86-64: GCC 13.3.0 and Python 3.12.3 | Existing local rp1-item4-ubuntu-amd64:20261111 image sha256:71380a09cdd629929563374f961f38f9d4cbc7b78ba8f4caf1ae33910f8f2bfd; direct compiler/test execution with the same isolation, without installing CMake or dependencies. |

No toolchain/image/host/panel/reference code or binary is redistributed. Implementation/review validation performed no package installation/download, physical device operation, reference execution, or Pi deployment; the owner subsequently authorized the reviewed source/documentation commit and push. [Third-party notices](../../THIRD_PARTY_NOTICES.md) continue to distinguish the empty incorporation inventory from external tools and their own terms.

## Gate and limits

The review checks new source/helper SPDX notices, build/dependency declarations, fixture preservation, source paths/imports, ignored outputs, root license/history, and clean pinned reference checkouts. The [milestone review](../development/milestone-3-review.md) records actual tests and limits. Undefined-memory/artifact/bus obligations remain unresolved, without fabricated passing oracles. Original MIT authorship does not authorize future code reuse, prove future dependency provenance, or establish firmware/Pi parity. Subsequent contributions and packages must repeat the [provenance gate](README.md#review-gate).
