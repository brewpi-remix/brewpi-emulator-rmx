# Provisional R4 local review record

The owner subsequently authorized R4 source publication and hosted CI verification. The [publication record](software-release-r4-hosted.md) owns the exact commit association and hosted results; the review-time dispositions below remain historical. R3 remains unstarted.

## Current reviewed local candidate

Date: November 14, 2026. Reviewer: Codex (automated technical review); owner review remains pending. The owner authorized fixes while preserving 0.0.1-rc.1, Arduino behavior, and independent MIT licensing, without R3, commits, or pushes. This section supersedes the initial preparation disposition retained below.

The reviewed saved copy at dist/review-2/brewpi-emulator-rmx-0.0.1-rc.1 is separate from the unchanged initial saved copy. The source snapshot is 019a7742a8bce8b37a80e61c6f3274046a99eab884f810feea1655cf402cec48, based on 1d36d857ee572185aa60f83be2a6cb5968511213, with source_commit null and reviewed commit association pending. All 132 packaged original inputs match the current working files; this archive-hash working record remains outside the source allowlist to avoid self-reference. The owner's explicit version-preserving instruction applies to this unaccepted local review only; accepted/public artifacts are never replaced. The [policy](software-release-policy.md) and [package guide](../../docs/release.md) record that distinction.

| Review finding | Fix |
| --- | --- |
| Doubled slashes and file/parent-directory conflicts could be accepted or fail only after partial extraction. | Require canonical member names, reject conflicting paths before writes, and check source-derived timestamps when reconciling archives. |
| Payload receipts checked file bytes without enforcing installed modes, and special files could escape enumeration. | Enforce schema 2 modes at each payload verification, reject links/special files, and validate source metadata/file modes. Saved-set validation rejects nonregular members before attempting reads. |
| Snapshot and baseline fields were not fully reconciled across the source, payload, build, and saved-set sidecars. | Compare baseline/snapshot roles and target metadata, inspect extracted inventories, reconcile archive/build/source hashes and package inputs, and retain explicit unsigned/provisional flags. |
| Commit and snapshot expectations could be mixed, permitting a commit-based manifest without an independently expected commit. | Require an exact commit expectation for schema 1 and an exact snapshot expectation for schema 2, reject mixed modes, and add positive/negative cross-schema regressions. |
| Saving trusted the earlier reproducibility summary without rechecking both build roots. | Retain actual CTest XML; recheck both independent roots, all six suite statuses, 48/9 fixture classifications, matching package records, and exact external-notice inventories before saving. |
| Clean-runtime receipts and package records were incompletely bound to their launcher. | Require exact process-start phase, execution mode, version, architecture, source identity, payload map, runtime package-input hashes, image identity, successful exit, and verified cleanup. |
| Packaging regressions were manual-only, and documentation understated the pre-R3 commit gate. | Add release/checks.py to existing CI helper/macOS receipts, update completion proof sizing, require reviewed commit association before starting R3, document exact image tags/provisioning commands, distinguish sidecars from payloads, and list remaining tool-floor/native gates. |

The shared review record also linked to ignored local output directories, which could pass link checks locally and fail in clean CI. Artifact locations are now plain local paths/commands. A separate clean-checkout link audit confirms that every local Markdown target belongs to original source inputs rather than generated output.

| Current validation | Result and scope |
| --- | --- |
| Source/package reproducibility | Two fresh differently located builds per architecture passed; source and binary archives/manifests match within each pinned environment. All four builds passed six suites, with 48 source-defined cases and nine unresolved characterization obligations. |
| Clean packaged runtime | Nine checks passed per architecture with exact payload identity and verified cleanup; native ARM64 and emulated amd64 remain explicitly distinct. No compiler/build tools were available in these runtime guests. |
| Native ARM64 host/panel | All 17 packaged workflows passed, including original/reference integrity, browser cleanup, payload restarts, and container removal. |
| Native ARM64 qualification | Release and ASan/UBSan six-suite runs, nine packaged runtime checks, inert staging/service syntax and explicit unit-command checks, and foreign-account isolation passed. No systemd PID 1 activation is claimed. |
| Native ARM64 tool floors | CMake 3.16.9 and Python 3.9.25 passed the extracted candidate source's six suites offline, without Git/reference checkouts. The separate launcher binds the source snapshot/archive and existing floor-image identity. |
| Original helper regressions | 13 integration, seven qualification-launcher, six readiness, 23 CI, and 12 packaging tests passed through the updated helper entry point on macOS. No new hosted CI execution is claimed. |
| Negative gates and static checks | Malformed/ambiguous paths, timestamps, special files, mode changes, changed/missing/failed second builds, disabled assertions, and inconsistent source identities were rejected. A copied candidate with an incorrect build architecture was rejected even after its outer checksums were refreshed. Static metadata/provenance/pinned-source/link checks and whitespace checks passed. |

