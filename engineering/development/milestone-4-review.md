# Milestone 4 review handoff

Date: November 13, 2026. Status: isolated host/panel integration implemented and reviewed. Following review and fixes, the owner authorized committing and pushing its setup, tests, and supporting docs to main. The owner authorized milestone 4 using a separate test setup, preserving Arduino behavior and independent MIT licensing, with a stop for review before committing or pushing. Baseline is published milestone 3 commit 10f95c7308153bf37fcea9f36563c0cb5224a568. Milestone 5, physical hardware/Pi work, releases, and deployment remain unapproved.

## Delivered scope and isolation

Original opt-in [integration tooling](../../tests/integration/run-isolated.sh) now builds a disposable Linux environment and drives the pinned external host and panel against the original emulator. [Operating guidance](../../docs/milestone-4.md) describes the exact launcher, interfaces, controls, local evidence, and restrictions. [Provenance](../licenses/milestone-4.md) distinguishes original MIT test sources from the external GPL clients, browser, packages, and raw captures.

The original C++ production source and reviewed protocol/default/diagnostic JSON datasets remain unchanged from the milestone 3 baseline. No host expectation was addressed by altering Arduino behavior. Reference repositories remain clean at their pinned revisions; runtime clones have their own configuration, UNIX socket, serial relay, logs, profiles, controller store, and web data. Source application code hashes are compared before/after execution. The final test container has no network, published port, physical-device mount, privileged mode, or working BrewPi state/service access.

A transparent original relay records and forwards real PTY bytes without synthesizing responses. The real Python host opens its explicit virtual serial endpoint, and PHP plus Chromium exercise the real panel. Acceptance checks distinguish host cache values from saved controller state because some host mutations are optimistic. Native tests run before application startup and remain separate from integration evidence.

## Workflow acceptance

| Planned workflow | Interface and checks |
| --- | --- |
| Startup | Real host identifies expected 0.2.13/Uno/RevC personality; captured serial begins n then s/c/v. Erased state remains uninitialized until reset. |
| Factory initialization | Browser clicks the normal reset button; PHP sends resetController, the real host sends E, and the emulator creates a valid version-4 store. |
| Discovery/assignment | Browser discovers three original probe identities and four physical actuator pins, assigns seven slots/functions/polarities, and consumes the real host's installed/available cache. |
| Modes and targets | Browser beer/fridge/off controls reach the host, controller, and saved representation. Off mode waits for disabled targets; optimistic host cache changes alone do not count as acceptance. |
| LCD and units | Captured L records retain four twenty-byte rows and B0 degree cells. The real host returns room/fridge alternation; browser maintenance controls exercise C→F→C and saved units. |
| Defaults | Browser C reset restores live gain while retaining the earlier saved gain; S demonstrates default live estimators with an intermediate pre-default saved estimator. |
| Profiles | Original CSV data is saved through the actual PHP endpoint; browser Open/OK/Apply selects/activates it. The real host sends beerSet:null in the blank segment and later resumes at 21 C using ordinary wall time at 1x. Profile-editor interaction is not claimed. |
| Calibration/deactivation/manual output | Explicit real host UNIX-socket messages exercise calibration/readback, deactivation/null readback, reactivation, test mode, and manual heater on/off. These are not labeled browser-control evidence. |
| Reset/rediscovery | Browser factory reset clears installed slots; real host reports seven available devices, then browser assignment reinstalls them. |
| Dynamic heating/cooling | A separate 60x constant-beer-target phase uses browser target changes and the real host to observe heating/cooling states and changing physical probe temperatures. Host chart/profile/log clocks remain wall time. |
| Process restart | Stop/reopen host and emulator against the same saved store; restore seven slots, beer target, and the saved gain after a deliberately volatile C reset. Ordinary restart starts a fresh external plant. |
| Logs/chart | Real host creates CSV/JSON data; PHP serves it and the browser renders chart canvases. Maintenance View logs consumes actual host stdout/stderr files. |

## Integration findings

The host's initial configuration defaults differ from firmware defaults, but startup responses overwrite its cache with the reviewed firmware values. No emulator default was changed to match the host's initial dictionaries. Command annotations can show the pre-mutation target, and immediately read host caches can be stale/optimistic; the fixture waits for controller-backed acceptance instead of treating those intermediate states as firmware defects.

The selected legacy panel may render a sample-profile chart while its tab is hidden, causing chart elements to overlap Open when that tab is revealed. The normal Apply action also schedules a five-second control-panel refresh that can change the selected tab. The fixture waits for that refresh and uses a normal browser resize after revealing the profile tab; the panel's own resize handler restores layout, and ordinary Open/OK/Apply clicks then work. No forced click, patched CSS/JavaScript, injected application handler, or reference modification is used. This workaround and the exact browser environment qualify the UI evidence.

The final chart retains numeric records written during the Fahrenheit portion of the unit round trip, then displays the current Celsius label after switching back. Its apparent early 68-degree spike is a 20 C reading logged as 68 F, not physical overheating. This is an observed external-client history/display limitation; the fixture preserves it and does not claim a single-unit thermal trajectory from that mixed-unit chart. The later heating/cooling assertions use device readbacks after returning to Celsius.

Environment preparation initially exposed missing build/Python/PHP tools, and early automation attempts hit PHP-readiness and hidden-tab-layout races. These were test-environment/orchestration repairs, not passing workflow evidence or production behavior changes. The final standalone recipe uses a public digest-pinned Debian base, explicit native/PHP/browser tooling, and pinned Python dependencies. Raw failed-attempt outputs remain ignored local files.

## Follow-up review and corrections

