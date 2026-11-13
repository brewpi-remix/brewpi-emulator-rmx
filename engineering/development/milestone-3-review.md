# Milestone 3 review handoff

Date: November 13, 2026. Status: controller behavior, independent thermal model, and clock implemented and reviewed. Following implementation, review, and fixes, the owner authorized committing and pushing milestone 3 implementation, tests, and supporting documentation to main. The reviewed work is based on milestone 2 commit 5e88d25ce5af8b32b0b78edc774273315aeb7fd2. Milestone 4 host/panel integration, release/deployment, reference execution, physical hardware, and Pi installation have not been started.

## Implemented scope and fidelity

The original [behavioral/mathematical specification](../protocol/milestone-3-details.md) records additional pinned facts before independent implementation. Controller actions now include calibrated sensor histories, three-section fixed-point filters, the documented incorrect live beer-filter routing, hourly slope sampling/countdowns, PID/integral behavior, ordinary and minimum-on/wait states, peak detection/adaptation and typed I17/I18/I19/I20 formatting, camera/test-mode behavior, physical output polarity, and retained LCD layout/room alternation/reset timing. Target callbacks retain their synchronous PID/state effects and pre-write annotations; ordinary transition T precedes output updates. Default values, legacy parsing/registry/persistence quirks, and narrowed integral telemetry remain intact.

The external plant is an independently modeled two-node energy balance against a separate room boundary, not the firmware simulator or a changed controller policy. It implements reviewed physical capacities, fixed load wiring, conduction, fermentation heat, explicit daily room phase, door conductance, quantization/lag, and deterministic bounded noise. Controller milliseconds and seconds retain their reference widths; a wider age tracks external equipment. Fixed 100 ms integration and one-second controller eligibility are independent of wall pacing. Parser/output blocking defers controller evaluation while external equipment/time continue, then permits one due evaluation rather than a burst of missed controller samples.

R resets controller globals/clocks/histories while retaining plant age/state and saved configuration. E retains the source's smaller reset scope. Ordinary process restart begins a fresh external scenario; explicit checkpoints restore live/saved controller state, counters, histories, latches/pins, display/timer, physical state, random sequence, and fractional time without adding downtime. Snapshot validation rejects incomplete state transactionally, and resume checks saved-store consistency. Scenario files are read-only inputs with no adjacent lock requirement. [Operating guidance](../../docs/milestone-3.md) documents tested commands and limits.

## Reviewed fixture execution

The three reviewed milestone 1 JSON datasets are unchanged from the published milestone 2 baseline. Their metadata records specification creation, while execution evidence remains in separate ignored reports. The original runner now executes every source-defined case, including semantic controller actions and postconditions, rather than skipping the four previously deferred cases. Repeated time/evaluation requests use batched test envelopes to avoid serialization overhead; each declared engine call still executes, and peak observation stops at the first emitted event as in the original unbatched test.

| Fixture status | Result |
| --- | --- |
| Source-defined protocol/controller cases | 48 passed. |
| Deferred milestone 3 cases | Zero. The filter routing, test-mode camera timeout, derivative/integral counter, and strict minimum-on cases execute and pass. |
| requires_reference_trace cases | Nine unresolved, with no invented exact output, physical execution, or passing status. |

No oracle was changed to accommodate the implementation. Test-only construction remains distinct from serial commands and physical Arduino execution. The test driver exposes semantic evaluations and snapshots only to local tests; production protocol fields and N identity remain the reviewed firmware dialect, without a new management serial API or simulator Time field.

## Additional validation

Six suites exercise original code without importing or executing reference modules/helpers. In addition to the unchanged protocol/legacy regression/PTY checks, validation covers:

- A closed-form binomial DSP impulse oracle, constant-input filter histories, exact history restoration, and a guard against executing undefined reference shifts natively.
- Conservative energy balance, analytic isolated heater/cooler ramps, exact reviewed heat capacities, physical lag, fixed wiring under function reassignment, and preserved electrical latches on uninstall.
- Reviewed fermentation breakpoints/interpolation and beer-node energy, room phase, bounded deterministic noise, lag, and DS18B20 quantization.
- Identical complete snapshots for equal simulated events grouped as 1x/10x/60x, plus real-process pacing at those factors and paused wall-clock serial timeouts.
- Exact checkpoint continuation across a fractional integration step with nonzero histories/noise/random state; paused process resume with no downtime; incomplete snapshot rejection; mismatched saved-store rejection without rollback.
- The 600-second initial switch/off boundary, transition telemetry, blocked-parser sampling, modulo clock wrap, integral sign reduction/suppression/decay/windup gates, real filtered turning-point I17/I18 persistence, periodic LCD reset, digital door readback/inversion/annotation/light, the exact camera timeout boundary, and controlled virtual disconnection/reconnection diagnostics/history reseeding.

