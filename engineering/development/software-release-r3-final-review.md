# R3 final adversarial review and acceptance

Date: November 15, 2026, America/Chicago. Reviewer: Codex, following the owner's explicit instruction to finish testing, perform an adversarial review, fix issues, commit/push the reviewed R3 work, and verify hosted CI. Original review copyright 2026 Lee Bussy, MIT. Disposition: R3 sustained software qualification is complete for the saved 0.0.1-rc.1 candidate on the declared native ARM64 and x86-64 Linux environments. No blocking emulator issue was found. Release publication, final R4/R5/R6 acceptance, physical Pi peripherals, systemd activation, and nine Arduino characterization cases remain separate.

## Exact scope

The qualified candidate is dist/review-2/brewpi-emulator-rmx-0.0.1-rc.1, original source snapshot 019a7742a8bce8b37a80e61c6f3274046a99eab884f810feea1655cf402cec48, associated with source commit 38769c168428898a39e1c30e94607faf46f2e551 through the [published candidate record](software-release-r4-hosted.md). Candidate manifests are 19fb235540c0a6b932f215ddbf3fed18b64baa2f0790c498df94b5c06c7a5b22 (ARM64) and 74014296b938b6014f5976637d549ba8ea433451b836e7fbf1f701499936212c (amd64). Saved package verification passes; none of its 132 original inputs or packaged binary bytes was changed by R3.

Later main-branch rotary/pushbutton/door controls and other concurrent development are not part of this candidate's sustained qualification. Hosted CI after the R3 documentation/tooling commit tests that exact new main commit; it does not retroactively turn these candidate runs into soaks of later application code. No new application executable is substituted into the accepted evidence.

## Accepted whole workloads

| Native target and workload | Continuous wall duration | Achieved factor | Lifetime / sampled peak RSS, KiB | First / final steady median, KiB |
| --- | --- | --- | --- | --- |
| wspr5 ARM64 normal | 86400.000065433 s | 0.999998497 | 3696 / 3936 | 3936 / 3936 |
| wspr5 ARM64 accelerated | 21600.000058545 s | 59.998975137 | 3632 / 4176 | 4176 / 4176 |
| ubuntu x86-64 original normal | Full 86400 s deadline loop completed; clean process lifetime 86406.641589860 s | 0.999998824, derived from checkpoint/lifetime | 4224 / 4156 | 4152 / 4156 |
| ubuntu x86-64 accelerated | 21600.000094143 s | 59.998577049 | 4352 / 4400 | 4400 / 4400 |

The original x86 normal workload completed successfully before a post-exit reporting heartbeat defect interrupted its worker. Its lost exact observed-duration float is not invented: the retained immutable runner, completed control-flow path, interruption stack, clean child lifetime, complete samples, and host profile history establish the full deadline loop. The [x86 recovery review](software-release-r3-x86-recovery.md) explicitly accepts that completed workload while retaining the overall supervisor failure unchanged. The owner's correction prevented an unnecessary repeat of successful testing. The redundant retry was intentionally stopped with verified cleanup and no partial time counted.

The separate accelerated-only x86 attempt correctly reports partial scope and r3_complete=false. That is not a failure. Its complete six-hour result combines with the independently accepted complete original normal workload and passing clock/fault/lifecycle records. No short runs, interrupted intervals, or pilot durations are stitched together.

Each advertised architecture has eight distinct constructed clock-boundary cases, all eight named host-environment fault cases, and at least 100 lifecycle cycles. Quiescent emulator FD/thread shape remained 8/1; transient ninth FDs during active file operations are not misreported as a leak or as constant instantaneous usage. Same-PID/start-tick trend continuity, successful wait4 lifetime accounting, clean exit, complete steady-hour windows, and original RSS budgets pass. The real-host profiles include disabled/resumed segments and heating/cooling demands. Independent CSV audits cover 8312 ARM and 8294 original x86 temperature rows and all nine scheduled plateaus. Accelerated runs each record six ordered 2000-reply backpressure checks and 19 16-bit-second wraps.

The largest ARM sample gap is below 0.505 seconds; x86 trends pass the same one-second limit, with boot/UTC continuity checked separately. Every accepted final target cleanup reports no remaining owned namespace PIDs. Owned private test directories and evidence remain retained. No service, host account, power, radio, Avahi, or physical-controller setting was changed.