| Reviewed archive | SHA-256 |
| --- | --- |
| brewpi-emulator-rmx-0.0.1-rc.1-source.tar.gz | 9b5f4eb487320f0e108cdc37ba7607b8597c45227af6a843b607110cdb9dff51 |
| brewpi-emulator-rmx-0.0.1-rc.1-linux-arm64.tar.gz | ba8bf5c3d78ea9e96ad91f4633bb7a73253ce8f27cd2b2726c96cfb074082b82 |
| brewpi-emulator-rmx-0.0.1-rc.1-linux-amd64.tar.gz | e3e2bce6695401a2484e5c2bb401692dfd62919e5b3c01847a37f7eef09f9837 |

Both binary archives are byte-for-byte identical to the initial saved packages. The revised source archive and source-bound manifests have new identities because the packaging/validation/docs changed. There is no additional production C++ change in this review. Application version, serial firmware identity, controller/transport/storage behavior, normative fixtures, and root MIT license remain unchanged. Independently authored helpers and regressions remain MIT; no BrewPi/Fuscus implementation, translated test, asset, or third-party dependency is introduced. External GNU package notices remain separately attributed sidecars; [preliminary provenance](../licenses/software-release-r4.md) does not claim final R5 distribution acceptance.

Accepted local review evidence is under runs/r4/review-1/attempt-3. Earlier review preparations are retained: attempt-1 predates the final source-baseline gate, and attempt-2 predates the final cross-schema expectation gate. The intermediate dist/review-1 copy and the initial saved copy are retained unchanged; neither source identity substitutes for the final reviewed copy. All three saved sets passed the stronger verifier. Run python3 release/local.py verify dist/review-2/brewpi-emulator-rmx-0.0.1-rc.1 to check the final reviewed copy again.

This provisional review is complete and stops for owner review. Remaining gates include exact reviewed commit association and corresponding hosted source checks, native amd64 minimum-tool and complete packaged workflows, R3 sustained tests, final R4/R5 acceptance, and R6 handoff. Physical Pi qualification, systemd activation, and the nine Arduino characterization cases remain outside this software evidence. No commit, push, tag, upload, reference modification, host service activation, or R3 work was performed.

## Initial preparation (retained history)

Date: November 14, 2026. This record covers packaging 0.0.1-rc.1 for later R3 qualification. “Saved candidate” means retained package bytes and checksums that let subsequent results identify what was tested; the repository remains editable. No commit, push, tag, publication, R3 workload, physical Pi qualification, systemd activation on the host, or Arduino characterization is authorized or claimed here.

### Source and licensing

The baseline is 1d36d857ee572185aa60f83be2a6cb5968511213. The candidate contains uncommitted original R4 inputs, so source_commit is null rather than misidentifying the baseline as the candidate commit. SOURCE.json binds all 132 explicitly allowlisted original files, their modes, and hashes to snapshot 31abe4d216e460745d9ffb23c20aa00c323251225dd4b116c0bb7ccb071ccb8a. The source archive adds only that generated identity record. Reviewed commit association remains pending owner review and later authorization.

Original version metadata, packaging helpers, recipes, regression cases, and supporting prose are independently authored MIT work. No BrewPi/Fuscus implementation, translated tests, assets, or generated tables are incorporated. Root LICENSE.md, HANDOFF.md, SETUP.md, and normative protocol JSON remain unchanged. The only production C++ change is --version reporting brewpi-emulator-rmx 0.0.1-rc.1; serial firmware identity and Arduino behavior remain unchanged. See the [preliminary provenance record](../licenses/software-release-r4.md) and [package guide](../../docs/release.md).

The six-file binary inventory contains the executable, readiness helper, inert service example, MIT license, notices, and standalone operating guidance. It bundles no shared libraries or host/panel files. Actual compiler/runtime package inventories, downloaded package hashes, and separately attributed Debian copyright notices accompany the archives as sidecars; they are external material under their own terms. Preliminary notices recognize compiler startup/template contributions and external GNU dependencies. R5 actual-archive/component/license acceptance remains pending.

### Deterministic construction

Pinned Debian 12 base and dated snapshot recipes produce recorded architecture-specific build/runtime image identities. GCC 12.2.0 and GNU ld 2.40 compile generic armv8-a and x86-64 code without native CPU tuning. Archive ordering, owners, modes, timestamps, locale, timezone, and source/build path mappings are fixed. Two fresh containers and differently located build roots per architecture produced identical source archives, binary archives, deterministic manifests, and package input records. No executable rewriting occurs after hashing.

