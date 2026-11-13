# Milestone 2 review handoff

This is the historical milestone 2 review/publication record. Current controller/thermal/clock status and evidence are recorded in the [milestone 3 review](milestone-3-review.md).

Date: November 13, 2026. Status: transport, registry, and persistence implementation complete for review against the milestone 2 fixture scope. The owner authorized implementation and local validation, with a stop before committing or pushing. At completion of review, all changes were local and unstaged, based on milestone 1 commit c476bf9c03e6070f23b63504e388dbc5928daf81. The owner subsequently authorized committing and pushing the reviewed implementation, tests, fixtures, and supporting documentation to main. No release, deployment, Pi installation, physical controller operation, or reference-repository modification was performed.

## Delivered behavior

Original C++17 implements a raw POSIX PTY, configurable stable path, exclusive state/path ownership, client reopen without reset, wall-clock token deadlines, ordered buffered output/backpressure, and owned-link cleanup. The independent streaming grammar preserves partial/duplicate/stale-token application, diagnostics, incremental saves, firmware identity, fixed-point C/F defaults, cold/narrowed V, and the original LCD byte fixture. No strict JSON parser is substituted for the Arduino wire grammar.

The registry implements the fixed original hardware identities, reference bus/pin ordering, signed-byte patch selectors, forced U ownership, first applicable diagnostic plus E3/old U on failed updates, accepted duplicates/reserved functions, enumeration record leakage, calibration sentinel, manual reads/writes, fallback actuator state, room omission, and zero-ROM disconnection. Saved-record reload validates without U normalization or a fabricated U/E3 cascade.

Persistence separates live and saved settings/constants/slots. Per-field saves, volatile C, intermediate S, E initialization, forced mode reload, strict profile target save threshold, R, and actual process restart are exercised. The original host-file representation records raw interoperability facts without copying the firmware EEPROM layout. Host-file errors terminate outside the serial protocol; they do not receive invented diagnostic IDs or success replies. [Operation and limitations](../../docs/milestone-2.md) describes the actual commands and lifecycle.

## Fixture accounting and tests

All source-defined reply expectations and the defaults/diagnostic datasets are unchanged. The follow-up review corrected only the initial presets of two unresolved characterization cases, as recorded below. Their execution_status metadata records specification-creation provenance; current scoped emulator execution is recorded in separate test reports and this handoff, without rewriting the frozen oracles. The independent runner consumes their expectations rather than generating expectations from emulator output. Presets construct declared initial state through a separate test-only driver; construction is not a new serial command or physical Arduino execution. Exact raw cases compare bytes, semantic cases preserve types/absence/order, diagnostic arguments are checked against reviewed signatures, and all output in each controlled window is accounted for.

| Reviewed cases | Result |
| --- | --- |
| 44 milestone 2 source-defined cases | Passed through the C++ engine, including wire/lifecycle and relevant storage/V semantic setup. |
| beer_filter_write_routing | Deferred: live filtering belongs to milestone 3. |
| test_mode_camera_timeout_is_skipped | Deferred: scheduled output/camera updates belong to milestone 3. |
| positive_derivative_and_counter_boundary | Deferred: scheduled PID/history belongs to milestone 3. |
| minimum_on_boundary_is_strict | Deferred: state/timer evaluation belongs to milestone 3. |
| Nine requires_reference_trace cases | Unresolved, never counted as passing or silently skipped success. |

Supplementary original regressions cover invalid known scalar/time/flag conversions, custom minus/decimal grammar, unescaped diagnostic bytes, forced off-mode reload, negative patch omission, FF ROM omission, and strict local-codec rejection of duplicate keys, bad numbers, unmatched surrogates, and excessive nesting. These clarify the contract without changing reviewed expectations; the [source-backed notes](../protocol/milestone-2-details.md) describe the additional facts.

Actual PTY tests cover erased boot, raw flags, identity, both ownership locks, real one-second partial-token waiting, every split point in a representative setting/query sequence, coalesced commands, assignment/manual output, client close/reopen, 2,500 replies under slow-reader backpressure, volatile C versus R, actual process restart, foreign path preservation, corrupt/wrong-version stores, E recovery, fatal host-write failure without a serial acknowledgment, and cleanup that preserves a foreign replacement path. These are emulator tests, not tests against Arduino or actual host/panel processes.