The owner authorized review/fixes within milestone 4, again excluding milestone 5, staging, commits, and pushes. Production Arduino behavior, the independent MIT boundary, and the reviewed JSON oracles are unchanged. The review found and corrected these evidence and orchestration gaps:

| Gap | Correction |
| --- | --- |
| An existing evidence directory could retain old passing results, append stale serial records, or keep an apparent pass after a launcher failure. | Reserve a new directory atomically, reject reuse without modifying old bytes, write launcher status, invalidate a primary pass on any nonzero launcher exit, and retain the earlier child report separately. |
| Dynamic checks searched all prior T records, allowing an earlier phase's state to satisfy a later demand. A partially appended capture/frame could also cause intermittent parse failures. | Tag emulator sessions, scope state assertions to the resumed session and post-target-change window, require the associated beer target, and parse only complete records/frames while rejecting malformed complete data. |
| Device count, degree/unit labels, deactivation flags, and canvas presence did not prove every documented behavior. | Check exact assignment fields against unchanged reviewed defaults, numerical C→F→C readings, null deactivation and calibrated reactivation, confirmed test mode/manual readback, CSV structure, and the actual browser chart response's state/temperature history. |
| An interruption could bypass ordinary cleanup; a relay/copy failure could prevent later cleanup/audit, and nonzero application exits were not consistently disqualifying. | Handle termination and BaseException, make cleanup idempotent, attempt independent cleanup/audit stages, reject abnormal host/emulator exits, use an owned container ID/init process, and impose a bounded whole-run timeout. |
| The original audit covered only 77 code files, earlier host logs were overwritten on restart, and data collection included unrelated bundled sample datasets. | Audit all tracked files except the declared mutable active-profile CSV, archive logs for each emulator session, and collect only the generated test-batch data directories. External evidence remains ignored and is not treated as MIT source. |

Eight original negative regressions cover evidence reuse, build failure, a launcher failure after an apparent pass, owned-container/isolation arguments, partial/malformed/session-scoped traces, non-code reference tampering, cleanup-stage failures, termination handling, and incorrect device mappings despite a matching count. All eight passed locally and in the same offline tool image. The complete application run's initial helper gate had seven checks; helper-review-checks.log separately records all eight after adding the termination regression. The saved launcher now runs all eight before native/application validation. The unchanged native suites and all 17 strengthened integration records also passed. Launcher and cleanup reports both passed, with host exit codes [0,0,0].

## Evidence and limits

The final saved launcher completed successfully with 17 passing interface-specific integration records and zero JavaScript errors. All six native suites passed in the same final environment, including 48 source-defined reviewed fixture cases, zero deferred cases, and nine unresolved reference-characterization cases. The reviewed runtime-clone audit found 160 tracked reference files unchanged, including code, assets, licenses, and supporting files; the active host profile CSV is explicitly recorded as mutable runtime input. The container exited and was removed; the local external tool image remains available, with no lab applications or published ports left running.

| Final external environment | Observed version |
| --- | --- |
| Linux ARM64 container | Debian 12 bookworm; GCC 12.2.0; CMake 3.25.1 using the Make generator. |
| Host interpreter | Python 3.11.2 and the exact packages in tests/integration/requirements.txt. |
| Panel/browser | PHP 8.2.35 with sockets/mbstring; Chromium 156.0.8078.79; Playwright 1.56.0. |
| Tool image | brewpi-emulator-m4-tools:portable, sha256:7acae435dbf94ea0e016d2073cb6a64dcc92fc81ae12058f5886a8d49807cb6f. |

At the declared 60x phase's sample points, beer/chamber readings changed from 20.125/24.688 C during heating to 20.000/9.688 C during cooling. Those are real host device-readback observations of the model, not measured brewing equipment. The final fresh restart returned beer to 20.000 C while restoring target 18 C, gain 7, and all seven saved assignments. The real host produced 35 CSV rows, the actual chart response contained 33 data rows including heating/cooling states, the panel rendered two chart canvases, and its maintenance log viewer displayed the actual controller identification from the host log.

The reviewed evidence directory is ignored runs/milestone4/review-final: integration-results.json, native-tests.log/native-test-results, helper-checks.log/helper-review-checks.log, launcher-results.json, cleanup-results.json, image-inspect.json, tool-versions/package metadata, wire.jsonl, http.jsonl, reference-code-integrity.json, host/web data, controller state/checkpoint, and browser screenshots. The saved launcher reproduces the fixture in a fresh evidence directory; raw outputs are not embedded in this handoff. Static checks cover 81 project files, 226 local links, eight anchors, and 144 pinned source links, plus helper MIT notices, shell/Python syntax, C++ formatting, whitespace, original production/native-test/fixture/license/history preservation, clean pinned references, unchanged HEAD, and an empty index.

Raw serial/HTTP captures, package/image versions, screenshots, native results, host/web data, and integrity records remain ignored local evidence, with original result summaries distinguished from external client-produced bytes. No capture, panel artwork, or reference implementation is included in tracked test sources.

These checks establish compatibility for the selected host/panel pair in an isolated Linux/browser environment. They do not establish another panel's compatibility, physical Arduino behavior for the nine unresolved characterization cases, native Pi operation, USB reset/discovery/flashing, Bluetooth hardware integration, or release/distribution qualification. No accelerated host-profile equivalence is claimed. Milestone 5, releases, deployment, and further publication remain unapproved.

The original integration tooling, workflow evidence, limitations, fixes, and independent MIT provenance were presented for owner review. The owner subsequently authorized committing and pushing these reviewed milestone 4 artifacts to main. Milestone 5 remains unapproved.