| Environment | Evidence |
| --- | --- |
| macOS ARM64, AppleClang 21.0.0, CMake 4.5.0, Python 3.15.2 | Debug and address/undefined-behavior sanitizer builds; six suites passed. |
| Linux ARM64 container, GCC 13.3.0, CMake 3.28.3, Python 3.12.3 | Address/undefined-behavior sanitizer build and all six suites passed with the repository read-only and network disabled. |
| Emulated Linux x86-64 container, GCC 13.3.0, Python 3.12.3 | Direct C++17 compiler builds and all six suites passed; no x86-64 CMake execution or hardware claim. |

An additional native macOS check completed four two-hour simulated runs: fridge targets 16/24 C and beer targets 18/22 C, with physical temperatures moving in the requested direction. These are model trajectory sanity checks, not reference captures or exact controller-parity oracles; original local results are in ignored test-results/milestone3-trajectories.json.

Static checks cover 70 project files, 194 local documentation links, eight anchors, 144 revision-pinned source links, formatting/whitespace, SPDX/copyright coverage, unchanged reviewed JSON/defaults/diagnostics/license/history, clean pinned references, unchanged HEAD, and an empty Git index. Local JSON reports remain ignored build outputs. Compiler/container versions, image IDs, authorship, and dependency disposition are in [milestone 3 provenance](../licenses/milestone-3.md). No third-party code/library, generated upstream table, reference binary, or raw capture was incorporated. Root MIT text, historical handoff/setup files, and reference repositories are preserved.

## Follow-up implementation review

The owner subsequently authorized review and fixes within milestone 3, again excluding milestone 4, staging, commits, and pushes. The review checked controller scheduling/action order, fixed-point/filter/PID/state/peak behavior against the existing specification and selected pinned source facts, physical inputs/energy, checkpoint state and validation, real-process tests, and the MIT incorporation boundary. Source inspection supplied behavior facts only; no reference code or tests were executed or incorporated.

| Finding | Correction and regression evidence |
| --- | --- |
| Negative physical inputs could be hidden by positive aggregate heat capacities. | Validate all seven volume/density/specific-heat/capacity components before combining them. Original model tests individually reject negative components even when a derived total would stay positive. This changes external scenario validation, not Arduino command validation. |
| Checkpoint restore narrowed the native 64-bit integral-branch instrumentation count to 32 bits. | Restore nonnegative integer counts through the exact JSON integer range. An original regression round-trips 4294967296 and verifies transactional rejection of negative, fractional, and inexact-range counts. Arduino controller word widths remain unchanged. |
| I19/I20 adaptation had no exact end-to-end drift diagnostic assertions. | Original controlled-history tests exercise both strict timeout boundaries, exact diagnostic IDs/string padding/precision, the preserved sentinel-derived error, resulting peak words/estimators, pending flags, and saved settings. Expected values come from independently calculated fixed-point arithmetic and reviewed diagnostic formatting, not a reference capture. |

After these corrections, all six suites were rerun and passed in the native macOS debug and sanitizer builds, the Linux ARM64 sanitizer build (137.89 seconds total), and the emulated Linux x86-64 direct build. Formatting, documentation/source links, fixture integrity, MIT notices, clean pinned references, unchanged HEAD, and empty-index checks also passed.

The three reviewed JSON datasets and their passing oracles are unchanged. The added drift tests preserve the firmware bug: replacing the logged missing peak does not recompute its already-derived adaptation error. The nine characterization obligations remain unresolved. The prior two-hour trajectory checks remain earlier sanity evidence; review regression validation is reported with the environment checks above.

## Limits and stopping point

These are source-informed emulator tests and independent mathematical/physical checks, not observed reference-firmware conformance or hardware qualification. The nine reviewed characterization cases remain open, as do additional undefined shift/overflow paths and physical bus/complex duplicate/electrical history outcomes. Native overflow guards are disclosed emulator limitations, not faithful Arduino rejections. No native undefined memory access is used as an AVR oracle. Full host/panel integration and agreed Pi qualification remain later milestones.

The physical model is illustrative external equipment, not a calibrated refrigerator or measured fermentation. Acceleration changes pacing only; it does not accelerate actual host wall-clock profiles or qualify all machine/rate combinations. Checkpoints capture a quiescent logical simulation boundary, not a host connection or serial backlog; an incomplete command or undrained reply prevents checkpoint replacement. Alternate instance identities require a future configured hardware map.

The implementation, evidence, fixes, and independent MIT provenance were presented for owner review. The owner subsequently authorized committing and pushing these reviewed milestone 3 artifacts to main. Milestone 4 work, service changes, releases, and deployment remain unapproved.
