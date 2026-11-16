# Current candidate controls integration results

Date: November 16, 2026. Original documentation copyright 2026 Lee Bussy, MIT. The owner's requested current-main LCD/rotary/pushbutton/door changes are included in a separately saved, unpublished 0.0.1-rc.1 candidate. This record completes the [integration assessment](candidate-controls-integration.md), whose snapshot-time status remains historical. No commit, push, tag, public release, host installation, service activation, physical peripheral qualification, or Arduino characterization was performed for this integration.

## Saved inputs and packages

The new local directory is dist/controls-review/brewpi-emulator-rmx-0.0.1-rc.1. Its source snapshot is 2863ed4820348ed92c9c167ad9b223eccbfc4b08341cdb654065a3e0440f2823, based on b809614bceb2d47dc4eab3a37af5ace6b8a0b0f3 with uncommitted original packaging/test/documentation changes. It is not a reviewed candidate commit. SOURCE.json and the source/payload/build manifests retain that distinction. This results record was written after construction and is outside the archived source's explicit 183-file allowlist.

| Archive | SHA-256 |
| --- | --- |
| brewpi-emulator-rmx-0.0.1-rc.1-source.tar.gz | 74ef1fad64a368d6837294189a134579e25a8e08988684c36096bc472b03e6e1 |
| brewpi-emulator-rmx-0.0.1-rc.1-linux-arm64.tar.gz | 1295e5767344a1be5a3790dc4f515c2885fb532a5bfb42fb8814c91acc056999 |
| brewpi-emulator-rmx-0.0.1-rc.1-linux-amd64.tar.gz | 124a75f63538c78de013a0134a07a9e28318b6881c38e27b760e80d651e1cd05 |

Both binary manifests explicitly select local-controls-v1: the original six project files plus libexec/brewpi-emulator-rmx/lcd-viewer.py, with exact hashes and modes. The default CMake install remains the six-file core layout. The previous dist/review-2/brewpi-emulator-rmx-0.0.1-rc.1 remains unchanged and passes the existing saved-set verifier. Both saved sets have been verified; no earlier archive was overwritten.

## Completed validation

- Two independent build roots per architecture produced identical archives and manifests, with all six source CTest suites passing in each root and all 48 source-defined fixtures passing. The nine reference-characterization cases remain explicitly unresolved. Docker ARM64 execution was native Linux; local Docker amd64 execution was emulated and is labeled accordingly.
- Both final clean-runtime packages passed all nine operating checks without compilers/build tools. The final ARM64 packaged host/panel run passed all 17 workflows; the packaged operating qualification passed Release and sanitizer suites, runtime checks, inert unit syntax, and isolated unit-command lifecycle checks. Owned containers were removed. This does not claim systemd PID 1 activation.
- Native ARM64 on wspr5 and native x86-64 on ubuntu passed model, dynamics, pacing, fixtures, edges, transport/controls, and terminal dimming checks. The actual packaged executables were selected for process/transport checks. The installed viewer was discovered under libexec, invoked with the existing isolated-Python argument, and verified by hash; the private headless environments correctly fell back to the terminal and continued answering the protocol. These runs do not claim a graphical desktop test. Existing [GUI/controls review evidence](rotary-controls-review.md) remains applicable to the unchanged viewer source.
- Each native target completed a separate 300-second 1x run and 300-second 60x run with seven configured devices, protocol polling, a target change during accelerated execution, raw process samples, lifetime resource records, and verified namespace cleanup. Observed rates were approximately 0.999x/59.934x on ARM64 and 0.999x/59.905x on x86-64. Peak sampled RSS was below 4.3 MiB. These checks passed the short-check resource thresholds; they do not establish a new steady-hour memory trend or replace a long soak.
- Original packaging regressions passed 15 tests, CI helper regressions passed 23 tests, and qualification helper regressions passed six tests. Specification/link validation passed with 48 source-defined and nine unresolved cases, and whitespace validation passed.

