# 0.0.1-rc.1 candidate release notes

Prepared November 16, 2026, America/Chicago, for owner review. This unsigned candidate has not been tagged or publicly released. Original project code, helpers, fixtures, configuration, and prose are independently authored MIT work, copyright 2026 Lee Bussy. External GNU/compiler/runtime/source material retains its own terms and required notices. No BrewPi/Fuscus implementation, transformed routine/test, generated table, font, or asset is reused.

## Candidate identity and scope

The application reports brewpi-emulator-rmx 0.0.1-rc.1. CMake's numeric version is 0.0.1, with prerelease rc.1. Serial n deliberately identifies the Arduino personality 0.2.13/8f1fa12, shield 2, board s, simulation 0, and logging 3; it does not report the application release version. The qualified original source commit is f717d36364778ad48cd28bb5ae5a221c29c5db49. Later validation/documentation commit cad8a2a71922efa99b3431ca75c12096249a3a0e and the uncommitted R6 handoff do not replace that candidate identity.

This is a hardware-free, single-chamber C++17 emulator for the selected BrewPi Remix host/panel. It provides actual PTY serial transport, firmware-like registry/settings/persistence, an independently modeled five-US-gallon thermal plant with separate beer/chamber/room temperatures and fermentation heat, paced/pause/accelerated simulation time, explicit coherent checkpoint continuation, and optional terminal/graphical LCD controls. Arduino action/reaction, including documented deterministic bugs, remains authoritative. Owner-approved local interactive confirmation, bounds, and display rules remain separate from ordinary serial behavior.

## Supported and unqualified use

| Platform or feature | Evidence and limit |
| --- | --- |
| Generic Linux x86-64 and AArch64 | Debian 12 64-bit userland, GCC 12 runtime baseline, generic x86-64/ARMv8-A instructions; native Release/sanitizer/minimum-tool, packaged client/runtime, and recovery evidence. Other distributions or older runtimes are not qualified. |
| Headless and terminal operation | No Python/Tcl/Tk needed for the core executable or Unicode terminal. Private PTYs, endpoint ownership, storage, blocking/backpressure, and optional terminal controls are validated. |
| Graphical LCD | Optional original Python helper requires Python 3.9+, tkinter/_tkinter, Tk 8.6+, and a graphical session/font. Native macOS GUI evidence and Linux headless/fallback checks exist; a Linux graphical desktop is not qualified. |
| macOS ARM64 | Development/test and native graphical-control evidence only; no macOS binary distribution. |
| External host/panel | The pinned brewpi-script-rmx/brewpi-www-rmx pair passed 17 isolated workflows. Other panels and live BrewPi installations are not qualified. |
| Packaging | One original source archive, two Linux binary archives, mandatory NOTICES and GNU corresponding-source companions, and SHA-256 manifests. No container image, DEB/RPM, installer, or 32-bit/Windows distribution. |

The final binary payload contains seven project files, including the optional original lcd-viewer helper; it bundles no shared OS library, Python/Tcl/Tk runtime, or font. Keep the complete five-archive set and the final R5 notices/source companions together. The archived preliminary third-party notice alone is incomplete. Checksums identify bytes; this unsigned RC makes no signature or attestation claim.

## Validation and limitations

All 48 source-defined fixtures pass; nine reference-characterization cases remain explicitly unresolved and do not count as conformance passes. Both native Linux architectures have final package/client evidence and exact executable hashes matching the candidate source's hosted Release receipts. Nine hosted CI jobs passed at candidate commit f717d36, run 43859184004, attempt 1; nine also passed for later R4/R5 tooling commit cad8a2a, run 43876988549, attempt 1.

Each architecture completed the accepted original 24-hour normal and six-hour 60x workloads. Those runs executed the earlier source 38769c168428898a39e1c30e94607faf46f2e551 and its recorded earlier binary hashes. The owner explicitly approved source-based carry-forward for the unchanged core when integrating local controls; actual revised packages also passed focused controls checks and separate 300-second 1x/60x native workloads. These are not new 30-hour soaks of the final hashes. The original x86 normal workload completed before a reporting failure; its completed workload was accepted by retained evidence recovery, while the original overall failure remains recorded. No partial runs were stitched together.

On the native x86 operating qualification only, an independently reproduced host/ASan address-space startup conflict required process-scoped setarch -R for the sanitizer CTest tree. The positive sanitizer control remained fatal. Normal Release/client/runtime checks retained normal ASLR; no shipped byte or host sysctl changed.

Manual host reopen/restart is required when an emulator process replaces its PTY. Firmware-saved settings can intentionally differ from live values; ordinary process restart reloads saved controller state and starts a fresh external plant, while explicit checkpoint resume restores coherent history without adding downtime. Profiles, CSV dates, and charts use wall time even when simulation is accelerated. The legacy panel needs the documented profile-tab browser-resize workaround in the tested environment, profile-editor dragging is not claimed, and mixed Celsius/Fahrenheit chart history can show a misleading apparent temperature spike.

Physical Pi peripherals/model/OS/SD-card/power qualification, systemd activation/boot behavior, Arduino/USB/GPIO/Bluetooth hardware, the nine Arduino cases and additional undefined outcomes, full AVR arithmetic/artifact parity, and physical power-loss durability are not claimed. A generic Linux test on an ARM host does not close those physical gates. Native store/checkpoint formats remain v1, without a migration or forward-compatibility promise; retain matching files and the candidate version. Final 0.0.1 requires a distinct candidate build and applicable validation, not relabeling this RC.

See the [candidate guide](rc1-guide.md) for build/run/staging and recovery. The repository's engineering/development/software-release-rc1-dossier.md maps each bounded claim to its exact retained evidence and hashes. R6 is prepared for review; committing, pushing, tagging, publication, deployment, and repository-rule/service activation require later authorization.
