# Milestone 2 provenance record

Date: November 13, 2026. All new original source, test helpers, CMake configuration, and documentation are copyright 2026 Lee Bussy and licensed under [MIT](../../LICENSE.md). Source/helper/build files carry SPDX-License-Identifier: MIT. The owner initially authorized milestone 2 implementation and validation with a stop before commit/push, then authorized committing and pushing the reviewed artifacts to main. The [review handoff](../development/milestone-2-review.md) records results and material limits.

## Original material and source exposure

The C++ streaming engine, local JSON codec, device representation, host-file serialization, POSIX transport/storage ownership, CMake build, Python fixture/regression/PTY tests, and test-only C++ driver were independently authored in this task. No upstream source/test/helper/header/macro/routine/table/asset/binary was imported, linked, vendored, translated, or mechanically rewritten. Implementation structure uses original maps, event-driven token states, host JSON storage, and native POSIX resources; it does not recreate the firmware class/header/EEPROM layout. Runtime code does not load fixture expectations or reference repositories.

The behavioral inputs are the reviewed MIT specification and original milestone 1 data, plus [documented additional interoperability facts](../protocol/milestone-2-details.md). Source exposure during the earlier review is disclosed. Limited additional source inspection in this task clarified scalar conversion order/grammar, device storage widths/sentinels, and forced mode reload; the cited reference files retain their own licenses. These facts were recorded as original prose, with independent implementations and regression inputs. This is source-informed independent work, not a formally separated clean-room claim.

The tests use Python's standard library and execute the original C++ build. They do not import or execute BrewPi/Fuscus modules or test code. Source-defined JSON expectations and the defaults/diagnostic datasets remain unchanged; only two unresolved characterization presets were corrected during follow-up review; expected streams are not generated from the implementation. Reports are ignored local emulator results, not incorporated external captures. No raw Arduino capture, upstream generated source, or third-party asset is included.

## External tools and dependencies

No third-party library source, generated table, package, or asset is incorporated or vendored. Original code uses the C++17 standard library and POSIX/libc facilities supplied by the selected operating system. No runtime library, toolchain, container image, host/panel source, or reference binary is redistributed. Executable/system-library distribution closure remains a future package-specific review, not a completed release-license assertion.

| External tool/environment actually used | Role and disposition |
| --- | --- |
| AppleClang 21.0.0, CMake 4.5.0, Python 3.15.2, clang-format 23.1.5 | Local compile/configure/test/format tools; not incorporated or redistributed. |
| GCC 13.3.0, Python 3.12.3, CMake 3.28.3 in Linux ARM64 | Local container build/tests, including sanitizers; system libraries remain external. |
| GCC 13.3.0 and Python 3.12.3 in emulated Linux x86-64 | Direct compiler and tests; CMake not available/installed in that image. |
| Existing local wsprry-gray-line-tools:local, image sha256:4df3c8dd73723be39fd3a16be972ffe023f6c4adad812c17c85be218f3f0f9bc | ARM64 external build environment, network disabled, source read-only, ephemeral output; no image content enters source. |
| Existing local rp1-item4-ubuntu-amd64:20261111, image sha256:71380a09cdd629929563374f961f38f9d4cbc7b78ba8f4caf1ae33910f8f2bfd | Emulated x86-64 external build environment with the same isolation; not redistributed. |

The [third-party incorporation inventory](../../THIRD_PARTY_NOTICES.md) remains empty. Tool execution does not change the tools' or system libraries' own licenses. No package installation/download, reference execution, host/panel integration, hardware operation, or release was performed.

## Review gate performed

Reviewed new file scope, SPDX/copyright coverage, source/build dependency declarations, preserved source-defined fixture expectations and MIT license, ignored generated outputs, and absence of reference paths/imports in build/runtime/tests. Standard wire names/IDs/defaults/minimal phrases are recorded interoperability facts. No copied diagnostic expansion table or implementation is shipped. Behavioral tests establish the stated milestone scope only; they cannot prove future authorship or unexecuted reference behavior. Future contributions, dependencies, packages, and release contents require their own [provenance gate](README.md#review-gate).

## Follow-up review provenance

The follow-up review inspected additional pinned communication facts for negative patch application, discovery cursor/value behavior, sensor read/write precedence, numeric saturation, short/lowercase/wildcard address handling, and C-string token visibility. The findings are recorded in original [clarification prose](../protocol/milestone-2-details.md), with original regression inputs and independently authored corrections to the event/map implementation. No source routine/header/table/test was imported, translated, or executed; the reference checkouts remain unchanged. The native storage and test-matcher corrections introduce no external dependency. Reviewed source-defined JSON oracles, the root MIT license, and historical setup/handoff records are preserved; two unresolved characterization presets were corrected to match their stated evidence requirements. No milestone 3 logic, commit, push, release, or device work was introduced.