The packaged executable hashes are e5072a1daa2f8bd81277bd64735861a9d73e4d2611cc2301e2f14fa48a9a758a (ARM64) and 47d2c661281fe7e1d0883cece47167040f96421cc2cf28fad20ef923a432c118 (amd64). They exactly match the native Release executable receipts from main's already successful hosted run 43806919359, attempt 1, at b809614. This is existing exact-binary CI evidence, not a claim that the uncommitted packaging helpers have a new hosted run.

## Evidence identities and reporting fixes

Local evidence is retained under runs/release-controls-20261116. Final packaging/workflow inputs are attempt2. Native controls checks executed the earlier attempt1 source snapshot a594870b1671c0dfd4c7d725ecf952e5d2239c1003af42dcfc1f86edb4a214e1. All seven installed file hashes/modes, both binary archives, and every production source file are identical between attempts; payload-equivalence.json records that comparison. Attempt2 corrects test/reporting helpers and documentation, and its complete packaged workflows passed using the corrected reader. No native run has been relabeled with the later source snapshot.

The first integration launch used an unrelated mutable local tool tag and failed before running the application; the retry used the recorded correct tool image. The first qualification body passed but its six-file evidence reader rejected the declared seventh file. The reader now uses the explicit profile, with a regression test, and the final end-to-end qualification passed. Early native harness attempts lacked the private generic controlling terminal or expected the wrong interpreter argument position; their failures and cleanup receipts remain retained. Correcting those test assumptions required no production-code changes. Seven already-passing native checks were retained from each prior attempt with matching input identities and original logs; only helper discovery and the outstanding short workloads were subsequently executed.

| Native evidence archive | SHA-256 |
| --- | --- |
| native-arm64-accepted/evidence.tar.gz | 4dba51b8d2165c1b24194f691c9e3fd11ef521ad95e6c7b2b451e164590c92c5 |
| native-amd64-accepted/evidence.tar.gz | b9bfebc7f598365b7fb6777fefbf4e0ca199c82d6b0d3e774c669d5df0d12c31 |

Each local native evidence directory also retains prior-checks.tar.gz and its checksum. The final raw samples/lifetime records were independently reread from the collected archives and resource calculations reproduced successfully. Raw external-client captures, external tools, and local qualification evidence remain ignored and outside the MIT source/package payloads.

## Carry-forward and review boundary

The [completed R3 assessment](software-release-r3-final-review.md) retains its original whole 24-hour/1x and six-hour/60x workload identities for each native architecture. As assessed in the integration plan, the core dynamics, storage, and JSON sources are unchanged; optional controls add bounded local interaction through existing settings/persistence/door paths and transient menu cancellation. Under the owner's current instruction, that earlier long-duration evidence is carried forward for the unchanged core, supplemented by the controls suites, exact-binary CI evidence, and the actual-package checks above. No fresh 30-hour test of the revised binary hashes is claimed or automatically required solely because their identities changed.

All added packaging/tests/helper integration remain independently authored MIT work, with contributor/SPDX notices retained and no BrewPi/Fuscus implementation reuse. The viewer bundles no font, graphical asset, Python runtime, or Tcl/Tk runtime. External compiler/runtime contributions retain their terms and separately attributed sidecars; the [provenance gate](../licenses/README.md#review-gate) and final actual-archive component/license review remain applicable. The earlier six-file provenance record describes its historical artifacts; this record explicitly accounts for the newly included original seventh helper.

The local revision is ready for owner review. Reviewed-commit association, final R4/R5/R6 acceptance, and any later authorized hosted checks/publication remain separate from saving this candidate. The saved provisional metadata conservatively lists release gates; it is not the authority for discarding completed evidence. Physical Pi qualification, systemd activation, and the nine Arduino characterization cases remain separate and were not performed here. Arduino wire behavior and the application version are unchanged by these packaging/validation fixes.