| Archive | SHA-256 |
| --- | --- |
| brewpi-emulator-rmx-0.0.1-rc.1-source.tar.gz | 328cc44f74ad48710d3f7bad313b715616132bf4183d87db39c154a75d5658e9 |
| brewpi-emulator-rmx-0.0.1-rc.1-linux-arm64.tar.gz | ba8bf5c3d78ea9e96ad91f4633bb7a73253ce8f27cd2b2726c96cfb074082b82 |
| brewpi-emulator-rmx-0.0.1-rc.1-linux-amd64.tar.gz | e3e2bce6695401a2484e5c2bb401692dfd62919e5b3c01847a37f7eef09f9837 |

Both executables require only libc.so.6, libgcc_s.so.1, libm.so.6, and libstdc++.so.6, with no RPATH/RUNPATH. Maximum observed version requirements are GLIBC_2.34, GLIBCXX_3.4.29, and CXXABI_1.3.9. Interpreters are /lib/ld-linux-aarch64.so.1 and /lib64/ld-linux-x86-64.so.2. These inspected requirements do not qualify arbitrary older distributions.

### Validation and evidence boundaries

All four extracted-source Release builds passed all six native suites, including 48 source-defined fixtures; all nine reference-characterization obligations remain unresolved. The macOS ARM64 ASan/UBSan source build also passed six suites with the same classifications. Clean runtime guests on both architectures passed all nine existing runtime checks against the exact extracted executable/helper with networking disabled, an unprivileged account, a read-only root, and compiler/linker/build tools absent. Container cleanup and input identities were verified. ARM64 Linux execution is native; amd64 Linux execution uses emulation on the ARM64 Docker VM and is supplemental evidence only.

Original packaging regressions passed five tests, including unsafe archive members, duplicate/missing/substituted inventory, snapshot tampering, and commit/snapshot identity confusion. Existing CI, integration launcher, qualification launcher, and readiness regressions passed 23, 13, seven, and six tests, respectively. Static source/provenance/document checks passed. An obsolete clean-runtime report was refused before saving a candidate, and an existing destination was refused without replacement.

Native ARM64 packaged host/panel validation passed all 17 planned workflows, including browser controls, host serial behavior, persistence quirks, evolving temperatures/control states, restart recovery, logging, and browser rendering. Packaged qualification passed Release and sanitizer suites, all nine runtime checks, service syntax and explicit unit-command checks, and foreign-account isolation; systemd PID 1 activation remains unqualified. Both launchers verified exact payload identity and container cleanup. Raw captures, nondeterministic observations, detailed logs, and setup attempts remain in ignored runs/r4 rather than entering the reproducible source archive. This original working record deliberately stays outside the source allowlist because including an archive-hash report in that archive would create a self-reference.

### Pending acceptance

Owner review, exact reviewed commit association, native amd64 packaged client/qualification, R3 sustained workloads, final R4 completion, R5 audit, and R6 handoff remain pending. Local checksums provide content identification, not a signature or authenticity guarantee. Neither published release acceptance nor physical hardware qualification is implied.

### Saved candidate and review disposition

The local candidate directory dist/brewpi-emulator-rmx-0.0.1-rc.1 contains the three archives, source/payload/build/environment manifests, exact package inventories and separately attributed notice sidecars, and detached SHA256SUMS. The saved set is read-only as an accidental-edit precaution. Its verification succeeded; negative checks on a disposable copy rejected changed archive bytes and an unexpected file. A repeated save refused the existing destination and preserved its bytes. Nothing in this mechanism locks or prevents editing the repository. Changes to packages require fresh validation and candidate identification under the reviewed release policy.

Detailed accepted local preparation evidence is under runs/r4/attempt-3, with clean-runtime-arm64, clean-runtime-amd64, packaged-integration-arm64, and packaged-qualification-arm64 records. Earlier preparation attempts are retained: attempt 1 exercised runtime checks but its report-copy step failed, and attempt 2 preceded the final notice/orchestration/input-binding updates. Neither is the saved candidate or a substitute for attempt 3 evidence. Their checks do not count as acceptance of different package hashes.

Provisional local R4 preparation is complete and awaits owner review. The source identity is a snapshot of uncommitted inputs, not a reviewed candidate Git commit. Native amd64 complete package qualification, R3, and final release acceptance remain open. No Git objects, index entries, commits, pushes, public artifacts, services, or reference checkouts were changed by the save.
