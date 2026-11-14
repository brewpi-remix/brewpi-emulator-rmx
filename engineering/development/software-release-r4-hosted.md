# R4 source publication and hosted CI

Date: November 14, 2026. The owner authorized committing/pushing the reviewed provisional R4 tooling, validation fixes, tests, and supporting docs to main, followed by hosted CI verification. Preserve 0.0.1-rc.1, Arduino action/reaction, and independent MIT licensing. R3, release/tag creation, package uploads, service activation, physical Pi qualification, Arduino characterization, and repository-rule activation remain excluded.

## Published source and saved candidate association

The reviewed implementation was published as [38769c168428898a39e1c30e94607faf46f2e551](https://github.com/brewpi-remix/brewpi-emulator-rmx/commit/38769c168428898a39e1c30e94607faf46f2e551). Every one of the 132 original allowlisted files was compared directly with committed Git blob contents and executable modes. All match source snapshot 019a7742a8bce8b37a80e61c6f3274046a99eab884f810feea1655cf402cec48, originally prepared against baseline 1d36d857ee572185aa60f83be2a6cb5968511213. The original comparison receipt is retained under ignored runs/r4/publication/candidate-commit-association.json.

The saved review copy remains at dist/review-2/brewpi-emulator-rmx-0.0.1-rc.1. Its source archive hash remains 9b5f4eb487320f0e108cdc37ba7607b8597c45227af6a843b607110cdb9dff51; the ARM64 and amd64 archive hashes remain ba8bf5c3d78ea9e96ad91f4633bb7a73253ce8f27cd2b2726c96cfb074082b82 and e3e2bce6695401a2484e5c2bb401692dfd62919e5b3c01847a37f7eef09f9837. No saved archive, manifest, notice sidecar, or checksum was rewritten. SOURCE.json continues to describe its original precommit snapshot honestly; this separate association supplies the exact matching published commit rather than changing that metadata in place. Reproduce those saved bytes from the retained source archive and declared inputs; creating a new snapshot at a later Git HEAD creates different source metadata.

The [local R4 record](software-release-r4.md) owns the review-time results and history. This publication record and the archive-hash working record stay outside the saved source allowlist. Documentation-only publication records can therefore be committed without changing the 132 archived inputs or regenerating candidate bytes. Historical review-stop instructions in those archived inputs remain snapshots of their authorization; the owner's later explicit R4 publication instruction governs this commit/push/CI task.

## Hosted verification

All nine required contexts passed for the exact published source in [run 43601055552](https://github.com/brewpi-remix/brewpi-emulator-rmx/actions/runs/43601055552), attempt 1:

| Context | Result |
| --- | --- |
| specification | Passed |
| helper-regressions | Passed |
| linux-amd64-release | Passed |
| linux-amd64-sanitizers | Passed |
| linux-arm64-release | Passed |
| linux-arm64-sanitizers | Passed |
| macos-arm64-development | Passed |
| host-panel-arm64 | Passed |
| pr-validation | Passed |

Downloaded original summaries were reconciled with completed job results, GitHub Actions check-run producers, exact source commit/workflow revision, canonical source-input fingerprint, run ID, attempt, and artifact identities. The source fingerprint is 39e7ac8afb5ae4acc4192cff9584d1606b9c6be6c44a686283b47e376e86a2e9. Native machine/system proofs, Linux owned-container cleanup, all six suite names, 48 source-defined passes, nine unresolved characterization obligations, complete helper proofs, and the final completion summary were verified. No partial, skipped, stale, or mixed-attempt result was accepted.

The helper lanes include all 61 original regressions: 13 integration, seven qualification-launcher, six readiness, 23 CI, and 12 packaging checks. Both native Linux Release lanes additionally passed offline CMake 3.16.9/Python 3.9.25 source checks; the pinned ARM64 source host/panel workflow passed all 17 cases. These hosted source results supplement the separate exact-package evidence without relabeling local emulated amd64 package execution as native qualification.

Original receipts, their SHA256 values, run/job/check/artifact metadata, and the verification result are retained under ignored runs/r4/publication/43601055552/attempt-1 before the seven-day hosted summary retention expires. This document records that exact tested source. Its documentation-only publication successor must receive its own complete workflow run; it does not inherit or replace the recorded source/run identity. The final branch-head verification is retained separately in the same local publication evidence area.


## Preserved boundaries

Original source, helpers, tests, and documentation remain independently authored MIT work; root LICENSE.md and normative protocol fixtures are unchanged. The reviewed local binary archives are byte-identical to the earlier saved copies. External compiler/runtime/package notices retain their own terms in local sidecars and are not published as original MIT content. The only production C++ change remains the previously reviewed application --version presentation; firmware identity and behavior are preserved.

Hosted CI verifies native Linux source suites on amd64 and ARM64, native macOS development checks, original helper/specification gates, and the pinned ARM64 host/panel source workflow. It does not qualify the exact shipped amd64 package, physical hardware, live services, R3 sustained workloads, final R5 distribution acceptance, or R6 handoff. Local emulated package results remain labeled as emulated. No package/tag/release upload or R3 workload is authorized by source publication.