| Environment | Evidence |
| --- | --- |
| macOS ARM64; AppleClang 21.0.0, CMake 4.5.0, Python 3.15.2 | Debug build and all three CTest suites passed; address/undefined-behavior sanitizer build and suites passed. |
| Linux ARM64 container; GCC 13.3.0, CMake 3.28.3, Python 3.12.3 | Debug CMake build and suites passed; final address/undefined-behavior sanitizer build and all three suites passed. |
| Linux x86-64 container under emulation; GCC 13.3.0, Python 3.12.3 | Direct C++17 compiler build and all three suites passed. CMake was absent in this image; no dependency installation or claim of x86-64 CMake execution. |

Container runs used existing local images, network disabled, repository mounted read-only, and ephemeral build directories. Image IDs and external-tool disposition are in the [provenance record](../licenses/milestone-2.md). Final static checks covered 58 project files, 166 local links, seven anchors, 126 pinned source links, formatting/whitespace, MIT/SPDX notices, preserved source-defined oracles and root license/history, clean reference checkouts, unchanged HEAD, and an empty index. Generated binaries/reports/state remain ignored. Root MIT license and historical handoff/setup snapshots are unchanged.

## Follow-up review and corrections

The review found and corrected errors beyond the original fixtures: ordinary negative U patches were incorrectly applied; discovery reused its cursor across hardware groups and fabricated digital values; d incorrectly suppressed sensor reads when w was also supplied; raw numeric saturation could produce a sentinel; address parsing normalized lowercase and short/repeated prefixes incorrectly; and callback arguments did not model embedded NUL termination. The noncanonical-boolean fidelity guard also now follows ordinary validation so it cannot mask defined E6/E3/old-U failures. Source-backed behavioral notes now specify these facts before the independently authored corrections. The prior f:-2-to-254 regression was itself wrong and was replaced with the Arduino omission expectation, not treated as an immutable oracle. Source-defined JSON expectations and the two other JSON datasets remain unchanged. U_before_E now starts erased, and duplicate_function_remove_history now starts assigned, correcting inconsistent characterization setup without creating any passing oracle.

The pending h/d/U state is now bounded by recognized fields without imposing a transaction-length limit. State-file reads reject FIFOs without blocking, enforce their size limit during reads, and reject incomplete native device records rather than defaulting away corruption. These are host-environment representation checks, not new Arduino validators or diagnostics.

Validation now rejects non-CRLF/incomplete/blank frames, duplicate JSON keys, nonfinite numbers, unknown fixture formats/classifications/revisions, and invalid restart barriers. Presets seed explicit raw settings/constants/variables rather than reconstructing them from rounded readbacks; unsupported nonzero clock/history inputs fail instead of being silently ignored. The setup checks also validate the corrected characterization presets. Additional regressions cover each correction, long selector streams, short/lowercase/wildcard ROMs, signed attribute output on no-target records, and native-store failure cases. Client write boundaries can be coalesced by the kernel; actual engine chunk boundaries are tested separately through the fixture driver.

## Limits and review boundary

The continuously ticking controller/filter/PID state machine and physical thermal model are milestone 3 work. Command-side target derivation supplies the reviewed target/persistence scenarios but does not qualify repeated PID/integral histories. Probe readings currently use the fixed external 20 C baseline plus calibration, with no changing plant/filter history; dynamic LCD rendering/alternation is also pending. There is no assertion of full brewing/control or host/panel compatibility from these tests.

The nine reviewed characterization cases, additional malformed ROM/noncanonical bool cases, and hardware-dependent bus/duplicate/pin histories remain fidelity obligations. Detected unsafe unsupported paths halt outside serial rather than simulating native undefined writes or inventing Arduino responses. This halt is a disclosed emulator limitation, not reference behavior. No fixture pass closes those gaps. A stale symlink after unclean termination requires deliberate inspected cleanup; it is not overwritten automatically.

The owner reviewed this milestone and authorized its commit and push to main. The implementation, original MIT provenance, test evidence, and limits remain the publication record. No milestone 3 work is authorized or started.