## Adversarial findings and disposition

| Finding | Resolution and evidence impact |
| --- | --- |
| A full-day resource reconciliation could outlive the latency heartbeat's five-second deadline after the emulator had already exited cleanly. | Explicit bounded post-exit validation phase; active-observation heartbeat remains five seconds. Negative regressions distinguish the phases. Recover the completed original workload instead of declaring an emulator failure or repeating 24 hours. |
| A partial accelerated-only result could be misread as complete R3, or a failed overall attempt could obscure its successful completed workload. | Explicit scope propagation and validators reject partial-as-full reports. The combined record cites the recovered normal and complete accelerated attempts separately, with their actual dispositions. |
| Malformed summaries could use non-finite durations/latency maxima or omit the required n sample count. | Require finite positive duration, 30 timing samples, finite ordered median/maximum below the unchanged bound, and consistent distributions when supplied. Non-finite observation clocks, unknown phases, and invalid/future heartbeats are rejected. All accepted saved evidence passes the stricter readers. |
| Exact n function-timer values were summarized rather than retained individually. | Retained final wire traces provide labeled reconstructed distributions; the original maxima/medians remain distinct. Future runner reports include individual timer values directly. No prior exact values are fabricated and no successful soak is repeated for a serialization improvement. |
| Automatic summary validation did not independently rehash the rotated capture tail. | Separate read-only adversarial replay verifies retained segment hashes, byte/record totals, ledgers, final cumulative digests, and raw framing/CP437 behavior. Earlier intentionally rotated bytes are not claimed to be replayable offline. |
| Preliminary records still described ongoing work or old stop-before-commit authorization. | Current status and explicit final authorization now lead the R3 record; historical attempt entries remain identified as history. Provenance and operator guidance describe partial scope, recovery, and candidate-only acceptance. |

The review fixes are independently authored MIT reporting/orchestration changes. They do not alter Arduino responses, candidate code, normative fixtures, accepted thresholds, or the runtime environment of a completed workload. Archived helper maps stay bound to the versions actually executed; current stricter readers and future reporting changes are identified separately. Raw external client material remains private/ignored under its own terms and is not copied into original fixtures or relabeled MIT. See the [R3 provenance record](../licenses/software-release-r3.md).

## Durable evidence and validation

| Whole attempt archive | SHA-256 |
| --- | --- |
| ARM64 acceptance-arm64-20261114T150836Z/completed-attempt-evidence.tar.gz | 253602a98e5cb0b379f9764b60c7c7609c05001654dc33477eba902f058a18bc |
| Original x86 acceptance-amd64-20261114T150902Z/failed-attempt-evidence.tar.gz | 975cb8f27d473b4530f99c7cf8cc3e96dd8a527bb964bb7c888f78b784f3ab2a |
| Scoped x86 acceptance-amd64-20261115T223343Z/completed-attempt-evidence.tar.gz | 096fe000fca0960d7b555d42357fc3c8df2dac1afcaada2132f88bbfc102cfec |

These complete private archives are retained under the owner-controlled ignored runs/r3/stage tree and remain on their targets. Runtime exports/package records, launch/helper maps, payload receipts, full resource samples/lifetime reports, and cleanup records were reconciled locally. Derived receipts and original read-only audit scripts are under runs/r3/reconciliation; combined-review.json binds the original normal candidate receipt to the same x86 candidate used by the six-hour run. The [ARM review](software-release-r3-arm-review.md) and [overall record](software-release-r3.md) preserve additional details and earlier attempts.

Local validation includes 13 original helper regression methods with additional negative cases, complete saved-evidence replay on both architectures, original specification/link/provenance checks, and saved package verification. The pinned workflow linter is Linux-only; attempting it on macOS produced an executable-format error; the pinned linter then passed on native x86 Linux. Hosted CI must still be recorded against the delivered commit and exact run attempt; no local result, earlier branch run, or skipped job is substituted. The current CI helper lane covers its existing helper inventory; R3-specific reader regressions are additionally run locally and on native x86, rather than claimed as an unconfigured hosted lane.
