# Selected Linux target qualification

The original milestone 5 selection was isolated Debian 12 ARM64; the Docker launcher still defaults to that architecture. The explicitly selected native-package path below additionally supports x86-64. These original MIT helpers use Python stdlib, original project tests, CMake, native compiler tools, systemd-analyze, and separately supplied external tool filesystems. No reference implementation is incorporated; actual host/panel integration uses separate pinned clients. See the [scope](../../engineering/development/milestone-5-scope.md), [operating guide](../../docs/operation.md), [review](../../engineering/development/milestone-5-review.md), and [provenance](../../engineering/licenses/milestone-5.md).

From the repository root, with Docker and host Python 3.9+ available and the ARM64 image prepared:

```sh
./tests/qualification/run-isolated.sh "$PWD/runs/milestone5/new-qualification"
```

The evidence directory must not exist. RMX_QUALIFICATION_IMAGE may name a compatible ARM64 image; the launcher resolves its actual immutable local ID and records inspect metadata. If the existing image is unavailable, build it with the original [milestone 4 recipe](../integration/Dockerfile):

```sh
docker build --platform linux/arm64 -t brewpi-emulator-m4-tools:portable tests/integration
```

Image preparation downloads external Debian/Python tools and needs network; qualification itself runs with no network. The base digest and Python requirements are pinned, but Debian repositories may produce newer packages, so a newly built image is a new environment requiring fresh qualification. The review records the actual tested image ID and versions, not a promise that the tag always denotes those bytes. No reference repository enters the image build context.

The launcher reserves fresh evidence, rejects another architecture, mounts source read-only and evidence writable, uses an owned container ID/init process, imposes a 900-second overall timeout, and cleans up the container on exit. It verifies removal through a successful Docker query; inability to verify cleanup fails the run. Missing, failed, or incomplete child reports fail even if the container exits zero. A failed child/launcher cannot leave a primary passing report; an earlier child report is archived separately. It creates only disposable container paths and ignored local evidence/image data. It does not install or activate a service on the user's host.

prepare.py creates UID/GID 2001 inside the container, builds Release and Debug/ASan/UBSan, executes all six native suites unprivileged, stages and audits six install files, checks that BUILD_SHARED_LIBS=ON still yields a runnable install without an uninstalled project library, inspects the AArch64 ELF/library closure and dynamic search paths, records actual package notices, verifies source-input hashes before and after execution, validates the generated unit syntax, and invokes service.py to exercise the exact configured commands under that account. runtime.py tests ownership/readiness, 1x/10x/60x pacing and partial-input waits, alternating ordered replies with a paused reader, full snapshot continuation, failed-checkpoint preservation, and deliberate SIGKILL/stale-link recovery. No systemd manager runs; namespace policies, boot ordering, physical Pi operation, and nine unresolved exact-firmware outcomes remain unqualified.

Require qualification-results.json and launcher-results.json to pass, including cleanup_verified=true. Inspect source-inventory.json/source-integrity.json, service-results.json, runtime-results, native-release/native-sanitize, tool/image metadata, install-inventory.json, ELF/library output, and individual build/test logs. Raw evidence is ignored and is not an MIT fixture oracle. Runtime thresholds describe the saved workload; they are not a universal latency or acceleration guarantee.

Run the small original negative regressions independently without Docker:

```sh
python3 tests/qualification/checks.py
python3 tests/qualification/launcher_checks.py
```

The six readiness checks verify queued-byte/termios preservation and invalid endpoint/process/limit rejection. The seven launcher checks substitute an original fake docker executable to verify evidence preservation, failure invalidation/owned cleanup, architecture rejection, isolation/image arguments, missing/nonpassing child evidence, unverified cleanup, and repeated termination during finalization. They do not count as actual container/runtime evidence. Their logs remain separate from the final target run.

## Native x86-64 package workflows

The original native_package.py helper runs the existing integration, qualification, or toolchain-free runtime workflow on an explicitly staged native x86-64 Linux host without requiring Docker there. It requires sudo/root provisioning, Linux namespaces, mount, ip, cp, and an external disposable Debian 12 filesystem. The launcher requires a new user-owned staging directory, a request.json with purpose="R4 native packaged qualification", architecture="amd64", and source_snapshot_sha256, plus source/, payload/, candidate.json, refs/, and a tools symlink to the selected external filesystem. Stage only independently authored candidate source/payloads and separate pinned read-only client references. No reference code is incorporated into the source archive.

Invoke python3 native_package.py launch PRIVATE_BASE ROLE under the explicitly authorized sudo boundary, with ROLE set to runtime, integration, or qualification. Every role reserves its own fresh directory and copies the external filesystem before changing test accounts or the configured prefix. Source, payload, manifest, and reference mounts are read-only; PID/mount/network/IPC/UTS namespaces and generic private PTYs isolate execution. Only private loopback is enabled. There are no physical devices, host account changes, host service actions, or systemd manager activation. Integration and qualification require the complete tools filesystem with PHP, Chromium, and systemd-analyze, and reject a smaller soak-only filesystem before building. Runtime requires the separate toolchain-free filesystem and drops to UID/GID 2001 before invoking the original runtime checker.

The native-launcher.json records host architecture, workflow exit, source snapshot, and owned PID-namespace cleanup. Accept it only together with complete original child evidence and matching payload/source receipts, never from exit status alone. The two-hour native workflow deadline accommodates a slow single-core test host; it does not change the existing child assertions, CTest deadlines, pacing thresholds, or R3 soak policy. Keep image/export identities, wrapper hashes, actual package hashes, and native-versus-emulated evidence explicit. native_package_checks.py exercises the root/PID boundary, native-architecture rejection, and dereferencing of a tool symlink before copying into the disposable directory.

Before provisioning, the launcher now checks the request's manifest digest, wrapper digest, version, architecture, source snapshot, and source-baseline consistency. It treats the named reviewed commit as a separate claim; the offline [R4 verifier](../../release/README.md) proves that association against Git rather than equating a baseline with a reviewed commit. Copy/provisioning failures produce a failed launcher record, retain partial setup evidence, and restore signal handlers. Cleanup refers to owned processes; retained files are not deleted. These additional guards were validated against the original passing requests without relabeling those executions as runs of the revised wrapper.

If an independently reproduced sanitizer startup failure requires it, request.json may explicitly set sanitizer_process_no_aslr=true for qualification only. The private ctest wrapper then uses setarch -R only in /qualification/build-sanitize and passes every other invocation through unchanged. Host sysctls, Release/runtime execution, instrumentation, test oracles, and sanitizer fatal-error behavior remain unchanged. Record the diagnostic, a fatal sanitizer positive control, this condition, and the original failed attempt; do not use it to hide an emulator failure. See the [upstream startup issue](https://github.com/google/sanitizers/issues/1614).
