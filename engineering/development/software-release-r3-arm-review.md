# ARM64 R3 evidence review

Reviewed November 15, 2026 by Codex under the owner's instruction to review the completed ARM evidence. This original review is copyright 2026 Lee Bussy under the root MIT license. Disposition: the ARM64 evidence supports its declared R3 software qualification; no blocking inconsistency was found. This ARM-only review preceded x86 completion; the [final review](software-release-r3-final-review.md) now records combined R3 acceptance. This is neither release approval nor authorization to commit or push.

## Inputs and execution identity

Reviewed attempt: wspr5 acceptance-arm64-20261114T150836Z. The retained complete evidence archive has SHA-256 253602a98e5cb0b379f9764b60c7c7609c05001654dc33477eba902f058a18bc. Local candidate manifest SHA-256 is 19fb235540c0a6b932f215ddbf3fed18b64baa2f0790c498df94b5c06c7a5b22. Its unchanged source snapshot 019a7742a8bce8b37a80e61c6f3274046a99eab884f810feea1655cf402cec48 is associated with source commit 38769c168428898a39e1c30e94607faf46f2e551 through the [published candidate record](software-release-r4-hosted.md). The saved candidate verifier passed again during this review.

The environment receipt identifies native aarch64, Debian 12 userland, host kernel 6.18.60+rpt-rpi-2712, UID 2001, and affinity CPU 3. Exact runtime export/package records, candidate execution receipts, archived harness inputs, and the three test-only tool hashes reconciled locally. The archived ARM harness matches its own launch and passing pilot; it is intentionally not relabeled as the later x86 watchdog correction. Its log records 12 Python regressions and two native supervisor checks, whereas the corrected x86 helper set has 13 Python regressions. These are separate, preserved execution identities.

## Rechecked gates

| Gate | Independently reviewed evidence | Disposition |
| --- | --- | --- |
| Full durations and pacing | Normal 86400.000065433 wall seconds at factor 0.999998497; accelerated 21600.000058545 at factor 59.998975137. One uninterrupted emulator identity per workload. | Pass |
| Sample continuity | 172775 normal and 43200 accelerated samples; largest monotonic gaps 0.504622 and 0.503786 seconds. Boot/UTC gaps agree, and no suspension-sized drift appeared. | Pass |
| Complete-lifetime and sampled RSS | Normal wait4/sample peaks 3696/3936 KiB; accelerated 3632/4176 KiB. Both accounting methods remain separately reported and below 131072 KiB. | Pass |
| Steady-hour growth | Normal first/final medians 3936/3936 KiB; accelerated 4176/4176 KiB. Complete windows follow the fixed 1800-second warm-up. | Pass |
| Lifecycle recovery | 100 sequential cycles with quiescent emulator shape 8 FDs and 1 thread; checkpoint-resume equality, fresh-store reload, client reopen, and periodic forced-stop/stale-link cases are asserted by the preserved original runner. | Pass |
| Clock and host-environment faults | Eight distinct constructed boundary cases and all eight named corruption, mismatch, alias, and pre/post-replacement fsync cases. No physical power-loss durability claim. | Pass |
| Real-host profile history | Fixed CSV points match the original schedule; all 8312 logged temperature replies reconcile to host CSV row count. Nine plateau intervals, including disabled and resumed segments, match the declared targets outside the fixed transition grace. | Pass |
| Protocol capture retention | All three capture ledgers reconcile counts, byte totals, segment numbering, and final cumulative digests. Every retained segment matches its own hash and record count; retained framing, identity, and raw CP437 LCD validation pass. | Pass within planned rotation scope |
| Latency and pressure | Thirty measured n queries per workload have recorded maxima below 0.000252 seconds; incomplete-token waits are 1.006936/1.007205 seconds. All final 30 request/reply trace intervals were independently reconstructed. Six ordered 2000-reply backpressure checks and 19 accelerated 16-bit-second wraps are recorded. | Pass, with timing-retention limitation below |
| Cleanup | Successful target supervisor and independent validator; no remaining owned namespace PIDs. Both child lifetime reports show clean exit and no interruption. | Pass |

The ordinary resource samples sometimes show a ninth FD during active work; that is not a quiescent-cycle growth result. Every matched lifecycle quiescent sample remained at eight FDs, all resource thread observations stayed at one, and final cleanup passed. Do not describe every instantaneous FD count as constant.

## Evidence limits and corrected reporting

The planned ring rotated one of nine normal host-capture segments and 48 of 56 accelerated capture segments. Those earlier raw bytes cannot be replayed offline. Their validated online counters/digests and complete segment ledgers remain preserved, while all retained segments were rehashed and replayed. This matches the permitted [R3 rotation policy](software-release-plan.md); the review does not claim a full raw-byte offline replay. Complete external host CSV/log history additionally supports the normal profile checks, including the early disabled/resumed interval whose serial segment was rotated.

The runner saved the n timing count, maximum, and median, but not each exact timed call value. All 30 final request/reply trace intervals per workload remain available and were reconstructed in the local review receipt. They supply a retained wire-trace distribution, not invented replacements for the original function-timer samples. There were no recorded over-bound queries. Future reporting should retain the individual timer values directly; this record makes the limitation explicit instead of claiming those exact values were saved.

Peak wait4 values need not numerically dominate independently sampled mapping RSS on this Linux environment. Both methods were retained and separately checked against the unchanged budget, and steady growth uses the mapping samples consistently. This review does not replace the original measurements or relax thresholds.

Raw external host/panel material remains private and ignored under its own terms; it was not copied into original fixtures or relicensed as MIT. The review script and derived audit summaries are independently authored. Candidate bytes, firmware behavior, normative fixtures, and original licensing inputs remain unchanged. Physical Pi peripherals, systemd activation, nine Arduino characterization cases, and x86 completion remain outside this ARM result.

The retained original review script and machine-readable receipt are runs/r3/reconciliation/arm64/review/audit.py and audit.json. The earlier complete local reconciliation receipt is runs/r3/reconciliation/arm64/local-validation.json. They are ignored evidence, not candidate payload files. The [overall R3 record](software-release-r3.md) retains the separate attempt dispositions and ongoing x86 status.
