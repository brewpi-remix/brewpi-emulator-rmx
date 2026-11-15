# Original regression entry points

These files are independently authored original MIT material, copyright 2026 Lee Bussy, including references.json and the package-input schema defined in payload.py. They contain interoperability revisions and input hashes, not reference implementation code. See the [R2 execution record](../../engineering/development/software-release-r2.md) and [provenance inventory](../../engineering/licenses/software-release-r2.md). Source-build and packaged-input evidence have separate meanings; neither locally manufactures a hosted-CI result.

## Local checks

Run from the repository root with assertions enabled. Every native output directory must be new. Both normal and sanitizer builds execute all six named suites and preserve 48 source-defined passing cases and nine unresolved characterization obligations. Existing CMake build directories remain usable through their documented commands; this runner intentionally reserves a new directory to reject stale results.

```sh
python3 tests/specification.py
python3 tests/integration/checks.py
python3 tests/qualification/launcher_checks.py
python3 tests/qualification/checks.py
python3 tests/ci/checks.py
python3 release/checks.py
python3 tests/ci/native.py build-r2-local debug
python3 tests/ci/native.py build-r2-local-sanitize sanitize
```

The specification checker requires Git and all six reviewed clean sibling reference repositories. The reference provisioner is for clean disposable CI workspaces; it fetches exact reviewed commits outside the original source tree and refuses existing modified/wrong revisions. It does not update the owner's prepared references. The native CMake/CTest runner needs neither Git nor reference repositories, and it uses CTest from the build directory to support CMake 3.16.

## Isolated Linux setup

Image provisioning may download tools. Actual tests use network none, read-only source/client mounts, private temporary state, and owned-container cleanup. Docker access is required on the host; no Docker socket, physical device, or privileged mode is passed into a guest. These are disposable root-provisioned test guests, with unprivileged runtime checks where declared, rather than rootless isolation. Never point these commands at live BrewPi state.

```sh
docker build -t brewpi-emulator-ci:r2 -f tests/ci/Dockerfile tests/ci
docker build -t brewpi-emulator-r2-tools:locked -f tests/integration/Dockerfile tests/integration
RMX_INTEGRATION_IMAGE=brewpi-emulator-r2-tools:locked RMX_INTEGRATION_SKIP_BUILD=1 bash tests/integration/run-isolated.sh ../brewpi-script-rmx ../brewpi-www-rmx runs/r2/new-source-integration
RMX_QUALIFICATION_IMAGE=brewpi-emulator-r2-tools:locked bash tests/qualification/run-isolated.sh runs/r2/new-source-qualification
```

Qualification defaults to ARM64, preserving the owner's selected milestone 5 target. Use RMX_TARGET_ARCH=amd64 only on an actual native amd64 host with an amd64 image; image architecture, guest machine, ELF machine, and library inspection must match. The CI wrapper independently requires host/guest agreement; emulation is not a native qualification. All output directories must be new.

## Controlled packaged-input checks

Supply an already extracted original six-file install prefix tree. Do not put the manifest inside the payload tree. Schema 1 requires candidate_version (0.0.1-rc.1), source_commit (40 lowercase hex digits), architecture (amd64 or arm64), install_prefix (/usr/local for planned releases, or /opt/brewpi-emulator-rmx for the existing qualification fixture), application_version_output (the full exact --version output), and files (the six relative installed paths mapped to SHA256 values). The expected source commit must also be supplied independently through RMX_CANDIDATE_COMMIT. The payload is never repaired or rebuilt as a fallback. Separate source-native tests still build to validate the independent driver; their binaries are not selected for packaged process workflows.

For an R2 fixture only, configure/build a Linux Release tree with CMAKE_INSTALL_PREFIX=/usr/local, stage it using DESTDIR, then invoke the helper inside that same native Linux environment. Substitute the reviewed exact source commit and new local staging/output paths in these commands. The helper records an explicit fixture-only purpose and the current development application's version; this is not R4 candidate creation or acceptance.

```sh
DESTDIR=/output/stage cmake --install /output/release
python3 /work/tests/ci/package_fixture.py /output/stage/usr/local /output/manifest.json --source-commit EXACT_SOURCE_COMMIT
```

On the host, export RMX_EXECUTION_MODE=packaged-input, RMX_PAYLOAD_ROOT to the extracted prefix tree, RMX_PAYLOAD_MANIFEST to its separate manifest file, and RMX_CANDIDATE_COMMIT to the independently expected exact source commit. Then invoke the normal integration or qualification launcher with new evidence paths and the provisioned image. The launchers mount payload/manifest read-only and forward their identities. Qualification uses the manifest's install prefix and exact helper/unit/runbook/license/notices, while integration uses the chosen executable for all real host/panel restarts. Hashes are checked before and after runtime and on restarts. Missing inputs, version/architecture/hash mismatch, extra files, symlinks, or altered bytes fail.

## Minimum tools and hosted execution

Build floor.Dockerfile with BASE pointing to the prepared CI image. Its external CMake 3.16.9 and Python 3.9.25 sources use fixed official URLs and SHA256 hashes. Run tests/ci/offline.py in that image with network none and a fresh writable output path. It copies the original source inventory without Git/references and runs all six suites using the actual floor tools. Linux CI Release lanes perform this automatically on their native architecture.

The workflow's eight execution receipts are emitted only after successful checks. The ninth pr-validation job runs after failed dependencies too and requires successful named proofs bound to this source, workflow, run, and attempt. It rejects skipped, neutral, cancelled, failed, missing, stale, or incomplete results. Original summary JSON alone is uploaded for seven days; detailed external/raw evidence remains local/disposable. Source fingerprints and unsigned execution receipts are not binary provenance attestations. Candidate archive/runtime/reproducibility/license acceptance and R3 sustained runs remain later work. Preparing or linting this workflow locally does not execute GitHub Actions or activate branch rules.

## Reviewed evidence gates

The [R2 follow-up review](../../engineering/development/software-release-r2-review.md) records stronger gates: canonical source fingerprints and an 8,192-byte maximum receipt, one Linux output emitted after verified native/floor container cleanup, fatal sanitizer findings, exact six-suite CTest XML execution reports, and payload receipts bound to the independently supplied manifest. Source-build runs also require installed/executable hash evidence. Qualification refuses provisioning unless the launcher supplies its disposable-guest marker and /qualification is actually a tmpfs mount; invoke the launcher rather than running prepare.py directly on a host. The extracted project license must equal the reviewed MIT root license, while later notice/provenance acceptance remains separate.

R4 adds original packaging regressions to the existing helper and macOS development lane receipts. Schema 2 provisional package manifests additionally require exact source-snapshot identity and installed file modes; see the [package guide](../../docs/release.md). This local wiring has not yet been published or executed by hosted CI.

The CMake floor archive is fetched from the official Kitware GitHub release asset over HTTPS with curl certificate verification enabled. This avoids the expired certificate encountered at the earlier cmake.org URL while retaining version 3.16.9 and SHA256 1708361827a5a0de37d55f5c9698004c035abb1de6120a376d5d59a81630191f. The archive is checked before extraction; no trust-store override, insecure curl option, version update, or checksum update is used. The Python floor source and all execution/receipt gates remain unchanged.
